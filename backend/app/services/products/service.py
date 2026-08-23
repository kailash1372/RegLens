"""Catalog seeding and safe snapshot refresh workflow."""

from __future__ import annotations

from collections.abc import Mapping

from app.models.health import ScraperStatus
from app.models.product import CanonicalProductSnapshot, ProductRecord
from app.models.refresh import ProductRefreshOutcome
from app.repositories.products import ProductRepository
from app.services.products.identity import catalog_identity_matches
from app.services.products.ingredients import normalize_ingredients
from app.services.products.providers import (
    InvalidProductPayloadError,
    ProductConfigurationError,
    ProductDataProvider,
    ProductProviderError,
)


class ProductService:
    """Coordinates provider validation and durable last-known-good data."""

    def __init__(
        self,
        repository: ProductRepository,
        provider: ProductDataProvider,
        *,
        catalog: Mapping[str, ProductRecord] | list[ProductRecord] | None = None,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.catalog = (
            {product.id: product for product in catalog}
            if isinstance(catalog, list)
            else dict(catalog or {})
        )

    def seed_catalog(
        self, products: list[ProductRecord], *, refresh_existing: bool = False
    ) -> None:
        """Ensure catalog identities exist and optionally refresh cached snapshots."""
        self.repository.prune_products({product.id for product in products})
        for product in products:
            self.repository.upsert_product(product.model_copy(update={"active_snapshot": None}))
            existing_product = self.repository.get_product(product.id)
            if (
                refresh_existing
                or existing_product is None
                or existing_product.active_snapshot is None
            ):
                self.refresh(product.id)

    def refresh(self, product_id: str) -> ProductRecord:
        """Persist only schema-valid data and retain prior snapshots on failure."""
        return self.refresh_with_outcome(product_id).product

    def refresh_with_outcome(self, product_id: str) -> ProductRefreshOutcome:
        """Refresh a product and report acceptance separately from cached fallback."""
        product = self.repository.get_product(product_id)
        if product is None:
            raise KeyError(product_id)
        collector_id = self.provider.collector_id_for(product_id)
        try:
            collected_result = self.provider.fetch(product_id)
        except ProductProviderError as error:
            status = (
                ScraperStatus.INVALID_OUTPUT
                if isinstance(error, InvalidProductPayloadError)
                else ScraperStatus.NOT_CONFIGURED
                if isinstance(error, ProductConfigurationError)
                else ScraperStatus.REFRESH_FAILED
            )
            self.repository.record_refresh_failure(
                product_id,
                str(error),
                invalid_output=status is ScraperStatus.INVALID_OUTPUT,
                collector_id=collector_id,
                status=status,
            )
            refreshed = self.repository.get_product(product_id)
            if refreshed is None:
                raise RuntimeError(
                    "Product disappeared while recording refresh failure."
                ) from error
            return ProductRefreshOutcome(
                product=refreshed,
                accepted=False,
                served_cached=refreshed.active_snapshot is not None,
                status=status,
                error=str(error),
            )
        try:
            self._validate_snapshot(product, collected_result.snapshot)
        except InvalidProductPayloadError as error:
            self.repository.record_refresh_failure(
                product_id,
                str(error),
                invalid_output=True,
                collector_id=collector_id,
            )
            refreshed = self.repository.get_product(product_id)
            if refreshed is None:
                raise RuntimeError("Product disappeared while rejecting invalid output.") from error
            return ProductRefreshOutcome(
                product=refreshed,
                accepted=False,
                served_cached=refreshed.active_snapshot is not None,
                status=ScraperStatus.INVALID_OUTPUT,
                error=str(error),
            )
        self.repository.save_valid_snapshot(
            product_id,
            collected_result.snapshot,
            scraper_assets=collected_result.scraper_assets,
            collector_id=collector_id,
            status=(
                ScraperStatus.FIXTURE_CACHED
                if self.provider.uses_fixture_data
                else ScraperStatus.HEALTHY
            ),
        )
        self.repository.replace_ingredients(
            product_id,
            normalize_ingredients(
                self.repository.database,
                collected_result.snapshot.ingredients,
            ),
        )
        refreshed = self.repository.get_product(product_id)
        if refreshed is None:
            raise RuntimeError("Product disappeared while saving a snapshot.")
        return ProductRefreshOutcome(
            product=refreshed,
            accepted=True,
            served_cached=False,
            status=(
                ScraperStatus.FIXTURE_CACHED
                if self.provider.uses_fixture_data
                else ScraperStatus.HEALTHY
            ),
        )

    def _validate_snapshot(
        self, product: ProductRecord, snapshot: CanonicalProductSnapshot
    ) -> None:
        """Enforce catalog identity and live provenance before persistence."""
        if not hasattr(snapshot, "source"):
            raise InvalidProductPayloadError("Collector output has no canonical source provenance.")
        expected_url = self.provider.product_url_for(product.id)
        if expected_url and str(snapshot.source.url) != expected_url:
            raise InvalidProductPayloadError(
                "Collector source URL does not match the configured official product URL."
            )
        if snapshot.source.market.casefold() != product.market.casefold():
            raise InvalidProductPayloadError(
                f"Collector market '{snapshot.source.market}' does not match catalog market "
                f"'{product.market}'."
            )
        expected_identity = self.catalog.get(product.id)
        if (
            expected_identity
            and not self.provider.uses_fixture_data
            and not catalog_identity_matches(expected_identity, snapshot)
        ):
            raise InvalidProductPayloadError(
                f"Collector identity does not match catalog product '{product.id}'."
            )
