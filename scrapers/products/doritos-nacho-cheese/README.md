# DORITOS Nacho Cheese Flavored Tortilla Chips (US)

- Official source: https://www.doritos.com/products/doritos-nacho-cheese-flavored-tortilla-chips
- Market: `US`
- Variant identity: the parser requires the authoritative product name to
  contain `Nacho Cheese Flavored Tortilla Chips`; related DORITOS products are
  rejected.

The manufacturer page embeds SmartLabel at
`https://smtlbl.app/upc/028400516464?stylekey=doritos-10`. The iframe redirects
to the current product-version resource and exposes separate nutrition and
ingredient views. The parser reads those views when Bright Data exposes the
rendered iframe document, preserving serving nutrition (currently the label
states about 11 chips / 28 g) and the manufacturer's ingredient names.

The Doritos page itself does not publish scalar nutrition values in its HTML.
If the cross-origin SmartLabel iframe is not available to the collector parser,
nutrition and ingredients intentionally remain empty rather than being copied
from a third-party or exploratory source. SmartLabel's label image is retained
when an authoritative image URL is exposed in the rendered frame.
