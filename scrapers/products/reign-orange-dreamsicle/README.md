# REIGN Orange Dreamsicle — US

- Target: <https://www.reignbodyfuel.com/en-us/products/orange-dreamsicle/>
- Market: `US`
- Exact variant: Orange Dreamsicle, not another REIGN flavor or product line.

The collector requires both the exact canonical URL and the matching product
header/JSON-LD identity. It reads `300MG of CAFFEINE` only from the official
page's REIGN Advantage section and retains the published product-line name
from JSON-LD. It also returns attributable on-page claims such as `Zero Sugar`
without turning a marketing statement into an unverified numeric sugar value.

The manufacturer page currently does not expose an ingredient statement, a
structured Nutrition Facts panel, an authoritative nutrition-label image, or a
product-attributable warning statement. Those fields deliberately remain
empty/null; no retailer or exploratory facts are used as fallbacks.

Copy `interaction.js` and `parser.js` into Scraper Studio and apply the shared
canonical schema from [`../../studio-output-schema.json`](../../studio-output-schema.json).
Execute the collector against the official URL and validate the raw output
before creating a fixture.
