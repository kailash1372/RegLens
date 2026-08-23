"""Canonical product-snapshot contract shared with Bright Data collectors."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ServingSize(BaseModel):
    """Serving amount as stated by the manufacturer."""

    value: float | None = Field(default=None, gt=0)
    unit: str | None = None
    ml: float | None = Field(default=None, gt=0)


class NutritionFact(BaseModel):
    """A single nutrition-label row."""

    name: str = Field(min_length=1)
    value: float | None = Field(default=None, ge=0)
    unit: str | None = None
    daily_value_percent: float | None = Field(default=None, ge=0)


class ProductSource(BaseModel):
    """Provenance embedded in every canonical collector output."""

    url: HttpUrl
    market: str = Field(min_length=1, max_length=80)
    scraped_at: datetime


class CanonicalProductSnapshot(BaseModel):
    """Stable scraper output contract; extra domain metadata belongs outside it."""

    model_config = ConfigDict(extra="forbid")

    brand: str | None = None
    product_name: str | None = None
    product_line: str | None = None
    flavor: str | None = None
    serving_size: ServingSize = Field(default_factory=ServingSize)
    caffeine_mg: float | None = Field(default=None, ge=0)
    calories: float | None = Field(default=None, ge=0)
    sugar_g: float | None = Field(default=None, ge=0)
    nutrition_facts: list[NutritionFact] = Field(default_factory=list)
    ingredients: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    source: ProductSource

    @property
    def caffeine_basis_available(self) -> bool:
        """Return whether a numeric caffeine value has a stated serving basis."""
        return self.caffeine_mg is None or (
            self.serving_size.value is not None and bool(self.serving_size.unit)
        )

    @field_validator("ingredients", "warnings", "claims")
    @classmethod
    def remove_empty_text(cls, values: list[str]) -> list[str]:
        """Keep source text intact while dropping empty extraction artifacts."""
        return [value.strip() for value in values if value and value.strip()]


ProductCategory = Literal["energy_drink", "soft_drink", "candy", "snack", "instant_noodles"]


class ProductRecord(BaseModel):
    """Product identity managed by RegLens, separate from scraped facts."""

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    display_name: str
    category: ProductCategory = "energy_drink"
    manufacturer: str
    canonical_family: str | None = None
    market: str = Field(default="US", min_length=2, max_length=80)
    active_snapshot: CanonicalProductSnapshot | None = None


class ProductSummary(BaseModel):
    """Catalog card representation."""

    id: str
    display_name: str
    manufacturer: str
    category: ProductCategory
    canonical_family: str | None = None
    market: str
    caffeine_mg: float | None = None
    sugar_g: float | None = None
    refreshed_at: datetime | None = None
