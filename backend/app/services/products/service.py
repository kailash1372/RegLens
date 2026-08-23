"""Catalog seeding and safe snapshot refresh workflow."""

from __future__ import annotations

from app.models.product import ProductRecord
from app.repositories.products import ProductRepository
from app.services.products.ingredients import normalize_ingredients
from app.services.products.providers import (
    InvalidProductPayloadError,
    ProductDataProvider,
    ProductProviderError,
)


class ProductService:
    """Coordinates provider validation and durable last-known-good data."""

    def __init__(self, repository: ProductRepository, provider: ProductDataProvider) -> None:
        self.repository = repository
        self.provider = provider

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
        product = self.repository.get_product(product_id)
        if product is None:
            raise KeyError(product_id)
        collector_id = self.provider.collector_id_for(product_id)
        try:
            collected_result = self.provider.fetch(product_id)
        except ProductProviderError as error:
            self.repository.record_refresh_failure(
                product_id,
                str(error),
                invalid_output=isinstance(error, InvalidProductPayloadError),
                collector_id=collector_id,
            )
            refreshed = self.repository.get_product(product_id)
            if refreshed is None:
                raise RuntimeError(
                    "Product disappeared while recording refresh failure."
                ) from error
            return refreshed
        if collected_result.snapshot.source.market.casefold() != product.market.casefold():
            self.repository.record_refresh_failure(
                product_id,
                (
                    f"Collector market '{collected_result.snapshot.source.market}' does not "
                    f"match catalog market '{product.market}'."
                ),
                invalid_output=True,
                collector_id=collector_id,
            )
            refreshed = self.repository.get_product(product_id)
            if refreshed is None:
                raise RuntimeError("Product disappeared while rejecting a market mismatch.")
            return refreshed
        self.repository.save_valid_snapshot(
            product_id,
            collected_result.snapshot,
            scraper_assets=collected_result.scraper_assets,
            collector_id=collector_id,
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
        return refreshed
