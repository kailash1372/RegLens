"""Official openFDA food-enforcement adapter with normalized output."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import httpx

from app.models.product import ProductRecord
from app.models.regulatory import RecallRecord

OPENFDA_FOOD_ENFORCEMENT_URL = "https://api.fda.gov/food/enforcement.json"


class OpenFdaClient:
    """Fetch official food enforcement records; matching is a separate concern."""

    def __init__(self, *, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def fetch_for_product(self, product: ProductRecord, limit: int = 25) -> list[RecallRecord]:
        """Search by manufacturer first, leaving exact entity resolution to the matcher."""
        params = {
            "search": f'recalling_firm:"{product.manufacturer}"',
            "limit": str(limit),
        }
        retrieved_at = datetime.now(UTC)
        try:
            response = httpx.get(OPENFDA_FOOD_ENFORCEMENT_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError(f"openFDA request failed: {error}") from error
        return [self._normalize(item, retrieved_at) for item in payload.get("results", [])]

    @staticmethod
    def _normalize(item: dict[str, object], retrieved_at: datetime) -> RecallRecord:
        """Map openFDA's stable enforcement fields to the internal recall contract."""
        description = str(item.get("product_description") or "").strip()
        firm = str(item.get("recalling_firm") or "").strip() or None
        event_date = _parse_date(item.get("recall_initiation_date") or item.get("report_date"))
        source_url = f"{OPENFDA_FOOD_ENFORCEMENT_URL}?search=event_id:{item.get('event_id', '')}"
        identity = str(item.get("event_id") or f"{firm}|{description}|{event_date}")
        return RecallRecord(
            id="openfda-" + sha256(identity.encode()).hexdigest()[:20],
            authority="U.S. Food and Drug Administration",
            jurisdiction="US",
            product_description=description,
            brand_manufacturer=firm,
            reason=str(item.get("reason_for_recall") or "Not specified by source"),
            classification_status=str(item.get("classification") or item.get("status") or "")
            or None,
            event_date=event_date,
            source_url=source_url,
            retrieved_at=retrieved_at,
        )


def _parse_date(value: object) -> datetime | None:
    """Parse openFDA's YYYYMMDD date without rejecting a record for a missing date."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y%m%d").replace(tzinfo=UTC)
    except ValueError:
        return None
