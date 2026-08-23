# Cheetos Crunchy Cheese Flavored Snacks — US

- Manufacturer product page: <https://www.cheetos.com/products/cheetos-crunchy-cheese-flavored-snacks>
- Current manufacturer-embedded SmartLabel source:
  <https://smartlabel.pepsico.info/028400589864-0028-en-US/index.html?stylekey=cheetos-10>
- Market: `US`
- Exact label identity: UPC `028400589864`, Cheetos Crunchy Cheese Flavored
  Snacks, 8½ oz (240.9 g) bag.

The Cheetos product page embeds this manufacturer SmartLabel as a cross-origin
iframe. The collector must be configured with the SmartLabel URL above as its
`input.url`; the parser verifies its exact UPC path and visible label product
name. It emits the structured nutrition panel (28g serving) and, when the
Studio preview supplies the SmartLabel Ingredients section, the manufacturer
ingredient labels including `Artificial Color (Yellow 6)`.

SmartLabel dynamically replaces its detail panel when navigating between
Nutrition and Ingredients. A single synchronous browser document can expose
only the currently selected section in some runtimes. Before production, use a
Studio preview to confirm both sections are retained; if its runtime cannot
retain both, configure the product page's SmartLabel browser action or record
the exact limitation rather than populating ingredients from another source.
The embedded label says it was updated by Cheetos on 29-Jun-2024 and warns that
package QR code information is most specific to the scanned package version.

Copy `interaction.js` and `parser.js` into Scraper Studio and apply the shared
schema from [`../../studio-output-schema.json`](../../studio-output-schema.json).
