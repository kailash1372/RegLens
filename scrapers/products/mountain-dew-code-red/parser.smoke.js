const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "parser.js"), "utf8");

function element(text, attributes = {}, children = {}) {
  return {
    textContent: text,
    innerText: text,
    title: text,
    contentDocument: attributes.contentDocument || null,
    getAttribute(name) {
      return attributes[name] || null;
    },
    querySelectorAll(selector) {
      return children[selector] || [];
    },
  };
}

function parse({ target = true }) {
  const row = (name, value, percent) =>
    element(`${name} ${value || ""} ${percent || ""}`, {}, {
      "[role='rowheader'], .nutrient": [element(name)],
      "[role='cell'], .nutrient-value": [element(value), element(percent)],
    });
  const label = element("", {}, {
    "#nutrition-facts [role='row']": target
      ? [
          row("Calories", "280", ""),
          row("Sodium", "180mg", "8%"),
          row("Total Sugars", "76g", ""),
        ]
      : [],
    "#nutrition-facts h6": [element("Serving Size 1 bottle")],
    "#ingredients": [
      element("CARBONATED WATER, CITRIC ACID, SODIUM BENZOATE (PRESERVES FRESHNESS)."),
    ],
  });
  const document = {
    title: target ? "Mountain Dew Code Red - 20 fl oz" : "Mountain Dew Code Red - 12 fl oz",
    body: { innerText: "Caffeine 91mg" },
    querySelectorAll(selector) {
      if (selector === ".product-name") return [element(target ? "Mountain Dew Code Red" : "Mountain Dew Voltage")];
      if (selector === ".pepsico-nf-label") return [element("", { "data-size": target ? "20" : "12" })];
      if (selector === ".pepsico-nf-label iframe, #product-iframe iframe") {
        return [element("", { contentDocument: label })];
      }
      if (selector === "#product-iframe img, .product-content-left img") return [];
      return [];
    },
  };
  return new Function("input", "document", "location", source)(
    { url: "https://www.pepsicoproductfacts.com/Home/Product?form=RTD&formula=92301%2A01%2A10-01&size=20" },
    document,
    { href: "https://www.pepsicoproductfacts.com/Home/Product?form=RTD&formula=92301%2A01%2A10-01&size=20" },
  );
}

const target = parse({ target: true });
assert.equal(target.product_name, "Mountain Dew Code Red");
assert.equal(target.caffeine_mg, 91);
assert.equal(target.calories, 280);
assert.equal(target.sugar_g, 76);
assert.deepEqual(target.serving_size, { value: 1, unit: "bottle", ml: null });
assert.deepEqual(target.ingredients, [
  "CARBONATED WATER",
  "CITRIC ACID",
  "SODIUM BENZOATE (PRESERVES FRESHNESS)",
]);

const wrong = parse({ target: false });
assert.equal(wrong.product_name, null);
assert.equal(wrong.caffeine_mg, null);
assert.deepEqual(wrong.nutrition_facts, []);

console.log("Mountain Dew Code Red parser smoke tests: OK");
