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

function parse({ url, productName, jsonLdName, caffeineTitle, claims }) {
  const jsonLd = element(
    JSON.stringify({
      "@type": "Product",
      name: jsonLdName,
      brand: "Reign Total Body Fuel",
    }),
  );
  const document = {
    querySelector(selector) {
      if (selector === "#product-detail-flavor.product-name") {
        return element(productName, { "data-category": "REIGN" });
      }
      return null;
    },
    querySelectorAll(selector) {
      if (selector === 'script[type="application/ld+json"]') return [jsonLd];
      if (selector === ".rtb-title") return [element(caffeineTitle), ...claims.map(element)];
      return [];
    },
  };
  return new Function("input", "document", "location", source)(
    { url },
    document,
    { href: url },
  );
}

const target = parse({
  url: "https://www.reignbodyfuel.com/en-us/products/orange-dreamsicle/",
  productName: "Orange Dreamsicle",
  jsonLdName: "Orange Dreamsicle",
  caffeineTitle: "300MG of CAFFEINE",
  claims: ["Zero Sugar", "BCAAS", "Vitamins B3, B6, B12", "Reduce Fatigue"],
});
assert.equal(target.brand, "REIGN");
assert.equal(target.product_name, "Orange Dreamsicle");
assert.equal(target.product_line, "Reign Total Body Fuel");
assert.equal(target.caffeine_mg, 300);
assert.deepEqual(target.claims, ["Zero Sugar", "BCAAS", "Vitamins B3, B6, B12", "Reduce Fatigue"]);
assert.equal(target.sugar_g, null);

const wrongFlavor = parse({
  url: "https://www.reignbodyfuel.com/en-us/products/orange-dreamsicle/",
  productName: "White Gummy Bear",
  jsonLdName: "White Gummy Bear",
  caffeineTitle: "300MG of CAFFEINE",
  claims: ["Zero Sugar"],
});
assert.equal(wrongFlavor.product_name, null);
assert.equal(wrongFlavor.caffeine_mg, null);

console.log("REIGN parser smoke tests: OK");
