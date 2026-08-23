"""Product, immutable snapshot, and scraper-health persistence."""

from __future__ import annotations

import json
from datetime import datetime

from app.db.database import Database
from app.models.health import ScraperHealth, ScraperStatus
from app.models.ingredient import NormalizedIngredient
from app.models.product import CanonicalProductSnapshot, ProductRecord, ProductSummary
from app.models.scraper import ProductScraperAssets, ScraperAssets


class ProductRepository:
    """Repository keeping a last-known-good snapshot on every product."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_product(self, product: ProductRecord) -> None:
        """Create or update catalog identity without modifying snapshot history."""
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO products(
                    id, display_name, manufacturer, category, canonical_family, market
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name = excluded.display_name,
                    manufacturer = excluded.manufacturer,
                    category = excluded.category,
                    canonical_family = excluded.canonical_family,
                    market = excluded.market
                """,
                (
                    product.id,
                    product.display_name,
                    product.manufacturer,
                    product.category,
                    product.canonical_family,
                    product.market,
                ),
            )

    def prune_products(self, product_ids: set[str]) -> None:
        """Remove identities no longer present in the configured MVP catalog."""
        if not product_ids:
            raise ValueError("At least one supported product is required.")
        placeholders = ", ".join("?" for _ in product_ids)
        args = tuple(sorted(product_ids))
        with self.database.connect() as connection:
            for table in (
                "regulatory_findings",
                "product_ingredients",
                "product_scraper_assets",
                "scraper_health",
                "product_snapshots",
            ):
                connection.execute(
                    f"DELETE FROM {table} WHERE product_id NOT IN ({placeholders})", args
                )
            connection.execute(
                f"DELETE FROM recalls WHERE matched_product_id NOT IN ({placeholders})", args
            )
            connection.execute(f"DELETE FROM products WHERE id NOT IN ({placeholders})", args)

    def save_valid_snapshot(
        self,
        product_id: str,
        snapshot: CanonicalProductSnapshot,
        *,
        scraper_assets: ScraperAssets | None = None,
        collector_id: str | None = None,
    ) -> None:
        """Append a schema-valid snapshot; never overwrite prior successful data."""
        payload = snapshot.model_dump(mode="json")
        with self.database.connect() as connection:
            connection.execute(
                (
                    "INSERT INTO product_snapshots(product_id, payload_json, scraped_at) "
                    "VALUES (?, ?, ?)"
                ),
                (product_id, json.dumps(payload), snapshot.source.scraped_at.isoformat()),
            )
            connection.execute(
                """
                INSERT INTO scraper_health(
                    product_id, source_url, collector_id, status, schema_valid,
                    last_successful_refresh, last_error
                )
                VALUES (?, ?, ?, ?, 1, ?, NULL)
                ON CONFLICT(product_id) DO UPDATE SET
                    source_url = excluded.source_url,
                    collector_id = COALESCE(excluded.collector_id, scraper_health.collector_id),
                    status = excluded.status,
                    schema_valid = 1,
                    last_successful_refresh = excluded.last_successful_refresh,
                    last_error = NULL
                """,
                (
                    product_id,
                    str(snapshot.source.url),
                    collector_id,
                    ScraperStatus.HEALTHY.value,
                    snapshot.source.scraped_at.isoformat(),
                ),
            )
            assets = scraper_assets or ScraperAssets()
            connection.execute(
                """
                INSERT INTO product_scraper_assets(product_id, assets_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    assets_json = excluded.assets_json,
                    updated_at = excluded.updated_at
                """,
                (
                    product_id,
                    assets.model_dump_json(),
                    snapshot.source.scraped_at.isoformat(),
                ),
            )

    def record_refresh_failure(
        self,
        product_id: str,
        error: str,
        invalid_output: bool = False,
        collector_id: str | None = None,
    ) -> None:
        """Expose a failed refresh while deliberately retaining the active snapshot."""
        status = ScraperStatus.INVALID_OUTPUT if invalid_output else ScraperStatus.REFRESH_FAILED
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO scraper_health(
                    product_id, collector_id, status, schema_valid, last_error
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    collector_id = COALESCE(excluded.collector_id, scraper_health.collector_id),
                    status = excluded.status,
                    schema_valid = excluded.schema_valid,
                    last_error = excluded.last_error
                """,
                (
                    product_id,
                    collector_id,
                    status.value,
                    0 if invalid_output else None,
                    error[:500],
                ),
            )

    def list_products(self) -> list[ProductSummary]:
        """Return catalog cards with facts from their latest valid snapshots."""
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT p.*, s.payload_json, s.scraped_at
                FROM products p
                LEFT JOIN product_snapshots s ON s.id = (
                    SELECT id FROM product_snapshots
                    WHERE product_id = p.id
                    ORDER BY id DESC LIMIT 1
                )
                ORDER BY p.display_name
                """
            ).fetchall()
        summaries: list[ProductSummary] = []
        for row in rows:
            payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
            summaries.append(
                ProductSummary(
                    id=row["id"],
                    display_name=row["display_name"],
                    manufacturer=row["manufacturer"],
                    category=row["category"],
                    canonical_family=row["canonical_family"],
                    market=row["market"],
                    caffeine_mg=payload.get("caffeine_mg"),
                    sugar_g=payload.get("sugar_g"),
                    refreshed_at=datetime.fromisoformat(row["scraped_at"])
                    if row["scraped_at"]
                    else None,
                )
            )
        return summaries

    def get_product(self, product_id: str) -> ProductRecord | None:
        """Return product identity plus its last valid canonical snapshot."""
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT p.*, s.payload_json
                FROM products p
                LEFT JOIN product_snapshots s ON s.id = (
                    SELECT id FROM product_snapshots
                    WHERE product_id = p.id
                    ORDER BY id DESC LIMIT 1
                )
                WHERE p.id = ?
                """,
                (product_id,),
            ).fetchone()
        if row is None:
            return None
        snapshot = (
            CanonicalProductSnapshot.model_validate(json.loads(row["payload_json"]))
            if row["payload_json"]
            else None
        )
        return ProductRecord(
            id=row["id"],
            display_name=row["display_name"],
            manufacturer=row["manufacturer"],
            category=row["category"],
            canonical_family=row["canonical_family"],
            market=row["market"],
            active_snapshot=snapshot,
        )

    def replace_ingredients(
        self,
        product_id: str,
        ingredients: list[NormalizedIngredient],
    ) -> None:
        """Replace the active ingredient index while preserving original label names."""
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM product_ingredients WHERE product_id = ?", (product_id,)
            )
            connection.executemany(
                """
                INSERT INTO product_ingredients(
                    product_id, ordinal, original_label_name,
                    canonical_ingredient_id, match_type
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        product_id,
                        ordinal,
                        ingredient.original_label_name,
                        ingredient.canonical_ingredient_id,
                        ingredient.match_type,
                    )
                    for ordinal, ingredient in enumerate(ingredients)
                ],
            )

    def list_ingredients(self, product_id: str) -> list[NormalizedIngredient]:
        """Return original labels with canonical matches when explicitly available."""
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT pi.original_label_name, pi.canonical_ingredient_id,
                       pi.match_type, ie.preferred_name AS canonical_name
                FROM product_ingredients pi
                LEFT JOIN ingredient_entities ie
                    ON ie.id = pi.canonical_ingredient_id
                WHERE pi.product_id = ?
                ORDER BY pi.ordinal
                """,
                (product_id,),
            ).fetchall()
        return [NormalizedIngredient.model_validate(dict(row)) for row in rows]

    def get_scraper_assets(self, product_id: str) -> ProductScraperAssets | None:
        """Return accepted transport metadata without altering canonical product facts."""
        with self.database.connect() as connection:
            product = connection.execute(
                "SELECT id FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            if product is None:
                return None
            row = connection.execute(
                """
                SELECT assets_json, updated_at
                FROM product_scraper_assets
                WHERE product_id = ?
                """,
                (product_id,),
            ).fetchone()
        if row is None:
            return ProductScraperAssets(product_id=product_id)
        return ProductScraperAssets(
            product_id=product_id,
            scraper_assets=ScraperAssets.model_validate_json(row["assets_json"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_health(self) -> list[ScraperHealth]:
        """List one current health state per catalog product."""
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT p.id AS product_id, h.source_url, h.collector_id, h.status,
                       h.schema_valid, h.last_successful_refresh, h.last_error
                FROM products p LEFT JOIN scraper_health h ON h.product_id = p.id
                ORDER BY p.display_name
                """
            ).fetchall()
        return [
            ScraperHealth(
                product_id=row["product_id"],
                source_url=row["source_url"],
                collector_id=row["collector_id"],
                status=row["status"] or ScraperStatus.NOT_CONFIGURED,
                schema_valid=bool(row["schema_valid"]) if row["schema_valid"] is not None else None,
                last_successful_refresh=datetime.fromisoformat(row["last_successful_refresh"])
                if row["last_successful_refresh"]
                else None,
                last_error=row["last_error"],
            )
            for row in rows
        ]
