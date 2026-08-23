"""Ingredient entities preserve label text while enabling reviewed alias matches."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class NormalizedIngredient(BaseModel):
    """One manufacturer label ingredient and its optional canonical entity."""

    original_label_name: str
    canonical_ingredient_id: str | None = None
    canonical_name: str | None = None
    match_type: Literal["exact", "verified_alias", "unmatched"] = "unmatched"
