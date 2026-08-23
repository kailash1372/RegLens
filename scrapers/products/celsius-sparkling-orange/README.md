# CELSIUS Sparkling Orange

- Target: https://www.celsius.com/products/celsius/sparkling-orange/
- Market: US manufacturer site; this is the standard CELSIUS page, not the Essentials line.
- Parser reads the rendered product header, with conservative nulls when a
  field is not published as text.

Copy `interaction.js` and `parser.js` into a Bright Data Scraper Studio
collector and validate against the live page. The parser scopes identity and
claims to the exact Sparkling Orange product header and rejects Essentials
pages. Serving size, caffeine, calories, sugar, nutrition details, and the
complete ingredient list are printed in the product label image, so they stay
null/empty until a separate label/OCR step is added.
The product line also stays null unless the manufacturer explicitly publishes
`CELSIUS Sparkling` in the scoped text or structured data.
The parser returns `scraper_assets.nutrition_label_images` as raw transport
metadata for that future vision/OCR step; it is not part of the canonical
product snapshot and does not populate any nutrition field.

The stable exact-variant back-label image for that future step is:

```css
img[src*="/Orange-supp.png"]
img[alt="Sparkling Orange – Product's Back Label"]
```

with first-party URL:
`https://www.celsius.com/wp-content/uploads/2023/08/Orange-supp.png`.

Run the local target/rejection checks with `node smoke_test.js`.

Before publishing, follow the shared nullable-object schema procedure in
[`../../README.md`](../../README.md). The null-valued `serving_size` children
need the manually supplied JSON schema because Studio cannot infer their types.
