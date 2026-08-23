# Fanta Orange — Canada

- Official source: https://www.coca-cola.com/ca/en/brands/fanta
- Market: `CA`

The parser targets the exact `Fanta Orange` heading in the manufacturer's
multi-product page and scopes extraction to that product's
`product-information` container. It reads the current Canadian nutrition rows
(per 1 bottle / 500 mL), ingredients, and product metadata from the rendered
page. Ingredients retain the manufacturer's spelling and are split only at
top-level commas. Other Canadian Fanta variants, including Zero Sugar Orange,
are outside the scope and cannot contribute values.

Nutrition label images are emitted only when a scoped first-party image is
explicitly identified as a nutrition/label asset. Missing or image-only facts
remain null/empty. This is a separate market snapshot from the Saudi Arabia
Fanta Orange scraper; no cross-market values are merged here.

The JavaScript files are tracked Bright Data Scraper Studio reference code, not
runtime imports. Copy them manually into Studio, apply the shared schema from
[`../../studio-output-schema.json`](../../studio-output-schema.json), and
preview the exact URL before publishing.
