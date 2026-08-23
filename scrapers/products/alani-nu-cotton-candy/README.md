# Alani Nu Cotton Candy Energy

- Target: https://www.alaninu.com/products/energy-drink-cotton-candy
- Market: US manufacturer site.
- Bright Data collector: `c_mt4gy8rx2lzhs4i7t3` (the canonical product fields
  were previewed and API-tested).
- Interaction: `navigate(input.url); collect(parse());`.
- Local parser: canonical copy of the tested Scraper Studio parser; nutrition
  values are extracted from the live manufacturer page and never embedded.

The page is a Shopify storefront and may include merchandising/recommendation
blocks. The parser prefers Product JSON-LD for identity and uses product-scoped
selectors for caffeine, nutrition, ingredients, warnings, and claims. Bright
Data's runtime provides the `$` and `text_sane()` helpers used by the parser.

The raw collector result also emits
`scraper_assets.nutrition_label_images`. The exact Cotton Candy label is
selected from the rendered page with:

```css
img[src*="Stretch_AN-Website-12oz-PDP-CTC-03_V1.png"]
```

This image was visually verified to contain nutrition facts, ingredients, and
the caffeine warning. Its live first-party URL is derived rather than embedded.
The later `scraper_assets` addition still requires a production preview before
that asset field should be considered API-validated.

Before publishing, follow the shared nullable-object schema procedure in
[`../../README.md`](../../README.md). In particular, keep genuine unavailable
values as `null`; do not use placeholder nutrition values to train inference.
