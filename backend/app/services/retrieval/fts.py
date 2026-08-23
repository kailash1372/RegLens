"""SQLite FTS5/BM25 retrieval with a deterministic LIKE fallback."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from app.db.database import Database


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
    """Search retained source text without requiring an embedding service."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def search(self, query: str, limit: int = 6) -> list[RetrievedPassage]:
        """Return BM25-ranked passages, falling back to token overlap when needed."""
        tokens = re.findall(r"[A-Za-z0-9]{2,}", query.lower())
        if not tokens:
            return []
        match_query = " OR ".join(f'"{token}"' for token in dict.fromkeys(tokens))
        with self.database.connect() as connection:
            try:
                rows = connection.execute(
                    """
                    SELECT f.source_id, f.title, f.authority, f.jurisdiction, f.evidence_text,
                           s.source_url, bm25(regulatory_evidence_fts) AS score
                    FROM regulatory_evidence_fts f
                    JOIN regulatory_sources s ON s.id = f.source_id
                    WHERE regulatory_evidence_fts MATCH ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (match_query, limit),
                ).fetchall()
            except sqlite3.OperationalError:  # FTS availability varies across system SQLite builds.
                rows = []
            if not rows:
                like = "%" + "%".join(tokens[:6]) + "%"
                rows = connection.execute(
                    """
                    SELECT id AS source_id, title, authority, jurisdiction, evidence_text,
                           source_url, 0.0 AS score
                    FROM regulatory_sources
                    WHERE lower(evidence_text) LIKE ? OR lower(title) LIKE ?
                    ORDER BY retrieved_at DESC
                    LIMIT ?
                    """,
                    (like, like, limit),
                ).fetchall()
        return [
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
