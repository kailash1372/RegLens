# MAGGI 2-Minute Masala Noodles — India

- Target: <https://www.maggi.in/en/product/maggi-2-minute-noodles-masala/>
- Market: `IN`
- Exact source identity: the target URL plus `MAGGI® 2-Minute Noodles` header and
  a table with both `per 100g` and `Per serve (75g)` columns.

The parser preserves the two nutrition bases separately. The scalar calories
and sugars are the stated 75g serving values, while `nutrition_facts` has one
row per 100g and one per serving for every manufacturer table row. Per-serving
GDA percentages are retained in `daily_value_percent`; when only the source's
RDA percentage exists, the fact name is marked `; RDA` to avoid implying it is
GDA. The current page does not publish a textual ingredient statement, so no
ingredient values are inferred from product imagery or other sites.

Copy `interaction.js` and `parser.js` into Scraper Studio and set the shared
schema from [`../../studio-output-schema.json`](../../studio-output-schema.json).
