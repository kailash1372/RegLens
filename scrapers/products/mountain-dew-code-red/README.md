# Mountain Dew Code Red — 20 fl oz (US)

- Official source: https://www.pepsicoproductfacts.com/Home/Product?form=RTD&formula=92301%2A01%2A10-01&size=20
- Market: `US`
- Variant identity: the parser requires the page title/product name to identify
  Mountain Dew Code Red and, when present, requires the PepsiCo `data-size` to
  remain `20`.

PepsiCo Product Facts server-renders the product identity and a More Information
section, then injects the current Nutrition Facts and ingredients into a label
iframe using `/services/labels/index` and GTIN `00012000002243`. The parser
reads that rendered label when Bright Data exposes the iframe document. It also
accepts a static capture of the label DOM, so the current values are not copied
from exploratory research or hardcoded into the collector.

The source currently exposes `Serving Size 1 bottle`, caffeine in the More
Information section, and a first-party product image. The page warns that
formulation and packaging can change; this is provenance context rather than a
product safety warning and is intentionally not emitted as a warning field.
Missing or non-rendered label values remain null/empty until the label resource
is available.
