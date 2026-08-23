"""Product-data providers with fixture and Bright Data implementations."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any

import httpx
from pydantic import ValidationError

from app.models.product import CanonicalProductSnapshot
from app.models.scraper import CollectedProductResult, ScraperAssets


class ProductProviderError(RuntimeError):
    """A recoverable source-provider failure that must retain cached data."""


class InvalidProductPayloadError(ProductProviderError):
    """An upstream response that cannot satisfy the canonical scraper contract."""


class ProductDataProvider(ABC):
    """Fetch canonical data for a known RegLens product identifier."""

    @abstractmethod
    def fetch(self, product_id: str) -> CollectedProductResult:
        """Fetch canonical product facts and separately validated scraper assets."""

    def collector_id_for(self, product_id: str) -> str | None:
        """Return the configured non-secret collector ID, when the provider has one."""
        del product_id
        return None


class FixtureProductProvider(ProductDataProvider):
    """Validated fixtures make the MVP runnable with no external dependencies."""

    def __init__(
        self,
        fixture_directory: Path,
        collector_ids: Mapping[str, str] | None = None,
    ) -> None:
        self.fixture_directory = fixture_directory
        self.collector_ids = dict(collector_ids or {})

    def fetch(self, product_id: str) -> CollectedProductResult:
        """Read one fixture without silently fabricating a missing product."""
        fixture_path = self.fixture_directory / f"{product_id}.json"
        if not fixture_path.is_file():
            raise ProductProviderError(f"No fixture exists for product '{product_id}'.")
        try:
            payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise InvalidProductPayloadError(
                f"Fixture '{fixture_path.name}' is invalid JSON."
            ) from error
        try:
            if not isinstance(payload, dict):
                raise InvalidProductPayloadError(
                    f"Fixture '{fixture_path.name}' must contain a JSON object."
                )
            canonical_payload = {
                key: value for key, value in payload.items() if key != "scraper_assets"
            }
            snapshot = CanonicalProductSnapshot.model_validate(canonical_payload)
            assets = ScraperAssets.model_validate(payload.get("scraper_assets", {}))
            return CollectedProductResult(snapshot=snapshot, scraper_assets=assets)
        except ValidationError as error:
            raise InvalidProductPayloadError(
                f"Fixture '{fixture_path.name}' violates the canonical schema."
            ) from error

    def collector_id_for(self, product_id: str) -> str | None:
        """Expose the live collector mapped to a cached fixture snapshot."""
        return self.collector_ids.get(product_id)


class BrightDataProductProvider(ProductDataProvider):
    """Trigger, poll, normalize, and validate Bright Data collector output."""

    def __init__(
        self,
        *,
        api_token: str | None,
        base_url: str,
        collector_ids: Mapping[str, str],
        product_urls: Mapping[str, str],
        trigger_path: str = "/dca/trigger",
        poll_path: str = "/dca/dataset",
        output_path: str = "/dca/dataset",
        poll_interval_seconds: float = 2.0,
        max_poll_attempts: int = 20,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self.api_token = api_token
        self.base_url = base_url.rstrip("/")
        self.collector_ids = dict(collector_ids)
        self.product_urls = dict(product_urls)
        self.trigger_path = trigger_path
        self.poll_path = poll_path
        self.output_path = output_path
        self.poll_interval_seconds = poll_interval_seconds
        self.max_poll_attempts = max_poll_attempts
        self.client = client or httpx.Client(timeout=httpx.Timeout(30.0))
        self.sleeper = sleeper

    def fetch(self, product_id: str) -> CollectedProductResult:
        """Collect one product and validate output before the service persists it."""
        collector_id, product_url = self._configuration_for(product_id)
        collection_id = self._trigger(collector_id, product_url)
        poll_response = self._poll(collection_id)
        output_response = (
            poll_response
            if self.output_path == self.poll_path
            else self._request_json("GET", self.output_path, params={"id": collection_id})
        )
        raw_product = _extract_product_payload(output_response)
        normalized = _normalize_canonical_payload(raw_product, product_url)
        try:
            snapshot = CanonicalProductSnapshot.model_validate(normalized)
            _validate_live_identity(snapshot, product_url)
            assets_payload = raw_product.get("scraper_assets", {})
            return CollectedProductResult(
                snapshot=snapshot,
                scraper_assets=ScraperAssets.model_validate(assets_payload),
            )
        except ValidationError as error:
            raise InvalidProductPayloadError(
                "Bright Data output violates the canonical product schema."
            ) from error

    def collector_id_for(self, product_id: str) -> str | None:
        """Expose configured collector identity for source-health diagnostics."""
        return self.collector_ids.get(product_id)

    def _configuration_for(self, product_id: str) -> tuple[str, str]:
        """Validate all local configuration before making a network request."""
        if not self.api_token:
            raise ProductProviderError("Bright Data API token is not configured.")
        collector_id = self.collector_ids.get(product_id)
        if not collector_id:
            raise ProductProviderError(
                f"Bright Data collector is not configured for '{product_id}'."
            )
        product_url = self.product_urls.get(product_id)
        if not product_url:
            raise ProductProviderError(
                f"Official product URL is not configured for '{product_id}'."
            )
        return collector_id, product_url

    def _trigger(self, collector_id: str, product_url: str) -> str:
        """Start asynchronous collection and return Bright Data's collection ID."""
        response = self._request_json(
            "POST",
            self.trigger_path,
            params={"collector": collector_id, "queue_next": "1"},
            payload=[{"url": product_url}],
        )
        collection_id = _find_collection_id(response)
        if not collection_id:
            raise InvalidProductPayloadError("Bright Data trigger response has no collection_id.")
        return collection_id

    def _poll(self, collection_id: str) -> object:
        """Poll the configured collection endpoint until output is available."""
        last_response: object | None = None
        for attempt in range(self.max_poll_attempts):
            response = self._request_json("GET", self.poll_path, params={"id": collection_id})
            last_response = response
            if _response_is_ready(response):
                return response
            if self.output_path != self.poll_path and _response_is_completed(response):
                return response
            if attempt < self.max_poll_attempts - 1:
                self.sleeper(self.poll_interval_seconds)
        raise ProductProviderError(
            f"Bright Data collection '{collection_id}' did not complete after "
            f"{self.max_poll_attempts} poll attempts; last response type was "
            f"{type(last_response).__name__}."
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        payload: object | None = None,
    ) -> object:
        """Request JSON without leaking bearer credentials in raised errors."""
        try:
            response = self.client.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self.api_token}"},
                params=params,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as error:
            raise ProductProviderError(
                f"Bright Data request to '{path}' failed: {error.__class__.__name__}."
            ) from error
        except json.JSONDecodeError as error:
            raise InvalidProductPayloadError(
                f"Bright Data response from '{path}' was not valid JSON."
            ) from error


