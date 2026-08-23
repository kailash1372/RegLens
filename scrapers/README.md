# Bright Data Scraper Studio collectors

This directory is tracked reference material for the public RegLens prototype.
It is not imported by the application: FastAPI and React never execute these
JavaScript files. A maintainer copies a product's `interaction.js` and
`parser.js` into Bright Data Scraper Studio, previews and publishes that
collector, then configures its Collector ID for the runtime API provider. The
local files remain the reviewed, reproducible parser source even when a
collector was created through Bright Data's natural-language CLI.

The fixture provider is the default, so a fresh checkout does not require
Bright Data credentials. The catalog currently has these product identities:

| Product directory | Category | Market |
| --- | --- | --- |
| `alani-nu-cotton-candy` | energy drink | US |
| `celsius-sparkling-orange` | energy drink | US |
| `c4-frozen-bombsicle` | energy drink | US |
| `bloom-raspberry-lemon` | energy drink | US |
| `red-bull-original` | energy drink | US |
| `reign-orange-dreamsicle` | energy drink | US |
| `brachs-classic-jelly-beans` | candy | US |
| `fanta-orange-sa` | soft drink | SA |
| `fanta-orange-ca` | soft drink | CA |
| `mountain-dew-code-red` | soft drink | US |
| `doritos-nacho-cheese` | snack | US |
| `cheetos-crunchy` | snack | US |
| `maggi-masala-noodles` | instant noodles | IN |
| `nongshim-shin-big-bowl` | instant noodles | US |

Fanta Orange Saudi Arabia and Canada intentionally have separate directories,
sources, and snapshots even though they share the `fanta-orange` product
family. Their ingredients and nutrition bases must not be merged.

Each directory contains the interaction and parser code to copy into a
separate Bright Data Scraper Studio collector. Use the exact target URL from
that collector's README. The local parser output follows the shared Product
Passport contract in [`studio-output-schema.json`](studio-output-schema.json).

## Studio workflow

For each product:

1. Read the product README and open its official manufacturer URL.
2. Copy `interaction.js` into the collector's Interaction Code panel.
3. Copy `parser.js` into the Parser Code panel.
4. Apply the complete shared output schema and run a preview.
5. Inspect product identity, market, source URL, nulls, and nutrition bases.
6. Validate the output through RegLens before adding or updating a fixture.
7. Record the Collector ID and production-preview status in
   [`COLLECTORS.md`](COLLECTORS.md).

The Bright Data CLI can create and run collectors, but it cannot upload these
local files verbatim. Every CLI command should use the project-approved
package invocation:

```bash
npm_config_registry=https://registry.npmjs.org npx -p @brightdata/cli bdata scraper create <url> '<description>'
npm_config_registry=https://registry.npmjs.org npx -p @brightdata/cli bdata scraper run <collector-id> <url> --sync
```

CLI-generated output must not be treated as canonical merely because a run
succeeded. If its shape or values differ, finish the collector manually in
Studio with the reviewed local parser and shared schema. Bright Data's CLI
does not expose an automated self-healing API or a supported deletion command;
incomplete templates may require manual cleanup in the Bright Data console.

## Publishing with nullable nested values

Scraper Studio cannot infer child field types when a preview returns only
`null` values, for example:

```js
serving_size: {
  value: null,
  unit: null,
  ml: null,
}
```

The null values are valid product data and must not be replaced with invented
numbers. Before publishing each collector:

1. Run a preview and inspect the product identity and source URL.
2. In the **Output schema** panel, click **Edit schema**.
3. Switch the schema editor to **JSON view**.
4. Replace the schema with the complete contents of
   [`studio-output-schema.json`](studio-output-schema.json).
5. Save the schema, run the preview again, and confirm the output still
   contains the real values or nulls returned by the parser.
6. Select **Save to Production** only after that validation succeeds.

Do not add a separate `const serving_size = ...` unless the parser actually
returns that variable. Bloom and CELSIUS return the nested object directly;
C4 uses the local `serving` variable; Alani defines `serving_size` from page
text. The shared output schema is independent of those implementation details.

The shared schema also defines `scraper_assets.nutrition_label_images`, which
is transport metadata for later label-image enrichment. It does not change the
canonical product facts and must not be treated as extracted nutrition data.

## Validation boundary

The local smoke tests verify parser behavior against maintained HTML fixtures,
not the current rendered manufacturer sites. A collector is live-validated
only after a successful Scraper Studio preview or production API response.
