# Nongshim Shin Ramyun Original Big Bowl — US

- Target: <https://nongshimusa.com/product-detail?pid=21>
- Market: `US`
- Exact variant gate: `pid=21`, the `Shin Ramyun Original Bowl` product title,
  the detailed-product image `shin_ramyun_big_bowl.png`, and the page's `Big
  Bowl version` description.

The visible product title alone says `Bowl`, while this page exposes four Shin
package types. The additional image and description gates prevent ingestion of
Bag, Bowl Noodle, Cup, and other Shin variants. Nutrition and the full
manufacturer ingredient statement are read from the product's accordion DOM;
the parser keeps parenthetical/bracketed ingredient groups intact. The exact
allergen/facility and manufacturer-change statements are retained as warnings.

Copy `interaction.js` and `parser.js` into Scraper Studio, apply the shared
schema from [`../../studio-output-schema.json`](../../studio-output-schema.json),
and preview the exact target URL before publishing.