def _find_collection_id(response: object) -> str | None:
    """Read a collection ID from direct or nested Bright Data trigger wrappers."""
    if not isinstance(response, dict):
        return None
    direct = response.get("collection_id") or response.get("id")
    if isinstance(direct, str) and direct:
        return direct
    for key in ("data", "result", "collection"):
        nested = response.get(key)
        found = _find_collection_id(nested)
        if found:
            return found
    return None


def _response_is_ready(response: object) -> bool:
    """Treat direct lists and successful output wrappers as completed collections."""
    if isinstance(response, list):
        return True
    if not isinstance(response, dict):
        return False
    status = response.get("status") or response.get("state")
    if isinstance(status, str) and status.lower() in {"failed", "error", "cancelled"}:
        raise ProductProviderError(f"Bright Data collection ended with status '{status}'.")
    if isinstance(status, str) and status.lower() in {"running", "queued", "pending"}:
        return False
    return any(key in response for key in ("data", "output", "items", "results"))


def _response_is_completed(response: object) -> bool:
    """Recognize a terminal status when output is fetched from another endpoint."""
    if not isinstance(response, dict):
        return False
    status = response.get("status") or response.get("state")
    return isinstance(status, str) and status.lower() in {"completed", "complete", "success"}


def _extract_product_payload(response: object) -> Mapping[str, Any]:
    """Unwrap common collector/dataset envelopes and require exactly one product."""
    candidate = _unwrap_response(response)
    if isinstance(candidate, dict) and isinstance(candidate.get("output"), dict):
        candidate = candidate["output"]
    if not isinstance(candidate, list):
        raise InvalidProductPayloadError("Bright Data output did not contain a product list.")
    if len(candidate) != 1 or not isinstance(candidate[0], dict):
        raise InvalidProductPayloadError(
            "Bright Data output must contain exactly one product object."
        )
    item = candidate[0]
    nested = item.get("output") or item.get("data")
    return nested if isinstance(nested, dict) else item


def _unwrap_response(response: object) -> object:
    """Unwrap one-level response envelopes without mistaking canonical fields for wrappers."""
    if not isinstance(response, dict):
        return response
    for key in ("data", "output", "items", "results"):
        value = response.get(key)
        if isinstance(value, (list, dict)):
            return value
    return response


def _normalize_canonical_payload(payload: Mapping[str, Any], product_url: str) -> dict[str, Any]:
    """Fill canonical null/default shapes and safely derive only source provenance."""
    canonical_fields = {
        "brand",
        "product_name",
        "product_line",
        "flavor",
        "serving_size",
        "caffeine_mg",
        "calories",
        "sugar_g",
        "nutrition_facts",
        "ingredients",
        "warnings",
        "claims",
        "source",
    }
    normalized = {key: value for key, value in payload.items() if key in canonical_fields}
    scalar_fields = (
        "brand",
        "product_name",
        "product_line",
        "flavor",
        "caffeine_mg",
        "calories",
        "sugar_g",
    )
    for field in scalar_fields:
        normalized.setdefault(field, None)
    for field in ("nutrition_facts", "ingredients", "warnings", "claims"):
        normalized.setdefault(field, [])
    serving_size = normalized.get("serving_size")
    normalized["serving_size"] = serving_size if isinstance(serving_size, dict) else {}
    for field in ("value", "unit", "ml"):
        normalized["serving_size"].setdefault(field, None)
    source = normalized.get("source")
    normalized["source"] = source if isinstance(source, dict) else {}
    normalized["source"].setdefault("url", product_url)
    normalized["source"].setdefault("market", "US")
    normalized["source"].setdefault("scraped_at", datetime.now(UTC).isoformat())
    return normalized


def _validate_live_identity(
    snapshot: CanonicalProductSnapshot,
    expected_url: str,
) -> None:
    """Reject structurally valid output that did not identify the requested product."""
    if not snapshot.product_name or not snapshot.product_name.strip():
        raise InvalidProductPayloadError(
            "Bright Data output has no product_name and cannot establish variant identity."
        )
    actual_url = httpx.URL(str(snapshot.source.url))
    configured_url = httpx.URL(expected_url)
    if actual_url != configured_url:
        raise InvalidProductPayloadError(
            "Bright Data output source URL does not match the configured official product URL."
        )
