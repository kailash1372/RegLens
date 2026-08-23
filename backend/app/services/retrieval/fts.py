"""Jurisdiction-aware SQLite FTS5 retrieval for regulatory evidence."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from app.db.database import Database
from app.models.regulatory import RegulatorySourceStatus


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    """A ranked evidence passage carrying complete provenance."""

    source_id: str
    title: str
    authority: str
    jurisdiction: str
    source_url: str
    evidence_text: str
    score: float


class RegulatoryRetriever:
    """Search current primary evidence, preferring the requested legal context."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def search(
        self,
        query: str,
        limit: int = 6,
        *,
        jurisdictions: Iterable[str] | None = None,
        statuses: Iterable[RegulatorySourceStatus | str] | None = None,
        topics: Iterable[str] | None = None,
    ) -> list[RetrievedPassage]:
        """Return current, jurisdiction-filtered passages ranked for stated topics."""
        tokens = re.findall(r"[A-Za-z0-9]{2,}", query.lower())
        if not tokens:
            return []
        requested_jurisdictions = _normalized_values(jurisdictions)
        requested_statuses = tuple(
            value.lower()
            for value in _normalized_values(statuses or (RegulatorySourceStatus.CURRENT,))
        )
        requested_topics = _normalized_values(topics)
        where_sql, filters = _source_filters(requested_jurisdictions, requested_statuses)
        match_query = " OR ".join(f'"{token}"' for token in dict.fromkeys(tokens))
        with self.database.connect() as connection:
            try:
                rows = connection.execute(
                    f"""
                    SELECT f.source_id, f.title, f.authority, f.jurisdiction, f.evidence_text,
                           s.source_url, bm25(regulatory_evidence_fts) AS score
                    FROM regulatory_evidence_fts f
                    JOIN regulatory_sources s ON s.id = f.source_id
                    WHERE regulatory_evidence_fts MATCH ? {where_sql}
                    ORDER BY score
                    LIMIT ?
                    """,
                    (match_query, *filters, limit * 3),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
            if not rows:
                like = "%" + "%".join(tokens[:6]) + "%"
                rows = connection.execute(
                    f"""
                    SELECT id AS source_id, title, authority, jurisdiction, evidence_text,
                           source_url, 0.0 AS score
                    FROM regulatory_sources s
                    WHERE (lower(evidence_text) LIKE ? OR lower(title) LIKE ?) {where_sql}
                    ORDER BY retrieved_at DESC
                    LIMIT ?
                    """,
                    (like, like, *filters, limit * 3),
                ).fetchall()
            rule_text = _rule_text_by_source(connection, [row["source_id"] for row in rows])
        passages = [
            RetrievedPassage(
                source_id=row["source_id"],
                title=row["title"],
                authority=row["authority"],
                jurisdiction=row["jurisdiction"],
                source_url=row["source_url"],
                evidence_text=row["evidence_text"],
                score=float(row["score"]),
            )
            for row in rows
        ]
        passages.sort(
            key=lambda passage: _ranking_key(
                passage,
                requested_jurisdictions,
                requested_topics,
                rule_text.get(passage.source_id, ""),
            )
        )
        return passages[:limit]


def _source_filters(
    jurisdictions: tuple[str, ...],
    statuses: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    """Build parameterized source filters shared by FTS and LIKE retrieval."""
    clauses: list[str] = []
    values: list[str] = []
    if jurisdictions:
        placeholders = ", ".join("?" for _ in jurisdictions)
        clauses.append(f"AND upper(s.jurisdiction) IN ({placeholders})")
        values.extend(jurisdictions)
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        clauses.append(f"AND lower(s.status) IN ({placeholders})")
        values.extend(statuses)
    return " " + " ".join(clauses), tuple(values)


def _rule_text_by_source(
    connection: sqlite3.Connection,
    source_ids: list[str],
) -> dict[str, str]:
    """Include rule applicability when ranking evidence without exposing a new fact layer."""
    if not source_ids:
        return {}
    placeholders = ", ".join("?" for _ in source_ids)
    rows = connection.execute(
        f"""
        SELECT source_id, category, subject, rule_type, applicability_notes
        FROM regulatory_rules
        WHERE source_id IN ({placeholders})
        """,
        source_ids,
    ).fetchall()
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(row["source_id"], []).append(
            " ".join(
                str(row[column] or "")
                for column in ("category", "subject", "rule_type", "applicability_notes")
            )
        )
    return {source_id: " ".join(parts).casefold() for source_id, parts in grouped.items()}


def _ranking_key(
    passage: RetrievedPassage,
    jurisdictions: tuple[str, ...],
    topics: tuple[str, ...],
    applicability_text: str,
) -> tuple[int, int, float, str]:
    text = " ".join(
        (passage.title, passage.authority, passage.evidence_text, applicability_text)
    ).casefold()
    topic_hits = sum(any(term in text for term in _topic_terms(topic)) for topic in topics)
    jurisdiction_penalty = int(
        bool(jurisdictions) and passage.jurisdiction.upper() not in jurisdictions
    )
    # SQLite BM25 returns lower (often negative) scores for stronger matches.
    return (-topic_hits, jurisdiction_penalty, passage.score, passage.source_id)


def _topic_terms(topic: str) -> tuple[str, ...]:
    """Map product-language intents to regulatory wording and rule applicability."""
    return {
        "children": ("children", "under 14", "affected population"),
        "caffeine": ("caffeine", "caffeinated", "ced"),
        "ingredients": ("ingredient", "additive", "color"),
        "threshold": ("maximum", "threshold", "per serving"),
        "recall": ("recall", "safety alert", "enforcement"),
        "regulatory": ("regulation", "guidance", "authorization"),
    }.get(topic, (topic,))


def _normalized_values(values: Iterable[RegulatorySourceStatus | str] | None) -> tuple[str, ...]:
    """Normalize and deduplicate external filter values deterministically."""
    if not values:
        return ()
    return tuple(
        dict.fromkeys(
            str(value.value if isinstance(value, RegulatorySourceStatus) else value).strip().upper()
            for value in values
            if str(value).strip()
        )
    )
