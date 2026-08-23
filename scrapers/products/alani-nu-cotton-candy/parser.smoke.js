const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "parser.js"), "utf8");

function element(text, attributes = {}) {
  return {
    innerText: text,
    textContent: text,
    getAttribute(name) {
      return attributes[name] || null;
    },
  };
}

function wrapper(elements) {
  return {
    0: elements[0],
    length: elements.length,
    first() {
      return wrapper(elements.slice(0, 1));
    },
    eq(index) {
      return wrapper(elements.slice(index, index + 1));
    },
    attr(name) {
      return elements[0]?.getAttribute(name) || null;
    },
    text() {
      return elements.map((item) => item.textContent).join(" ");
    },
    text_sane() {
      return this.text();
    },
    toArray() {
      return elements;
    },
    find(selector) {
      return wrapper(elements[0]?.children?.[selector] || []);
    },
    each(callback) {
      elements.forEach((item, index) => callback(index, item));
    },
  };
}

function parse({ servingText = "12 fl oz (355 mL)" }) {
  const jsonLd = element(JSON.stringify({ "@type": "Product", name: "Cotton Candy Energy" }));
  const nutritionRow = { children: { td: [element("Calories"), element("10"), element("0%")], }, textContent: "Calories 10 0%" };
  const selectorMap = {
    'script[type="application/ld+json"]': [jsonLd],
    'meta[property="og:site_name"]': [element("", { content: "Alani Nu" })],
    ".product-title": [element("Cotton Candy Energy")],
    ".product__category": [element("Energy Drinks")],
    ".product__flavor, [data-flavor]": [element("Cotton Candy")],
    ".product-benefits_cel__nutrition-info td:nth-child(2)": [element(servingText)],
    ".product-benefits_cel__panel-details-wrapper": [element("200 mg caffeine")],
    ".product-benefits_cel__nutrition-table tbody tr": [nutritionRow],
    ".product-benefits_cel__nutrition-ingredients": [element("Ingredients: Carbonated water, citric acid Contains: caffeine")],
    ".product-benefits_cel__benefit-item p": [element("Zero sugar")],
    'img[src*="Stretch_AN-Website-12oz-PDP-CTC-03_V1.png"]': [element("", { src: "/label.png" })],
  };
  const $ = (value) => {
    if (typeof value === "string") return wrapper(selectorMap[value] || []);
    return wrapper(value ? [value] : []);
  };
  const url = "https://www.alaninu.com/products/energy-drink-cotton-candy";
  return new Function("input", "document", "location", "$", source)(
    { url, schema_seed: true },
    {},
    { href: url },
    $,
  );
}

const target = parse({});
assert.deepEqual(target.serving_size, { value: 12, unit: "fl oz", ml: 355 });
assert.equal(target.caffeine_mg, 200);
assert.equal(target.product_name, "Cotton Candy Energy");

const zeroServing = parse({ servingText: "0 fl oz (0 mL)" });
assert.deepEqual(zeroServing.serving_size, { value: null, unit: null, ml: null });
const negativeServing = parse({ servingText: "-1 fl oz (-29 mL)" });
assert.deepEqual(negativeServing.serving_size, { value: null, unit: null, ml: null });

console.log("Alani Nu parser smoke tests: OK");
