/* Local parser smoke tests; no Bright Data or network access is required. */
const assert = require("node:assert/strict");
const fs = require("node:fs");

const parser = fs.readFileSync(__dirname + "/parser.js", "utf8");
new Function("input", parser);

function run({ url, name, main, info, warning, body, images = {}, schemaSeed = false }) {
  const selectors = {
    ".product__info-container .product__title h1": name,
    ".product__info-container": info,
    "#product-main": main,
    "#panel-product-warning": warning,
  };
  global.location = { href: url };
  global.document = {
    documentElement: { outerHTML: body.html },
    body: { innerText: body.text, textContent: body.text },
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
  url: "https://cellucor.com/products/c4-performance-energy-frozen-bombsicle",
  name: "C4 Performance Energy® Frozen Bombsicle",
  main:
    "Elevate energy and performance with 200mg of caffeine*. " +
    "Stay sharp with zero sugar or artificial colors.",
  info: "C4 Performance Energy Frozen Bombsicle 12 Pack Serving Size: 16oz",
  warning: "Not intended for children. Recommended for adults.",
  body: {
    html:
      '<script type="application/ld+json">' +
      JSON.stringify({
        "@type": "ProductGroup",
        name: "C4 Performance Energy® Frozen Bombsicle",
        brand: { name: "C4 Energy" },
        description: "Elevate energy with 200mg of caffeine and zero sugar.",
      }) +
      "</script>",
    text: "C4 Performance Energy Frozen Bombsicle Ultimate 300mg",
  },
  images: {
    'img[src*="C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_StylizedPDPs_Nutrition"]': [
      {
        getAttribute(name) {
          return name === "src"
            ? "//cellucor.com/cdn/shop/files/C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_StylizedPDPs_Nutrition.jpg?v=1&width=416"
            : name === "srcset"
              ? "//cellucor.com/cdn/shop/files/C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_StylizedPDPs_Nutrition.jpg?v=1&width=416 416w, //cellucor.com/cdn/shop/files/C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_StylizedPDPs_Nutrition.jpg?v=1&width=1946 1946w"
              : "";
        },
      },
    ],
    'img[src*="C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_BasicPDPs-NFP-Fun"]': [
      {
        getAttribute(name) {
          return name === "src"
            ? "//cellucor.com/cdn/shop/files/C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_BasicPDPs-NFP-Fun.png?v=2&width=416"
            : "";
        },
      },
    ],
  },
  schemaSeed: true,
});

assert.equal(target.product_name, "C4 Performance Energy® Frozen Bombsicle");
assert.equal(target.caffeine_mg, 200);
assert.deepEqual(target.serving_size, { value: 16, unit: "fl oz", ml: 473 });
assert.equal(target.calories, null);
assert.deepEqual(target.ingredients, []);
assert.deepEqual(target.claims, ["Zero sugar", "No artificial colors"]);
assert.deepEqual(target.warnings, ["Not intended for children. Recommended for adults."]);
assert.deepEqual(target.scraper_assets, {
  nutrition_label_images: [
    {
      url: "https://cellucor.com/cdn/shop/files/C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_StylizedPDPs_Nutrition.jpg?v=1&width=1946",
      content_type: "image",
      purpose: "nutrition_label",
    },
    {
      url: "https://cellucor.com/cdn/shop/files/C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_BasicPDPs-NFP-Fun.png?v=2&width=416",
      content_type: "image",
      purpose: "nutrition_label",
    },
  ],
});

const ultimate = run({
  url: "https://cellucor.com/products/c4-ultimate-energy-frozen-bombsicle",
  name: "C4 Ultimate Energy® Frozen Bombsicle",
  main: "Elevate energy with 300mg of caffeine.",
  info: "Serving Size: 16oz",
  warning: "Not intended for children.",
  body: {
    html:
      '<script type="application/ld+json">' +
      JSON.stringify({
        "@type": "Product",
        name: "C4 Ultimate Energy® Frozen Bombsicle",
      }) +
      "</script>",
    text: "C4 Ultimate Energy Frozen Bombsicle 300mg",
  },
});

assert.equal(ultimate.product_name, null);
assert.equal(ultimate.caffeine_mg, null);
assert.equal(ultimate.calories, null);
assert.deepEqual(ultimate.serving_size, { value: null, unit: null, ml: null });
assert.deepEqual(ultimate.scraper_assets, { nutrition_label_images: [] });

console.log("C4 parser smoke tests passed");
