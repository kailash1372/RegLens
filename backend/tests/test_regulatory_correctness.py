"""Regression coverage for evidence freshness and deterministic regulatory state."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db.database import Database
from app.models.product import CanonicalProductSnapshot, ProductRecord
from app.models.regulatory import (
    RegulatoryFinding,
    RegulatoryRule,
    RegulatorySource,
    RegulatorySourceStatus,
    VerificationStatus,
)
from app.repositories.products import ProductRepository
from app.repositories.regulatory import RegulatoryRepository
from app.services.llm.ask import _has_supported_citations
from app.services.regulatory.rules import evaluate_snapshot, rule_can_evaluate
from app.services.regulatory.service import RegulatoryService
from app.services.retrieval.fts import RegulatoryRetriever


def _source(source_id: str, jurisdiction: str = "CA") -> RegulatorySource:
    return RegulatorySource(
        id=source_id,
        authority="Example Authority",
        jurisdiction=jurisdiction,
        title=f"{jurisdiction} caffeine guidance",
        source_url=f"https://example.test/{source_id}",
        retrieved_at=datetime.now(UTC),
        source_type="guidance",
        content="Caffeine evidence text",
        evidence_text="Caffeine maximum and children guidance.",
        evidence_anchor="Caffeine evidence text",
        content_hash="hash",
    )


def _rule(rule_id: str = "rule", **updates: object) -> RegulatoryRule:
    value: dict[str, object] = {
        "id": rule_id,
        "source_id": "source",
        "jurisdiction": "CA",
        "authority": "Example Authority",
        "category": "caffeinated-energy-drink",
        "subject": "caffeine",
        "rule_type": "maximum-per-serving",
        "comparator": "<=",
        "threshold": 180,
        "unit": "mg",
        "affected_population": None,
        "applicability_notes": "Canadian context.",
        "verification_status": VerificationStatus.VERIFIED,
        "evidence_excerpt": "Caffeine maximum.",
    }
    value.update(updates)
    return RegulatoryRule.model_validate(value)


def _finding(product_id: str, rule_id: str) -> RegulatoryFinding:
    return RegulatoryFinding(
        product_id=product_id,
        rule_id=rule_id,
        finding_type="within_threshold",
        observed_value=100,
        threshold_value=180,
        difference=-80,
        unit="mg",
        status="context",
        explanation_template="Evidence-backed comparison.",
        evaluated_at=datetime.now(UTC),
    )


def test_effective_dates_disable_expired_and_future_rules() -> None:
    now = datetime.now(UTC)
    assert not rule_can_evaluate(_rule(effective_from=now + timedelta(days=1)), evaluated_at=now)
    assert not rule_can_evaluate(
        _rule(effective_until=now - timedelta(seconds=1)), evaluated_at=now
    )
    assert rule_can_evaluate(
        _rule(effective_from=now - timedelta(days=1), effective_until=now + timedelta(days=1)),
        evaluated_at=now,
    )


def test_rule_upsert_replaces_all_rule_fields_and_findings_replace_atomically(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "regulatory.db")
    database.initialize()
    regulatory = RegulatoryRepository(database)
    products = ProductRepository(database)
    products.upsert_product(
        ProductRecord(id="example", display_name="Example", manufacturer="Example")
    )
    regulatory.upsert_source(_source("source"))
    regulatory.upsert_rule(_rule("rule-a"))
    regulatory.upsert_rule(_rule("rule-b"))
    regulatory.replace_findings(
        "example", [_finding("example", "rule-a"), _finding("example", "rule-b")]
    )

    replacement = _rule(
        "rule-a",
        jurisdiction="US",
        authority="Updated Authority",
        category="soft-drink",
        subject="sodium",
        rule_type="guidance",
        comparator=">=",
        threshold=20,
        unit="mg",
        affected_population="adults",
        applicability_notes="Updated applicability.",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        effective_until=datetime(2027, 1, 1, tzinfo=UTC),
        verification_status=VerificationStatus.SUPPORTED,
        evidence_excerpt="Updated evidence.",
    )
    regulatory.upsert_rule(replacement)
    regulatory.replace_findings("example", [_finding("example", "rule-a")])

    stored = next(rule for rule in regulatory.list_rules() if rule.id == "rule-a")
    assert stored.model_dump() == replacement.model_dump()
    assert [finding.rule_id for finding in regulatory.list_findings("example")] == ["rule-a"]


def test_retrieval_filters_refresh_failed_sources_and_requested_jurisdiction(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "retrieval.db")
    database.initialize()
    repository = RegulatoryRepository(database)
    repository.upsert_source(_source("ca-current", "CA"))
    repository.upsert_source(_source("us-current", "US"))
    failed = _source("ca-failed", "CA").model_copy(
        update={"status": RegulatorySourceStatus.REFRESH_FAILED}
    )
    repository.upsert_source(failed)

    passages = RegulatoryRetriever(database).search(
        "caffeine children",
        jurisdictions=["CA"],
        topics=["children", "caffeine"],
    )

    assert [passage.source_id for passage in passages] == ["ca-current"]
    assert passages[0].jurisdiction == "CA"


def test_llm_citations_must_be_supplied_by_the_evidence_packet() -> None:
    packet = {"evidence": [{"source_id": "health-canada", "text": "Evidence"}]}
    assert _has_supported_citations("Supported [health-canada]", packet)
    assert not _has_supported_citations("Unsupported [invented-source]", packet)
    assert not _has_supported_citations("No citation", packet)


def test_expired_rule_does_not_create_a_finding() -> None:
    snapshot = CanonicalProductSnapshot(
        caffeine_mg=200,
        source={
            "url": "https://example.test/product",
            "market": "CA",
            "scraped_at": "2026-08-23T00:00:00Z",
        },
    )
    rule = _rule(effective_until=datetime.now(UTC) - timedelta(days=1))
    assert evaluate_snapshot("example", snapshot, rule) is None


def test_per_serving_rule_requires_a_stated_serving_basis() -> None:
    snapshot = CanonicalProductSnapshot(
        caffeine_mg=300,
        source={
            "url": "https://example.test/product",
            "market": "US",
            "scraped_at": "2026-08-23T00:00:00Z",
        },
    )

    assert evaluate_snapshot("reign-example", snapshot, _rule()) is None


def test_evaluation_deletes_finding_when_new_snapshot_no_longer_applies(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "stale-finding.db")
    database.initialize()
    products = ProductRepository(database)
    regulatory = RegulatoryRepository(database)
    products.upsert_product(
        ProductRecord(
            id="example",
            display_name="Example Energy",
            manufacturer="Example",
            category="energy_drink",
        )
    )
    regulatory.upsert_source(_source("source"))
    regulatory.upsert_rule(_rule())
    service = RegulatoryService(regulatory, products)

    with_caffeine = CanonicalProductSnapshot(
        caffeine_mg=200,
        serving_size={"value": 1, "unit": "can"},
        source={
            "url": "https://example.test/product",
            "market": "US",
            "scraped_at": "2026-08-23T00:00:00Z",
        },
    )
    products.save_valid_snapshot("example", with_caffeine)
    product = products.get_product("example")
    assert product is not None
    service.evaluate_product(product)
    assert len(regulatory.list_findings("example")) == 1

    without_caffeine = with_caffeine.model_copy(
        update={
            "caffeine_mg": None,
            "source": with_caffeine.source.model_copy(
                update={"scraped_at": datetime(2026, 8, 24, tzinfo=UTC)}
            ),
        }
    )
    products.save_valid_snapshot("example", without_caffeine)
    refreshed = products.get_product("example")
    assert refreshed is not None
    service.evaluate_product(refreshed)

    assert regulatory.list_findings("example") == []
