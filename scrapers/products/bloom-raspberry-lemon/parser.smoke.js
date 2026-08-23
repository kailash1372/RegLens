const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "parser.js"), "utf8");

function parse({ html, heading, productText, images = [] }) {
  const document = {
    documentElement: { outerHTML: html },
    querySelector(selector) {
      if (selector === "main h1") return { innerText: heading };
      if (selector === "main .main-pdp__intro") return { innerText: productText };
      return null;
    },
    querySelectorAll() {
      return images.map((attributes) => ({
        getAttribute(name) {
          return attributes[name] || null;
        },
      }));
    },
  };
  return new Function("input", "document", "location", source)(
    { url: "https://bloomnu.com/products/sparkling-energy?variant=44135391101028" },
    document,
    { href: "https://bloomnu.com/products/sparkling-energy?variant=44135391101028" },
  );
}

const target = parse({
  html: `<script type="application/ld+json">[
    {"@type":"Product","name":"Sparkling Energy - Strawberry Lemonade","description":"999 mg caffeine"},
    {"@type":"Product","name":"Sparkling Energy - Raspberry Lemon","brand":{"name":"Bloom Nutrition"},"description":"180 mg natural caffeine and a 10-calorie can with zero sugar."}
  ]</script>`,
  heading: "Sparkling Energy - Raspberry Lemon",
  productText:
    "180 mg natural caffeine. 10-calorie can. Zero sugar. Ingredients: Carbonated Water, Natural Flavors (Raspberry, Lemon), Citric Acid Warning: Do not use if seal is broken.",
  images: [
    {
      src: "/cdn/bloomenergy_raspberrylemon_03.png?width=1200",
      alt: "Raspberry Lemon nutrition label",
    },
  ],
});
assert.equal(target.product_name, "Sparkling Energy - Raspberry Lemon");
assert.equal(target.brand, "Bloom Nutrition");
assert.equal(target.product_line, "Sparkling Energy");
assert.equal(target.flavor, "Raspberry Lemon");
assert.equal(target.caffeine_mg, 180);
assert.equal(target.calories, 10);
assert.equal(target.sugar_g, 0);
assert.deepEqual(target.ingredients, [
  "Carbonated Water",
  "Natural Flavors (Raspberry, Lemon)",
  "Citric Acid",
]);
assert.equal(target.warnings.length, 1);
assert.deepEqual(target.scraper_assets, {
  nutrition_label_images: [
    {
      url: "https://bloomnu.com/cdn/bloomenergy_raspberrylemon_03.png?width=1600",
      content_type: "image",
      purpose: "nutrition_label",
    },
  ],
});

const adjacentVariant = parse({
  html: '<script type="application/ld+json">{"@type":"Product","name":"Sparkling Energy - Strawberry Lemonade"}</script>',
  heading: "Sparkling Energy - Strawberry Lemonade",
  productText: "999 mg caffeine. 999 calories. Total Sugars 99 g.",
});
assert.equal(adjacentVariant.product_name, null);
assert.equal(adjacentVariant.caffeine_mg, null);
assert.equal(adjacentVariant.calories, null);
assert.equal(adjacentVariant.sugar_g, null);
assert.deepEqual(adjacentVariant.scraper_assets.nutrition_label_images, []);

console.log("Bloom parser smoke tests: OK");
