"""Scraper-health API models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ScraperStatus(StrEnum):
    """Visible status for data-source reliability."""

    HEALTHY = "Healthy"
    STALE = "Stale"
    INVALID_OUTPUT = "Invalid output"
    REFRESH_FAILED = "Refresh failed"
    NOT_CONFIGURED = "Not configured"


class ScraperHealth(BaseModel):
    """Current health and the last error without exposing credentials."""

    product_id: str
    source_url: str | None = None
    collector_id: str | None = None
    status: ScraperStatus
    schema_valid: bool | None = None
    last_successful_refresh: datetime | None = None
    last_error: str | None = None
