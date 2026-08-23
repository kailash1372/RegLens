/* Local parser smoke tests; no Bright Data or network access is required. */
const assert = require("node:assert/strict");
const fs = require("node:fs");

const parser = fs.readFileSync(__dirname + "/parser.js", "utf8");
new Function("input", parser);

function run({ url, name, description, body, images = {}, schemaSeed = false }) {
  const selectors = {
    ".single-products .product-header .desktop .top .left h3": name,
    ".single-products .product-header .desktop .top .left .product-description":
      description,
    ".single-products .product-header .power-words": "Celsius",
  };
  global.location = { href: url };
  global.document = {
    documentElement: { outerHTML: body },
    body: { innerText: body, textContent: body },
    querySelector(selector) {
      const text = selectors[selector];
      return text === undefined ? null : { innerText: text, textContent: text };
    },
    querySelectorAll(selector) {
      return images[selector] || [];
    },
  };
  return new Function("input", parser)({ url, schema_seed: schemaSeed });
}

const target = run({
  url: "https://www.celsius.com/products/celsius/sparkling-orange/",
  name: "Sparkling Orange",
  description:
    "Made with clinically proven ingredients for active lifestyles.",
  body: "Sparkling Orange Celsius Essentials 270 mg",
  schemaSeed: true,
  images: {
    'img[src*="/Orange-supp.png"]': [
      {
        getAttribute(name) {
          return name === "src"
            ? "/wp-content/uploads/2023/08/Orange-supp.png"
            : "";
        },
      },
      {
        getAttribute(name) {
          return name === "src"
            ? "https://www.celsius.com/wp-content/uploads/2023/08/Orange-supp.png"
            : "";
        },
      },
    ],
  },
});

assert.equal(target.brand, "CELSIUS");
assert.equal(target.product_name, "Sparkling Orange");
assert.equal(target.product_line, null);
assert.equal(target.flavor, "Orange");
assert.deepEqual(target.serving_size, { value: null, unit: null, ml: null });
assert.equal(target.caffeine_mg, null);
assert.equal(target.calories, null);
assert.equal(target.sugar_g, null);
assert.deepEqual(target.nutrition_facts, []);
assert.deepEqual(target.ingredients, []);
assert.deepEqual(target.claims, ["Clinically proven ingredients"]);
assert.deepEqual(target.scraper_assets, {
  nutrition_label_images: [
    {
      url: "https://www.celsius.com/wp-content/uploads/2023/08/Orange-supp.png",
      content_type: "image",
      purpose: "nutrition_label",
    },
  ],
});

const essentials = run({
  url: "https://www.celsius.com/products/essentials/orange/",
  name: "Sparkling Orange",
  description: "270 mg caffeine and 10 calories.",
  body: "Sparkling Orange Essentials 270 mg",
});

assert.equal(essentials.brand, null);
assert.equal(essentials.product_name, null);
assert.equal(essentials.caffeine_mg, null);
assert.equal(essentials.calories, null);
assert.deepEqual(essentials.serving_size, { value: null, unit: null, ml: null });
assert.deepEqual(essentials.scraper_assets, { nutrition_label_images: [] });

console.log("CELSIUS parser smoke tests passed");
