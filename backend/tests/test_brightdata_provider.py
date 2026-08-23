"""Offline contract tests for the Bright Data collection adapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from app.core.config import Settings
from app.db.database import Database
from app.models.health import ScraperStatus
from app.models.product import CanonicalProductSnapshot, ProductRecord
from app.models.scraper import CollectedProductResult
from app.repositories.products import ProductRepository
from app.services.products.providers import (
    BrightDataProductProvider,
    InvalidProductPayloadError,
    ProductDataProvider,
    ProductProviderError,
)
from app.services.products.service import ProductService


def test_bright_data_provider_triggers_polls_and_normalizes_wrapped_output() -> None:
    """A mock collector response becomes a canonical snapshot without live calls."""
    requests: list[httpx.Request] = []
    responses = iter(
        [
            {"collection_id": "collection-123"},
            {"status": "running"},
            {
                "output": [
                    {
                        "output": {
                            "brand": "Example",
                            "product_name": "Sparkling Energy",
                            "caffeine_mg": 200,
                            "scraper_assets": {
                                "nutrition_label_images": [
                                    {
                                        "url": "https://images.manufacturer.test/label.png",
                                        "content_type": "image",
                                        "purpose": "nutrition_label",
                                    }
                                ]
                            },
                        }
                    }
                ]
            },
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=next(responses))

    provider = BrightDataProductProvider(
        api_token="test-token",
        base_url="https://brightdata.test",
        collector_ids={"example": "collector-123"},
        product_urls={"example": "https://manufacturer.test/example"},
        poll_interval_seconds=0,
        max_poll_attempts=3,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleeper=lambda _: None,
    )

    result = provider.fetch("example")

    assert result.snapshot.brand == "Example"
    assert result.snapshot.caffeine_mg == 200
    assert result.snapshot.sugar_g is None
    assert str(result.snapshot.source.url) == "https://manufacturer.test/example"
    assert len(result.scraper_assets.nutrition_label_images) == 1
    assert [request.method for request in requests] == ["POST", "GET", "GET"]
    assert requests[0].url.params["collector"] == "collector-123"
    assert requests[0].url.params["queue_next"] == "1"
    assert requests[1].url.params["id"] == "collection-123"


def test_bright_data_provider_rejects_missing_configuration_before_request() -> None:
    """A missing token must not result in an accidental network call."""
    attempted_request = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempted_request
        attempted_request = True
        return httpx.Response(500)

    provider = BrightDataProductProvider(
        api_token=None,
        base_url="https://brightdata.test",
        collector_ids={"example": "collector-123"},
        product_urls={"example": "https://manufacturer.test/example"},
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ProductProviderError, match="token"):
        provider.fetch("example")
    assert not attempted_request


def test_bright_data_provider_fetches_separate_output_after_completed_poll() -> None:
    """A completed status can lead to a separately configured output endpoint."""
    responses = iter(
        [
            {"collection": {"id": "collection-456"}},
            {"status": "completed"},
            {
                "items": [
                    {
                        "input": {"url": "https://manufacturer.test/example"},
                        "output": {
                            "brand": "Example",
                            "product_name": "Example Energy",
                            "caffeine_mg": 180,
                        },
                    }
                ]
            },
        ]
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=next(responses))

    provider = BrightDataProductProvider(
        api_token="test-token",
        base_url="https://brightdata.test",
        collector_ids={"example": "collector-456"},
        product_urls={"example": "https://manufacturer.test/example"},
        poll_path="/collections/status",
        output_path="/collections/output",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.fetch("example")

    assert result.snapshot.caffeine_mg == 180
    assert [request.url.path for request in requests] == [
        "/dca/trigger",
        "/collections/status",
        "/collections/output",
    ]


def test_malformed_refresh_retains_snapshot_and_marks_invalid_output(tmp_path: Path) -> None:
    """Invalid canonical output is visible in health but never replaces valid data."""
    database = Database(tmp_path / "reglens.db")
    database.initialize()
    repository = ProductRepository(database)
    product = ProductRecord(id="example", display_name="Example", manufacturer="Example Inc.")
    repository.upsert_product(product)
    provider = StaticProvider(_canonical_payload(), collector_id="collector-example")
    service = ProductService(repository, provider)
    first_refresh = service.refresh("example")

    service.provider = MalformedProvider()
    refreshed = service.refresh("example")
    health = repository.list_health()[0]

    assert first_refresh.active_snapshot is not None
    assert refreshed.active_snapshot is not None
    assert refreshed.active_snapshot.caffeine_mg == 200
    assert health.status is ScraperStatus.INVALID_OUTPUT
    assert health.schema_valid is False
    assert health.collector_id == "collector-example"


def test_market_mismatch_is_rejected_without_persisting_snapshot(tmp_path: Path) -> None:
    """A market variant cannot silently accept another market's formulation."""
    database = Database(tmp_path / "market.db")
    database.initialize()
    repository = ProductRepository(database)
    repository.upsert_product(
        ProductRecord(
            id="fanta-orange-ca",
            display_name="Fanta Orange — Canada",
            manufacturer="Coca-Cola",
            canonical_family="fanta-orange",
            market="CA",
            category="soft_drink",
        )
    )
    service = ProductService(repository, StaticProvider(_canonical_payload()))

    product = service.refresh("fanta-orange-ca")
    health = repository.list_health()[0]

    assert product.active_snapshot is None
    assert health.status is ScraperStatus.INVALID_OUTPUT
    assert "does not match catalog market" in (health.last_error or "")


