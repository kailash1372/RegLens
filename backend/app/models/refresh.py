"""Typed outcomes for product refresh operations."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.health import ScraperStatus
from app.models.product import ProductRecord


class ProductRefreshOutcome(BaseModel):
    """Describe whether a refresh was accepted or a cached snapshot was served."""

    product: ProductRecord
    accepted: bool
    served_cached: bool
    status: ScraperStatus
    error: str | None = None
