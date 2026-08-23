"""Primary regulatory evidence seeded for offline/demo operation."""

from __future__ import annotations

from datetime import UTC, datetime

from app.db.database import Database
from app.models.regulatory import RecallRecord, RegulatoryRule, VerificationStatus
from app.repositories.regulatory import RegulatoryRepository
from app.services.regulatory.ingestion import seed_regulatory_sources

THRESHOLD_EXCERPT = "In Canada, CEDs can contain a maximum of 180 mg of caffeine per serving."
UNDER_14_EXCERPT = (
    "CEDs are not recommended for those under 14 years old, those who are pregnant "
    "or breastfeeding, or people sensitive to caffeine."
)


def seed_regulatory_evidence(database: Database) -> None:
    """Idempotently seed only facts directly supported by the Health Canada page."""
    repository = RegulatoryRepository(database)
    seed_regulatory_sources(repository)
    source_id = "health-canada-caffeinated-energy-drinks"
    repository.upsert_rule(
        RegulatoryRule(
            id="ca-ced-caffeine-max-180mg-serving",
            source_id=source_id,
            jurisdiction="CA",
            authority="Health Canada",
            category="caffeinated-energy-drink",
            subject="caffeine",
            rule_type="maximum-per-serving",
            comparator="<=",
            threshold=180,
            unit="mg",
            affected_population="CED products in Canada",
            applicability_notes=(
                "Compare only as Canadian regulatory context. A U.S. formulation exceeding this "
                "threshold is not by itself evidence of illegal sale in Canada; formulations and "
                "market authorization must be confirmed separately."
            ),
            verification_status=VerificationStatus.VERIFIED,
            evidence_excerpt=THRESHOLD_EXCERPT,
        )
    )
    repository.upsert_rule(
        RegulatoryRule(
            id="ca-ced-under-14-guidance",
            source_id=source_id,
            jurisdiction="CA",
            authority="Health Canada",
            category="caffeinated-energy-drink",
            subject="affected_population",
            rule_type="guidance",
            comparator="context",
            affected_population="under 14 years old",
            applicability_notes=(
                "Contextual Health Canada guidance; no numeric product comparison is appropriate."
            ),
            verification_status=VerificationStatus.SUPPORTED,
            evidence_excerpt=UNDER_14_EXCERPT,
        )
    )


def red_bull_openfda_recall() -> RecallRecord:
    """Return the official Red Bull Energy Drink enforcement record (event 81503)."""
    return RecallRecord(
        id="openfda-81503",
        authority="U.S. Food and Drug Administration",
        jurisdiction="US",
        product_description=(
            "Red Bull Energy Drink, 8.4 Fl. oz. (250 mL); UPC 6 11269 99100 0 "
            "(on cans) and 61126991246 (on cases)."
        ),
        brand_manufacturer="Red Bull North America Inc.",
        reason=(
            "Investigation of complaints of off taste color and taste found that the product "
            "contained 3 times the level of the primary ingredients specified in the "
            "product formulation."
        ),
        classification_status="Class III; Terminated",
        event_date=datetime(2018, 12, 5, tzinfo=UTC),
        source_url="https://api.fda.gov/food/enforcement.json?search=event_id:81503",
        retrieved_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
