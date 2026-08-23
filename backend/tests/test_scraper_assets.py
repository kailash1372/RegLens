"""Scraper transport-asset validation and persistence tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import Settings
from app.db.database import Database
from app.main import create_app
from app.models.product import CanonicalProductSnapshot, ProductRecord
from app.models.scraper import CollectedProductResult, ScraperAssets
from app.repositories.products import ProductRepository
from app.services.products.providers import (
    FixtureProductProvider,
    InvalidProductPayloadError,
    ProductDataProvider,
)
from app.services.products.service import ProductService
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_collected_result_rejects_non_first_party_asset() -> None:
    """Asset metadata is strict and never accepts an unrelated image host."""
    with pytest.raises(ValidationError, match="first-party"):
        CollectedProductResult.model_validate(
            {
                "snapshot": _snapshot(),
                "scraper_assets": {
                    "nutrition_label_images": [
                        {
                            "url": "https://unrelated.example/label.png",
                            "content_type": "image",
                            "purpose": "nutrition_label",
                        }
                    ]
                },
            }
        )


def test_valid_assets_persist_and_invalid_refresh_preserves_them(tmp_path: Path) -> None:
    """Asset rows change only with a fully valid collected result."""
    database = Database(tmp_path / "reglens.db")
    database.initialize()
    repository = ProductRepository(database)
    repository.upsert_product(
        ProductRecord(id="example", display_name="Example", manufacturer="Example Inc.")
    )
    assets = ScraperAssets.model_validate(
        {
            "nutrition_label_images": [
                {
                    "url": "https://labels.manufacturer.test/nutrition.png",
                    "content_type": "image",
                    "purpose": "nutrition_label",
                }
            ]
        }
    )
    service = ProductService(repository, StaticProvider(_snapshot(), assets))

    service.refresh("example")
    stored_before_failure = repository.get_scraper_assets("example")
    service.provider = InvalidProvider()
    service.refresh("example")
    stored_after_failure = repository.get_scraper_assets("example")

    assert stored_before_failure is not None
    assert stored_after_failure == stored_before_failure
    assert len(stored_after_failure.scraper_assets.nutrition_label_images) == 1


def test_product_assets_endpoint_returns_separate_transport_metadata(tmp_path: Path) -> None:
    """The API exposes asset metadata without adding it to canonical snapshots."""
    settings = Settings(
        REGLENS_DATA_PROVIDER="fixture",
        REGLENS_DATABASE_PATH=tmp_path / "test.db",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/products/celsius-sparkling-orange/assets")
        product = client.get("/api/products/celsius-sparkling-orange")

    assert response.status_code == 200
    assets = response.json()["scraper_assets"]["nutrition_label_images"]
    assert len(assets) == 1
    assert assets[0]["purpose"] == "nutrition_label"
    assert "scraper_assets" not in product.json()["active_snapshot"]


def test_four_product_fixtures_keep_label_assets() -> None:
    """Fixture mode preserves the same asset contract as Bright Data mode."""
    fixture_provider = FixtureProductProvider(
        Path(__file__).parents[1] / "app" / "data" / "fixtures"
    )
    expected_assets = {
        "alani-nu-cotton-candy": 1,
        "bloom-raspberry-lemon": 1,
        "c4-frozen-bombsicle": 2,
        "celsius-sparkling-orange": 1,
    }

    for product_id, asset_count in expected_assets.items():
        result = fixture_provider.fetch(product_id)
        assert len(result.scraper_assets.nutrition_label_images) == asset_count


class StaticProvider(ProductDataProvider):
    """Test provider returning a complete result with separate asset metadata."""

    def __init__(self, snapshot: CanonicalProductSnapshot, assets: ScraperAssets) -> None:
        self.snapshot = snapshot
        self.assets = assets

    def fetch(self, _: str) -> CollectedProductResult:
        return CollectedProductResult(snapshot=self.snapshot, scraper_assets=self.assets)


class InvalidProvider(ProductDataProvider):
    """Test provider representing rejected asset or scraper metadata."""

    def fetch(self, _: str) -> CollectedProductResult:
        raise InvalidProductPayloadError("Nutrition-label image metadata is invalid.")


def _snapshot() -> CanonicalProductSnapshot:
    return CanonicalProductSnapshot.model_validate(
        {
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
                "scraped_at": "2026-08-23T00:00:00Z",
            },
        }
    )
