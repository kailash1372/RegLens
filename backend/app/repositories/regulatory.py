"""SQLite persistence for regulatory evidence, findings, and recalls."""

from __future__ import annotations

from datetime import datetime

from app.db.database import Database
from app.models.regulatory import (
    RecallRecord,
    RegulatoryFinding,
    RegulatoryRule,
    RegulatorySource,
    RegulatorySourceStatus,
    VerificationStatus,
)


class RegulatoryRepository:
    """Persist source-backed regulatory records independently of product snapshots."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_source(self, source: RegulatorySource) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO regulatory_sources
                    (id, authority, jurisdiction, title, source_url, retrieved_at,
                     source_type, content, evidence_text, evidence_anchor, content_hash,
                     status, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET authority=excluded.authority,
                    jurisdiction=excluded.jurisdiction, title=excluded.title,
                    source_url=excluded.source_url, retrieved_at=excluded.retrieved_at,
                    source_type=excluded.source_type, content=excluded.content,
                    evidence_text=excluded.evidence_text,
                    evidence_anchor=excluded.evidence_anchor,
                    content_hash=excluded.content_hash, status=excluded.status,
                    last_error=excluded.last_error
                """,
                (
                    source.id,
                    source.authority,
                    source.jurisdiction,
                    source.title,
                    str(source.source_url),
                    source.retrieved_at.isoformat(),
                    source.source_type,
                    source.content,
                    source.evidence_text,
                    source.evidence_anchor,
                    source.content_hash,
                    source.status.value,
                    source.last_error,
                ),
            )
            connection.execute(
                "DELETE FROM regulatory_evidence_fts WHERE source_id = ?", (source.id,)
            )
            connection.execute(
                """
                INSERT INTO regulatory_evidence_fts(
                    source_id, title, authority, jurisdiction, evidence_text
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    source.id,
                    source.title,
                    source.authority,
                    source.jurisdiction,
                    source.evidence_text,
                ),
            )

    def record_source_refresh_failure(self, source_id: str, error: str) -> None:
        """Preserve evidence but disable automation that could not be reconfirmed."""
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE regulatory_sources
                SET status = ?, last_error = ?
                WHERE id = ?
                """,
                (RegulatorySourceStatus.REFRESH_FAILED.value, error, source_id),
            )
            connection.execute(
                """
                UPDATE regulatory_rules
                SET verification_status = ?
                WHERE source_id = ?
                """,
                (VerificationStatus.NEEDS_REVIEW.value, source_id),
            )

    def record_missing_evidence_anchor(self, source_id: str, error: str) -> None:
        """Preserve last-known-good evidence and disable rules it can no longer support."""
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE regulatory_sources
                SET status = ?, last_error = ?
                WHERE id = ?
                """,
                (RegulatorySourceStatus.REFRESH_FAILED.value, error, source_id),
            )
            connection.execute(
                """
                UPDATE regulatory_rules
                SET verification_status = ?
                WHERE source_id = ?
                """,
                (VerificationStatus.NEEDS_REVIEW.value, source_id),
            )

    def upsert_rule(self, rule: RegulatoryRule) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO regulatory_rules
                    (id, source_id, jurisdiction, authority, category, subject, rule_type,
                     comparator, threshold, unit, affected_population, applicability_notes,
                     effective_from, effective_until, verification_status, evidence_excerpt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET source_id=excluded.source_id,
                    jurisdiction=excluded.jurisdiction, authority=excluded.authority,
                    category=excluded.category, subject=excluded.subject,
                    rule_type=excluded.rule_type, comparator=excluded.comparator,
                    threshold=excluded.threshold, unit=excluded.unit,
                    affected_population=excluded.affected_population,
                    applicability_notes=excluded.applicability_notes,
                    effective_from=excluded.effective_from,
                    effective_until=excluded.effective_until,
                    verification_status=excluded.verification_status,
                    evidence_excerpt=excluded.evidence_excerpt
                """,
                (
                    rule.id,
                    rule.source_id,
                    rule.jurisdiction,
                    rule.authority,
                    rule.category,
                    rule.subject,
                    rule.rule_type,
                    rule.comparator,
                    rule.threshold,
                    rule.unit,
                    rule.affected_population,
                    rule.applicability_notes,
                    _iso(rule.effective_from),
                    _iso(rule.effective_until),
                    rule.verification_status.value,
                    rule.evidence_excerpt,
                ),
            )

    def upsert_finding(self, finding: RegulatoryFinding) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO regulatory_findings
                    (product_id, rule_id, finding_type, observed_value, threshold_value,
                     difference, unit, status, explanation_template, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, rule_id) DO UPDATE SET finding_type=excluded.finding_type,
                    observed_value=excluded.observed_value,
                    threshold_value=excluded.threshold_value,
                    difference=excluded.difference, unit=excluded.unit, status=excluded.status,
                    explanation_template=excluded.explanation_template,
                    evaluated_at=excluded.evaluated_at
                """,
                (
                    finding.product_id,
                    finding.rule_id,
                    finding.finding_type,
                    finding.observed_value,
                    finding.threshold_value,
                    finding.difference,
                    finding.unit,
                    finding.status,
                    finding.explanation_template,
                    finding.evaluated_at.isoformat(),
                ),
            )

    def replace_findings(
        self,
        product_id: str,
        findings: list[RegulatoryFinding],
    ) -> None:
        """Atomically replace one product's complete deterministic finding set."""
        if any(finding.product_id != product_id for finding in findings):
            raise ValueError("Every replacement finding must belong to the target product.")
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM regulatory_findings WHERE product_id = ?", (product_id,)
            )
            connection.executemany(
                """
                INSERT INTO regulatory_findings
                    (product_id, rule_id, finding_type, observed_value, threshold_value,
                     difference, unit, status, explanation_template, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        finding.product_id,
                        finding.rule_id,
                        finding.finding_type,
                        finding.observed_value,
                        finding.threshold_value,
                        finding.difference,
                        finding.unit,
                        finding.status,
                        finding.explanation_template,
                        finding.evaluated_at.isoformat(),
                    )
                    for finding in findings
                ],
            )

    def upsert_recall(self, recall: RecallRecord) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO recalls
                    (id, authority, jurisdiction, product_description, brand_manufacturer,
                     reason, classification_status, event_date, source_url, retrieved_at,
                     match_type, matched_product_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET match_type=excluded.match_type,
                    matched_product_id=excluded.matched_product_id,
                    retrieved_at=excluded.retrieved_at
                """,
                (
                    recall.id,
                    recall.authority,
                    recall.jurisdiction,
                    recall.product_description,
                    recall.brand_manufacturer,
                    recall.reason,
                    recall.classification_status,
                    _iso(recall.event_date),
                    str(recall.source_url),
                    recall.retrieved_at.isoformat(),
                    recall.match_type.value,
                    recall.matched_product_id,
                ),
            )

    def list_sources(self) -> list[RegulatorySource]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM regulatory_sources ORDER BY authority, title"
            ).fetchall()
        return [
            RegulatorySource(
                id=row["id"],
                authority=row["authority"],
                jurisdiction=row["jurisdiction"],
                title=row["title"],
                source_url=row["source_url"],
                retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
                source_type=row["source_type"],
                content=row["content"],
                evidence_text=row["evidence_text"],
                evidence_anchor=row["evidence_anchor"],
                content_hash=row["content_hash"],
                status=row["status"],
                last_error=row["last_error"],
            )
            for row in rows
        ]

    def list_rules(self) -> list[RegulatoryRule]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM regulatory_rules ORDER BY authority, subject"
            ).fetchall()
        return [
            RegulatoryRule(
                id=row["id"],
                source_id=row["source_id"],
                jurisdiction=row["jurisdiction"],
                authority=row["authority"],
                category=row["category"],
                subject=row["subject"],
                rule_type=row["rule_type"],
                comparator=row["comparator"],
                threshold=row["threshold"],
                unit=row["unit"],
                affected_population=row["affected_population"],
                applicability_notes=row["applicability_notes"],
                effective_from=_parse(row["effective_from"]),
                effective_until=_parse(row["effective_until"]),
                verification_status=VerificationStatus(row["verification_status"]),
                evidence_excerpt=row["evidence_excerpt"],
            )
            for row in rows
        ]

    def list_findings(self, product_id: str | None = None) -> list[RegulatoryFinding]:
        query = "SELECT * FROM regulatory_findings"
        args: tuple[str, ...] = ()
        if product_id:
            query += " WHERE product_id = ?"
            args = (product_id,)
        query += " ORDER BY product_id, rule_id"
        with self.database.connect() as connection:
            rows = connection.execute(query, args).fetchall()
        return [
            RegulatoryFinding(
                product_id=row["product_id"],
                rule_id=row["rule_id"],
                finding_type=row["finding_type"],
                observed_value=row["observed_value"],
                threshold_value=row["threshold_value"],
                difference=row["difference"],
                unit=row["unit"],
                status=row["status"],
                explanation_template=row["explanation_template"],
                evaluated_at=datetime.fromisoformat(row["evaluated_at"]),
            )
            for row in rows
        ]

    def list_recalls(self, product_id: str | None = None) -> list[RecallRecord]:
        query = "SELECT * FROM recalls"
        args: tuple[str, ...] = ()
        if product_id:
            query += " WHERE matched_product_id = ?"
            args = (product_id,)
        query += " ORDER BY event_date DESC, id"
        with self.database.connect() as connection:
            rows = connection.execute(query, args).fetchall()
        return [
            RecallRecord(
                id=row["id"],
                authority=row["authority"],
                jurisdiction=row["jurisdiction"],
                product_description=row["product_description"],
                brand_manufacturer=row["brand_manufacturer"],
                reason=row["reason"],
                classification_status=row["classification_status"],
                event_date=_parse(row["event_date"]),
                source_url=row["source_url"],
                retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
                match_type=row["match_type"] or "no_match",
                matched_product_id=row["matched_product_id"],
            )
            for row in rows
        ]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
