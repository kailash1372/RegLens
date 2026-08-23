# Red Bull Original — US, 8.4 fl oz

- Target: <https://www.redbull.com/us-en/energydrink/products/red-bull-energy-drink-ingredients-list>
- Market: `US`
- Exact variant: Original Red Bull Energy Drink; `per 8.4 fl oz` only.

The parser requires the exact official ingredient-page URL and the page's
`Nutrition Declaration / per 8.4 fl oz` table. It extracts calories, sugars,
caffeine, and flexible nutrition facts from that table, rather than from
comparison copy elsewhere on the page. The manufacturer page currently calls
out ingredient topics (Caffeine, Taurine, B-group vitamins, Sugars, and Water)
but does not expose a package-style, comma-separated ingredient statement;
those exact topic labels are retained as the limited manufacturer-provided
ingredient representation.

Other Red Bull products are shown in page navigation. The exact URL plus the
8.4 fl oz nutrition-table gate prevents their facts from being emitted. There
is no attributable warning statement or authoritative nutrition-label image on
this target page, so those remain empty rather than inferred.

Copy `interaction.js` and `parser.js` into Scraper Studio. Configure the shared
canonical schema from [`../../studio-output-schema.json`](../../studio-output-schema.json),
then execute the collector against the official URL before adding a fixture.
Run `node parser.smoke.js` for local regression coverage.
