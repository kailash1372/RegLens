const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "parser.js"), "utf8");

function element(text, attributes = {}, children = {}) {
  return {
    textContent: text,
    innerText: text,
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
    element("", {}, {
      span: [element(name), element(value), element(percent)],
    });
  const frameDocument = element("", {}, {
    ".nfp__values > .nfp__row": target
      ? [row("Calories", "150", ""), row("Sodium", "170 mg", "7%"), row("Total Sugars", "< 1 g", "")]
      : [],
    ".nfp__header": [element("Nutrition Facts Serving Size About 11 Chips (28g)")],
    "#ingredient-list .list-title": target
      ? [element("Corn"), element("Vegetable Oil"), element("And Less Than 2% Of:"), element("Yellow 6"), element("Red 40")]
      : [],
    img: [],
  });
  const frame = element("", {
    src: "https://smtlbl.app/upc/028400516464?stylekey=doritos-10",
    contentDocument: frameDocument,
  });
  const document = {
    querySelectorAll(selector) {
      if (selector === "#product-scope") {
        return [element("", { "data-name": target ? "DORITOS Nacho Cheese Flavored Tortilla Chips" : "DORITOS Cool Ranch" })];
      }
      if (selector === ".single-product__title h1") return [element("DORITOS Nacho Cheese Flavored Tortilla Chips")];
      if (selector === "#prod-nutrition iframe, .product-nutrition iframe") return [frame];
      return [];
    },
  };
  const url = "https://www.doritos.com/products/doritos-nacho-cheese-flavored-tortilla-chips";
  return new Function("input", "document", "location", source)({ url }, document, { href: url });
}

const target = parse({ target: true });
assert.equal(target.product_name, "DORITOS Nacho Cheese Flavored Tortilla Chips");
assert.equal(target.calories, 150);
assert.equal(target.sugar_g, null);
assert.deepEqual(target.serving_size, { value: 28, unit: "g", ml: null });
assert.deepEqual(target.ingredients, ["Corn", "Vegetable Oil", "Yellow 6", "Red 40"]);

const wrong = parse({ target: false });
assert.equal(wrong.product_name, null);
assert.deepEqual(wrong.nutrition_facts, []);
assert.deepEqual(wrong.ingredients, []);

console.log("DORITOS Nacho Cheese parser smoke tests: OK");