def test_bright_data_rejects_structural_output_without_product_identity() -> None:
    """An all-null extraction must not become a valid live snapshot."""
    responses = iter(
        [
            {"collection_id": "collection-identity"},
            [{"brand": None, "product_name": None}],
        ]
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses))

    provider = BrightDataProductProvider(
        api_token="secret",
        base_url="https://api.brightdata.test",
        collector_ids={"example": "collector-123"},
        product_urls={"example": "https://example.com/product"},
        poll_interval_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(InvalidProductPayloadError, match="variant identity"):
        provider.fetch("example")


def test_ingredient_index_preserves_unmatched_manufacturer_text(tmp_path: Path) -> None:
    """Normalization preparation never destroys or guesses an ingredient identity."""
    database = Database(tmp_path / "ingredients.db")
    database.initialize()
    repository = ProductRepository(database)
    repository.upsert_product(
        ProductRecord(id="example", display_name="Example", manufacturer="Example Inc.")
    )
    payload = _canonical_payload()
    payload["ingredients"] = ["FD&C Red No. 40", "Natural Flavor"]

    ProductService(repository, StaticProvider(payload)).refresh("example")
    ingredients = repository.list_ingredients("example")

    assert [item.original_label_name for item in ingredients] == [
        "FD&C Red No. 40",
        "Natural Flavor",
    ]
    assert all(item.canonical_ingredient_id is None for item in ingredients)
    assert all(item.match_type == "unmatched" for item in ingredients)


def test_bright_data_settings_collectors_filter_empty_values() -> None:
    """Only configured collector IDs are passed to the production provider."""
    settings = Settings(
        _env_file=None,
        REGLENS_DATA_PROVIDER="brightdata",
        BRIGHTDATA_COLLECTOR_CELSIUS="collector-celsius",
    )

    assert settings.brightdata_collectors == {"celsius-sparkling-orange": "collector-celsius"}


class StaticProvider(ProductDataProvider):
    """Test provider returning an already-canonical payload."""

    def __init__(self, payload: dict[str, object], collector_id: str | None = None) -> None:
        self.payload = payload
        self._collector_id = collector_id

    def fetch(self, _: str) -> CollectedProductResult:
        return CollectedProductResult(
            snapshot=CanonicalProductSnapshot.model_validate(self.payload)
        )

    def collector_id_for(self, _: str) -> str | None:
        return self._collector_id


class MalformedProvider(ProductDataProvider):
    """Test provider representing schema-invalid upstream collector output."""

    def fetch(self, _: str) -> CollectedProductResult:
        raise InvalidProductPayloadError(
            "Bright Data output violates the canonical product schema."
        )


def _canonical_payload() -> dict[str, object]:
    return {
        "brand": "Example",
        "product_name": "Example Energy",
        "serving_size": {"value": 12, "unit": "fl oz", "ml": 355},
        "caffeine_mg": 200,
        "nutrition_facts": [],
        "ingredients": [],
        "warnings": [],
        "claims": [],
        "source": {
            "url": "https://manufacturer.test/example",
            "market": "US",
            "scraped_at": "2026-08-22T12:00:00Z",
        },
    }
