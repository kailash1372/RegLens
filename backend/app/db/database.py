"""Small SQLite database wrapper and idempotent schema initialization."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    manufacturer TEXT NOT NULL,
    category TEXT NOT NULL,
    canonical_family TEXT,
    market TEXT NOT NULL DEFAULT 'US'
);
CREATE TABLE IF NOT EXISTS product_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL REFERENCES products(id),
    payload_json TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_snapshots_product_created
ON product_snapshots(product_id, id DESC);
CREATE TABLE IF NOT EXISTS scraper_health (
    product_id TEXT PRIMARY KEY REFERENCES products(id),
    source_url TEXT,
    collector_id TEXT,
    status TEXT NOT NULL,
    schema_valid INTEGER,
    last_successful_refresh TEXT,
    last_error TEXT
);
CREATE TABLE IF NOT EXISTS product_scraper_assets (
    product_id TEXT PRIMARY KEY REFERENCES products(id),
    assets_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ingredient_entities (
    id TEXT PRIMARY KEY,
    preferred_name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ingredient_aliases (
    normalized_alias TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES ingredient_entities(id),
    verification_status TEXT NOT NULL,
    authority_source_id TEXT
);
CREATE TABLE IF NOT EXISTS product_ingredients (
    product_id TEXT NOT NULL REFERENCES products(id),
    ordinal INTEGER NOT NULL,
    original_label_name TEXT NOT NULL,
    canonical_ingredient_id TEXT REFERENCES ingredient_entities(id),
    match_type TEXT NOT NULL,
    PRIMARY KEY(product_id, ordinal)
);
CREATE TABLE IF NOT EXISTS regulatory_sources (
    id TEXT PRIMARY KEY,
    authority TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    retrieved_at TEXT NOT NULL,
    source_type TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'current',
    last_error TEXT,
    evidence_text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS regulatory_rules (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES regulatory_sources(id),
    jurisdiction TEXT NOT NULL,
    authority TEXT NOT NULL,
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    comparator TEXT NOT NULL,
    threshold REAL,
    unit TEXT,
    affected_population TEXT,
    applicability_notes TEXT NOT NULL,
    effective_from TEXT,
    effective_until TEXT,
    verification_status TEXT NOT NULL,
    evidence_excerpt TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_regulatory_rules_subject ON regulatory_rules(subject);
CREATE TABLE IF NOT EXISTS regulatory_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL REFERENCES products(id),
    rule_id TEXT NOT NULL REFERENCES regulatory_rules(id),
    finding_type TEXT NOT NULL,
    observed_value REAL NOT NULL,
    threshold_value REAL NOT NULL,
    difference REAL NOT NULL,
    unit TEXT NOT NULL,
    status TEXT NOT NULL,
    explanation_template TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    UNIQUE(product_id, rule_id)
);
CREATE TABLE IF NOT EXISTS recalls (
    id TEXT PRIMARY KEY,
    authority TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    product_description TEXT NOT NULL,
    brand_manufacturer TEXT,
    reason TEXT NOT NULL,
    classification_status TEXT,
    event_date TEXT,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    match_type TEXT,
    matched_product_id TEXT REFERENCES products(id)
);
CREATE INDEX IF NOT EXISTS idx_recalls_product ON recalls(matched_product_id);
CREATE VIRTUAL TABLE IF NOT EXISTS regulatory_evidence_fts USING fts5(
    source_id UNINDEXED,
    title,
    authority,
    jurisdiction UNINDEXED,
    evidence_text
);
"""


class Database:
    """Connection factory for the intentionally lightweight local SQLite store."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a row-oriented connection and commit successful mutations."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create the schema without destructive migrations."""
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(regulatory_sources)").fetchall()
            }
            migrations = {
                "content": "TEXT NOT NULL DEFAULT ''",
                "status": "TEXT NOT NULL DEFAULT 'current'",
                "last_error": "TEXT",
            }
            for name, declaration in migrations.items():
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE regulatory_sources ADD COLUMN {name} {declaration}"
                    )
            product_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(products)").fetchall()
            }
            product_migrations = {
                "canonical_family": "TEXT",
                "market": "TEXT NOT NULL DEFAULT 'US'",
            }
            for name, declaration in product_migrations.items():
                if name not in product_columns:
                    connection.execute(f"ALTER TABLE products ADD COLUMN {name} {declaration}")
