# Brach's Classic Jelly Beans

- Official source: https://www.brachs.com/products/easter/classic-jelly-beans
- Market: `US`

The parser scopes the manufacturer page's `product-detail__bottom` region and
reads its current visible nutrition and ingredients disclosure. It identifies
the exact `Classic Jelly Beans` heading before emitting data, so a redirect or
unrelated recommendation cannot become a product snapshot. Ingredients are
split only at top-level commas, preserving parenthesized text and the original
label wording. Hidden or image-only values remain null/empty. First-party
nutrition-label images are emitted only when the scoped image metadata signals a
label or nutrition facts asset.

`interaction.js` is the minimal Bright Data Scraper Studio navigation/collection
entry point. These JavaScript files are tracked Studio reference code, not
runtime imports; copy them manually into a collector and apply the shared
schema from [`../../studio-output-schema.json`](../../studio-output-schema.json)
before previewing. This folder intentionally contains no exploratory
spreadsheet facts or regulatory conclusions.
