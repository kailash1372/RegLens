# Bloom Nutrition Raspberry Lemon Sparkling Energy

- Target: https://bloomnu.com/products/sparkling-energy?variant=44135391101028
- Market: US manufacturer site; the query selects the Raspberry Lemon variant.
- The canonical Shopify handle is `sparkling-energy`; Raspberry Lemon is a variant, not a separate product handle.

The parser accepts only a Product JSON-LD node (or product-page heading) that
states both `Sparkling Energy` and `Raspberry Lemon`. Facts come only from that
node and the product-content DOM, never page-wide navigation or nearby products.
Brand, product line, and flavor are emitted only when explicit in matching
structured data, a scoped heading, or page metadata; the variant gate itself
does not populate those fields.
It does not copy facts from the Raspberry Lemonade drink-mix product or retailer
listings. Serving size, nutrition facts, ingredients, and warnings remain
null/empty when the first-party page exposes them only in a label image; a
separate vision enrichment path may handle that image later.

The raw collector output also includes `scraper_assets.nutrition_label_images`.
It finds the live `src` or `srcset` whose filename contains
`bloomenergy_raspberrylemon_03.png`, resolves it against the current page URL,
requests the 1600-pixel first-party rendition for legible label text,
and emits the resulting absolute image URL. This metadata is outside the
canonical product contract.

Run `node parser.smoke.js` in this directory for offline target/adjacent-flavor
and label-asset regression coverage. The smoke fixture is not a live-site
validation.

Before publishing, follow the shared nullable-object schema procedure in
[`../../README.md`](../../README.md). The live Raspberry Lemon preview has been
observed successfully, but any production revision must be previewed again.
