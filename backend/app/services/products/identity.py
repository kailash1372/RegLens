"""Catalog-to-collector identity checks shared by live trust boundaries."""

from __future__ import annotations

import re

from app.models.product import CanonicalProductSnapshot, ProductRecord

_IDENTITY_STOP_WORDS = {
    "and",
    "arabia",
    "bottle",
    "can",
    "canada",
    "fl",
    "india",
    "l",
    "ml",
    "oz",
    "saudi",
    "the",
    "us",
}


def catalog_identity_matches(
    product: ProductRecord,
    snapshot: CanonicalProductSnapshot,
) -> bool:
    """Require product-family and variant terms in collector-emitted identity fields."""
    actual: set[str] = set()
    for field in ("brand", "product_name", "product_line", "flavor"):
        actual.update(_identity_tokens(getattr(snapshot, field, None)))
    family = _identity_tokens(product.canonical_family)
    if not family or not family <= actual:
        return False
    return (_identity_tokens(product.display_name) - family) <= actual


def _identity_tokens(value: str | None) -> set[str]:
    """Tokenize identity labels while ignoring market and packaging qualifiers."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (value or "").replace("'", "").casefold())
        if token not in _IDENTITY_STOP_WORDS
    }
