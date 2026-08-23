"""Cautious matching of official recall records to catalog products."""

from __future__ import annotations

import re

from app.models.product import ProductRecord
from app.models.regulatory import RecallMatchType, RecallRecord

_STOP_WORDS = {"and", "drink", "energy", "the", "with", "of"}


def _tokens(value: str | None) -> set[str]:
    """Normalize words while retaining enough identity to avoid collisions."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (value or "").lower())
        if len(token) > 2 and token not in _STOP_WORDS
    }


def classify_recall_match(product: ProductRecord, recall: RecallRecord) -> RecallMatchType:
    """Classify exact SKU/family/brand evidence without guessing from a brand alone."""
    snapshot = product.active_snapshot
    description = _tokens(recall.product_description)
    brand_tokens = _tokens(recall.brand_manufacturer)
    product_brand = _tokens(product.manufacturer) | _tokens(snapshot.brand if snapshot else None)
    if not product_brand or not description.intersection(product_brand):
        return RecallMatchType.NO_MATCH

    name_tokens = _tokens(
        " ".join(
            value
            for value in (
                product.display_name,
                snapshot.product_name if snapshot else None,
                snapshot.flavor if snapshot else None,
            )
            if value
        )
    )
    family_tokens = _tokens(
        " ".join(
            value
            for value in (
                product.display_name,
                snapshot.product_line if snapshot else None,
            )
            if value
        )
    )
    if brand_tokens and not brand_tokens.intersection(product_brand):
        return RecallMatchType.NO_MATCH
    if name_tokens and name_tokens.issubset(description):
        return RecallMatchType.EXACT_PRODUCT
    if family_tokens and len(family_tokens.intersection(description)) >= 2:
        return RecallMatchType.PRODUCT_FAMILY
    if description.intersection(product_brand):
        return RecallMatchType.BRAND
    return RecallMatchType.NO_MATCH


def attach_match(product: ProductRecord, recall: RecallRecord) -> RecallRecord:
    """Return a copy annotated with the conservative match classification."""
    match = classify_recall_match(product, recall)
    return recall.model_copy(
        update={
            "match_type": match,
            "matched_product_id": product.id if match is not RecallMatchType.NO_MATCH else None,
        }
    )
