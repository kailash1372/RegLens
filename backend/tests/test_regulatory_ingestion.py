"""Authoritative source corpus ingestion and last-known-good behavior."""

from pathlib import Path

import httpx
from app.db.database import Database
from app.models.regulatory import RegulatorySourceStatus
from app.repositories.regulatory import RegulatoryRepository
from app.services.regulatory.ingestion import (
    SOURCE_DEFINITIONS,
    RegulatorySourceIngestor,
    seed_regulatory_sources,
)
from app.services.regulatory.seed import seed_regulatory_evidence


def _repository(tmp_path: Path) -> RegulatoryRepository:
    database = Database(tmp_path / "sources.db")
    database.initialize()
    return RegulatoryRepository(database)


def test_preserved_corpus_contains_five_primary_sources(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    seed_regulatory_sources(repository)

    sources = repository.list_sources()
    assert {source.id for source in sources} == {
        "health-canada-caffeinated-energy-drinks",
        "health-canada-permitted-supplemental-ingredients",
        "fda-color-additives",
        "fda-fdc-red-no-3",
        "canada-recalls-open-data",
    }
    assert all(source.content for source in sources)
    assert all(source.status is RegulatorySourceStatus.CURRENT for source in sources)


def test_refresh_replaces_preserved_text_with_retrieved_page(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    seed_regulatory_sources(repository)
    expected_url = SOURCE_DEFINITIONS[0].source_url
    body = (
        "<html><body><main><h1>Current guidance</h1><p>"
        + SOURCE_DEFINITIONS[0].evidence_anchor
        + " "
        + "Evidence " * 40
        + "</p></main></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == expected_url
        return httpx.Response(200, headers={"content-type": "text/html"}, text=body)

    ingestor = RegulatorySourceIngestor(
        repository,
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    source = ingestor.refresh(SOURCE_DEFINITIONS[0].id)

    assert "Current guidance" in source.content
    assert source.status is RegulatorySourceStatus.CURRENT
    assert source.last_error is None
    assert source.content_hash is not None


def test_failed_refresh_preserves_content_and_marks_source_degraded(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    seed_regulatory_evidence(repository.database)
    source_id = SOURCE_DEFINITIONS[0].id
    before = next(source for source in repository.list_sources() if source.id == source_id)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    ingestor = RegulatorySourceIngestor(
        repository,
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = ingestor.refresh(source_id)

    assert result.content == before.content
    assert result.status is RegulatorySourceStatus.REFRESH_FAILED
    assert result.last_error is not None
    assert "503" not in result.last_error
    assert all(
        rule.verification_status.value == "NEEDS_REVIEW"
        for rule in repository.list_rules()
        if rule.source_id == source_id
    )


def test_missing_anchor_preserves_evidence_and_downgrades_dependent_rules(tmp_path: Path) -> None:
    """A changed page cannot silently retain VERIFIED automation authority."""
    repository = _repository(tmp_path)
    seed_regulatory_evidence(repository.database)
    source_id = SOURCE_DEFINITIONS[0].id
    before = next(source for source in repository.list_sources() if source.id == source_id)

    body = "<html><body><main><p>" + "New unrelated page text " * 30 + "</p></main></body></html>"

    ingestor = RegulatorySourceIngestor(
        repository,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, headers={"content-type": "text/html"}, text=body)
            )
        ),
    )
    result = ingestor.refresh(source_id)

    assert result.content == before.content
    assert result.content_hash == before.content_hash
    assert result.status is RegulatorySourceStatus.REFRESH_FAILED
    assert "evidence anchor" in (result.last_error or "")
    assert all(
        rule.verification_status.value == "NEEDS_REVIEW"
        for rule in repository.list_rules()
        if rule.source_id == source_id
    )

    seed_regulatory_evidence(repository.database)
    assert all(
        rule.verification_status.value == "NEEDS_REVIEW"
        for rule in repository.list_rules()
        if rule.source_id == source_id
    )
