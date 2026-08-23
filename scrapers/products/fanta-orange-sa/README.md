# Fanta Orange — Saudi Arabia

- Official source: https://www.coca-cola.com/sa/en/brands/fanta
- Market: `SA`

The page is a multi-product Fanta landing page. The parser first selects the
exact `Fanta Orange` heading and ascends to its `product-information` container,
so Strawberry and other Fanta variants cannot contaminate the snapshot. It
extracts the manufacturer-rendered nutrition rows (per 100 ml), ingredients,
and the product warning text from that scoped container. Ingredients retain
their source wording while being split only at top-level commas. Label images
are emitted only for first-party assets whose metadata identifies nutrition or
label content; the product packshot is not treated as a nutrition label.

The parser intentionally emits null/empty values when the current page does not
expose a field. No exploratory spreadsheet facts or regulatory conclusions are
embedded in this scraper. The JavaScript files are tracked Bright Data Scraper
Studio reference code, not runtime imports; copy them manually into Studio and
apply the shared schema from
[`../../studio-output-schema.json`](../../studio-output-schema.json) before
previewing or publishing.
