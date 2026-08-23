"""Evidence quality, deterministic comparison, and recall matching tests."""

from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.main import create_app
from app.models.product import CanonicalProductSnapshot, ProductRecord
from app.models.regulatory import RecallMatchType, RecallRecord, RegulatoryRule, VerificationStatus
from app.services.regulatory.recalls import attach_match, classify_recall_match
from app.services.regulatory.rules import evaluate_snapshot, rule_can_evaluate
from fastapi.testclient import TestClient


def _rule(status: VerificationStatus = VerificationStatus.VERIFIED) -> RegulatoryRule:
    return RegulatoryRule(
        id="rule",
        source_id="source",
        jurisdiction="CA",
        authority="Health Canada",
        category="caffeinated-energy-drink",
        subject="caffeine",
        rule_type="maximum-per-serving",
        comparator="<=",
        threshold=180,
        unit="mg",
        applicability_notes="Context only for a US formulation.",
        verification_status=status,
        evidence_excerpt="In Canada, CEDs can contain a maximum of 180 mg of caffeine per serving.",
    )


def _snapshot(caffeine: float) -> CanonicalProductSnapshot:
    return CanonicalProductSnapshot(
        brand="CELSIUS",
        product_name="CELSIUS Sparkling Orange",
        product_line="CELSIUS",
        flavor="Sparkling Orange",
        serving_size={"value": 12, "unit": "fl oz", "ml": 355},
        caffeine_mg=caffeine,
        source={
            "url": "https://www.celsius.com/products/celsius/sparkling-orange/",
            "market": "US",
            "scraped_at": "2026-08-22T12:00:00Z",
        },
    )


def _product() -> ProductRecord:
    return ProductRecord(
        id="red-bull-original",
        display_name="Red Bull Original Energy Drink",
        manufacturer="Red Bull",
        active_snapshot=CanonicalProductSnapshot(
            brand="Red Bull",
            product_name="Red Bull Energy Drink",
            product_line="Red Bull Energy Drink",
            flavor="Original",
            source={
                "url": "https://www.redbull.com/us-en/energydrink/red-bull-energy-drink",
                "market": "US",
                "scraped_at": "2026-08-22T12:00:00Z",
            },
        ),
    )


def _recall(description: str, firm: str = "Red Bull North America") -> RecallRecord:
    return RecallRecord(
        id="recall",
        authority="U.S. Food and Drug Administration",
        jurisdiction="US",
        product_description=description,
        brand_manufacturer=firm,
        reason="Labeling issue",
        source_url="https://api.fda.gov/food/enforcement.json",
        retrieved_at=datetime.now(UTC),
    )


def test_only_verified_structured_rules_are_eligible() -> None:
    assert rule_can_evaluate(_rule())
    assert not rule_can_evaluate(_rule(VerificationStatus.SUPPORTED))
    assert not rule_can_evaluate(_rule(VerificationStatus.NEEDS_REVIEW))


def test_caffeine_finding_reports_difference_and_context() -> None:
    finding = evaluate_snapshot("celsius-sparkling-orange", _snapshot(200), _rule())
    assert finding is not None
    assert finding.finding_type == "exceeds_threshold"
    assert finding.difference == 20
    assert "Market-specific formulations may differ" in finding.explanation_template

    within = evaluate_snapshot("celsius-sparkling-orange", _snapshot(180), _rule())
    assert within is not None
    assert within.finding_type == "within_threshold"


def test_recall_matching_requires_brand_and_product_identity() -> None:
    product = _product()
    exact = _recall("Red Bull Energy Drink Original 250 mL")
    assert classify_recall_match(product, exact) is RecallMatchType.EXACT_PRODUCT

    family = _recall("Red Bull Energy Drink assorted flavors")
    assert classify_recall_match(product, family) is RecallMatchType.PRODUCT_FAMILY

    unrelated = _recall("Monster Energy Original", "Monster Beverage Corporation")
    assert classify_recall_match(product, unrelated) is RecallMatchType.NO_MATCH
    assert attach_match(product, unrelated).matched_product_id is None


def test_regulatory_provenance_and_findings_endpoints(tmp_path: Path) -> None:
    settings = Settings(
        REGLENS_DATA_PROVIDER="fixture",
        REGLENS_DATABASE_PATH=tmp_path / "reglens.db",
    )
    with TestClient(create_app(settings)) as client:
        sources = client.get("/api/sources")
        assert sources.status_code == 200
        assert len(sources.json()) == 5
        assert all(source["content"] for source in sources.json())
        assert all(source["status"] == "current" for source in sources.json())
        rules = client.get("/api/rules")
        assert any(rule["verification_status"] == "VERIFIED" for rule in rules.json())
        findings = client.get("/api/findings")
        assert any(item["finding_type"] == "exceeds_threshold" for item in findings.json())
        discoveries = client.get("/api/discoveries")
        assert discoveries.status_code == 200
        cards = {card["id"]: card for card in discoveries.json()}
        assert set(cards) == {
            "canada-caffeine-comparison",
            "canada-children-guidance",
            "fda-red-three-status-change",
            "recall-match-specificity",
        }
        assert cards["canada-caffeine-comparison"]["evidence_status"] == "VERIFIED"
        assert len(cards["canada-caffeine-comparison"]["related_product_ids"]) == 3
        assert (
            "reign-orange-dreamsicle"
            not in cards["canada-caffeine-comparison"]["related_product_ids"]
        )
        assert cards["fda-red-three-status-change"]["source_url"].startswith("https://www.fda.gov/")
