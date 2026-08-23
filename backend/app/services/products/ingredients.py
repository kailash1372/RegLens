"""Conservative ingredient normalization with no guessed synonym relationships."""

from __future__ import annotations

import re

from app.db.database import Database
from app.models.ingredient import NormalizedIngredient


def normalize_ingredients(
    database: Database,
    label_names: list[str],
) -> list[NormalizedIngredient]:
    """Match exact names or VERIFIED aliases and leave everything else unmatched."""
    with database.connect() as connection:
        aliases = {
            row["normalized_alias"]: (row["entity_id"], row["preferred_name"])
            for row in connection.execute(
                """
                SELECT ia.normalized_alias, ia.entity_id, ie.preferred_name
                FROM ingredient_aliases ia
                JOIN ingredient_entities ie ON ie.id = ia.entity_id
                WHERE ia.verification_status = 'VERIFIED'
                """
            ).fetchall()
        }
        entities = {
            _normalized_key(row["preferred_name"]): (row["id"], row["preferred_name"])
            for row in connection.execute(
                "SELECT id, preferred_name FROM ingredient_entities"
            ).fetchall()
        }

    normalized: list[NormalizedIngredient] = []
    for label_name in label_names:
        key = _normalized_key(label_name)
        match = entities.get(key)
        match_type = "exact"
        if match is None:
            match = aliases.get(key)
            match_type = "verified_alias"
        normalized.append(
            NormalizedIngredient(
                original_label_name=label_name,
                canonical_ingredient_id=match[0] if match else None,
                canonical_name=match[1] if match else None,
                match_type=match_type if match else "unmatched",
            )
        )
    return normalized


def _normalized_key(value: str) -> str:
    """Normalize formatting only; do not infer chemical equivalence."""
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
