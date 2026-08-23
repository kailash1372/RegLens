"""Canonical contract and core endpoint coverage."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import Settings
from app.db.database import Database
from app.main import create_app
from app.models.product import CanonicalProductSnapshot, ProductRecord
from app.repositories.products import ProductRepository
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_canonical_schema_rejects_unexpected_fields() -> None:
    """Collector compatibility forbids accidental contract expansion."""
    payload = {
        "brand": "Example",
        "source": {
            "url": "https://example.com/product",
            "market": "US",
            "scraped_at": "2026-08-22T12:00:00Z",
        },
        "not_in_contract": "nope",
    }
    try:
        CanonicalProductSnapshot.model_validate(payload)
    except ValidationError as error:
        assert "not_in_contract" in str(error)
    else:
        raise AssertionError("Unexpected canonical fields must be rejected")


def test_canonical_schema_rejects_scraper_assets() -> None:
    """Transport metadata must remain outside the shared scraper snapshot contract."""
    payload = {
        "source": {
            "url": "https://example.com/product",
            "market": "US",
            "scraped_at": "2026-08-22T12:00:00Z",
        },
        "scraper_assets": {"nutrition_label_images": []},
    }

    with pytest.raises(ValidationError, match="scraper_assets"):
        CanonicalProductSnapshot.model_validate(payload)


def test_canonical_schema_normalizes_empty_text_items() -> None:
    """Parser extraction artifacts do not leak into domain arrays."""
    product = CanonicalProductSnapshot.model_validate(
        {
            "ingredients": [" caffeine ", "", "  "],
            "source": {
                "url": "https://example.com/product",
                "market": "US",
                "scraped_at": "2026-08-22T12:00:00Z",
            },
        }
    )
    assert product.ingredients == ["caffeine"]


def test_canonical_schema_normalizes_numeric_label_values() -> None:
    """Numeric strings from collector output become typed values without inference."""
    product = CanonicalProductSnapshot.model_validate(
        {
            "serving_size": {"value": "12", "unit": "fl oz", "ml": "355"},
            "caffeine_mg": "200",
            "nutrition_facts": [
                {
                    "name": "Sodium",
                    "value": "180",
                    "unit": "mg",
                    "daily_value_percent": "8",
                }
            ],
            "source": {
                "url": "https://example.com/product",
                "market": "US",
                "scraped_at": "2026-08-22T12:00:00Z",
            },
        }
    )
    assert product.serving_size.ml == 355
    assert product.caffeine_mg == 200
    assert product.nutrition_facts[0].daily_value_percent == 8


def test_product_catalog_endpoints_use_expanded_fixture_data(tmp_path: Path) -> None:
    """The expanded experience starts without Bright Data or an API key."""
    database = Database(tmp_path / "test.db")
    database.initialize()
    ProductRepository(database).upsert_product(
        ProductRecord(
            id="unsupported-product",
            display_name="Unsupported product",
            manufacturer="Example",
        )
    )
    settings = Settings(
        REGLENS_DATA_PROVIDER="fixture",
        REGLENS_DATABASE_PATH=database.path,
        BRIGHTDATA_COLLECTOR_CELSIUS="collector-celsius",
    )
    with TestClient(create_app(settings)) as client:
        catalog = client.get("/api/products")
        assert catalog.status_code == 200
        assert len(catalog.json()) == 14
        assert any(item["manufacturer"] == "Red Bull" for item in catalog.json())
        assert all(item["id"] != "unsupported-product" for item in catalog.json())
        passport = client.get("/api/products/celsius-sparkling-orange")
        assert passport.status_code == 200
        assert passport.json()["active_snapshot"]["caffeine_mg"] == 200
        assert passport.json()["market"] == "US"
        ingredients = client.get("/api/products/celsius-sparkling-orange/ingredients")
        assert ingredients.status_code == 200
        assert all("original_label_name" in item for item in ingredients.json())
        comparison = client.get(
            "/api/products/compare",
            params={"ids": "celsius-sparkling-orange,bloom-raspberry-lemon"},
        )
        assert comparison.status_code == 200
        assert len(comparison.json()) == 2
        red_bull = client.get("/api/products/red-bull-original")
        assert red_bull.status_code == 200
        assert red_bull.json()["active_snapshot"]["caffeine_mg"] == 80
        fanta_ca = client.get("/api/products/fanta-orange-ca").json()
        fanta_sa = client.get("/api/products/fanta-orange-sa").json()
        assert fanta_ca["canonical_family"] == fanta_sa["canonical_family"] == "fanta-orange"
        assert fanta_ca["market"] == "CA"
        assert fanta_sa["market"] == "SA"
        assert (
            fanta_ca["active_snapshot"]["ingredients"] != fanta_sa["active_snapshot"]["ingredients"]
        )
        categories = {item["category"] for item in catalog.json()}
        assert {"energy_drink", "soft_drink", "candy", "snack", "instant_noodles"} <= categories
        cross_market = client.get(
            "/api/products/compare",
            params={"ids": "fanta-orange-ca,fanta-orange-sa"},
        )
        assert cross_market.status_code == 200
        assert {item["market"] for item in cross_market.json()} == {"CA", "SA"}
        health = client.get("/api/scrapers/health")
        assert health.status_code == 200
        assert {item["status"] for item in health.json()} == {"Healthy"}
        celsius_health = next(
            item for item in health.json() if item["product_id"] == "celsius-sparkling-orange"
        )
        assert celsius_health["collector_id"] == "collector-celsius"
