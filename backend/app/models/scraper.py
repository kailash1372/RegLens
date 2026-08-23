"""Transport-only scraper metadata that is deliberately outside canonical facts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.models.product import CanonicalProductSnapshot


class NutritionLabelImage(BaseModel):
    """A first-party nutrition-label image emitted by a product collector."""

    model_config = ConfigDict(extra="forbid", strict=True)

    url: HttpUrl
    content_type: Literal["image"]
    purpose: Literal["nutrition_label"]


class ScraperAssets(BaseModel):
    """Validated collector asset metadata kept outside the shared snapshot contract."""

    model_config = ConfigDict(extra="forbid", strict=True)

    nutrition_label_images: list[NutritionLabelImage] = Field(default_factory=list)


class CollectedProductResult(BaseModel):
    """A canonical snapshot and its separately persisted scraper transport metadata."""

    model_config = ConfigDict(extra="forbid")

    snapshot: CanonicalProductSnapshot
    scraper_assets: ScraperAssets = Field(default_factory=ScraperAssets)

    @model_validator(mode="after")
    def require_first_party_assets(self) -> CollectedProductResult:
        """Reject asset URLs outside the manufacturer source's registered domain."""
        source_url = str(self.snapshot.source.url)
        for image in self.scraper_assets.nutrition_label_images:
            is_first_party = _same_registered_domain(source_url, str(image.url))
            if image.url.scheme != "https" or not is_first_party:
                raise ValueError(
                    "Nutrition-label image URLs must be HTTPS and first-party "
                    "to the product source."
                )
        return self


class ProductScraperAssets(BaseModel):
    """Latest accepted asset set for an individual product."""

    product_id: str
    scraper_assets: ScraperAssets = Field(default_factory=ScraperAssets)
    updated_at: datetime | None = None


def _same_registered_domain(left_url: str, right_url: str) -> bool:
    """Compare registrable-domain approximations without making a network request."""
    left_host = urlparse(left_url).hostname
    right_host = urlparse(right_url).hostname
    if not left_host or not right_host:
        return False
    return _registered_domain(left_host) == _registered_domain(right_host)


def _registered_domain(hostname: str) -> str:
    """Return a conservative two-label domain approximation for first-party checks."""
    parts = hostname.lower().rstrip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else hostname.lower()
