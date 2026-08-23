# C4 Performance Energy Frozen Bombsicle

- Target: https://cellucor.com/products/c4-performance-energy-frozen-bombsicle
- Market: US manufacturer site (Cellucor/C4 Energy).
- This exact path is the Performance formulation; do not use the similarly named Ultimate or pre-workout page.

The Shopify product page exposes product JSON-LD and rendered product content.
The parser selects the Performance product-group node, scopes facts to
`#product-main`/the active product info, and rejects the linked Ultimate
formulation. It extracts the visible 200 mg caffeine, 16 oz serving selector,
zero-sugar wording, and product warning. Calories, nutrition facts, and
ingredients remain empty because they are printed in the label image.

For a future label/OCR step, the stable exact-variant nutrition images are
selected with:

```css
img[src*="C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_StylizedPDPs_Nutrition"]
img[src*="C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_BasicPDPs-NFP-Fun"]
```

Their canonical first-party URLs are under
`https://cellucor.com/cdn/shop/files/` with those filenames (the page may add
`?v=...&width=...` resizing parameters). Validate in Scraper Studio after
copying; values remain null when the page does not publish them as text.

The parser additionally returns `scraper_assets.nutrition_label_images` as
raw transport metadata for a future vision/OCR stage. This is not part of the
canonical product snapshot; it contains only DOM-discovered absolute image
URLs and does not populate nutrition fields.

Current full-size URLs observed on the page:

```text
https://cellucor.com/cdn/shop/files/C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_StylizedPDPs_Nutrition.jpg?v=1776359497&width=5000
https://cellucor.com/cdn/shop/files/C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_BasicPDPs-NFP-Fun.png?v=1776359497&width=5000
```

Run the local target/rejection checks with `node smoke_test.js`.

Before publishing, follow the shared nullable-object schema procedure in
[`../../README.md`](../../README.md). `serving_size` is returned from the local
`serving` variable; do not rename the return expression to an undefined
`serving_size` variable.
