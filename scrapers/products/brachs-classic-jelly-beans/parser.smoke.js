const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "parser.js"), "utf8");

function element(text, children = {}, attributes = {}, className = "") {
  return {
    className,
    innerText: text,
    textContent: text,
    getAttribute(name) {
      return attributes[name] || null;
    },
    querySelectorAll(selector) {
      return children[selector] || [];
    },
  };
}

function parse({ url, nutritionText = "Serving Size: 14 pieces Calories 150 Sugars 24 g" }) {
  const heading = element("Classic Jelly Beans");
  const nutrition = element(nutritionText);
  const ingredientBlock = element("Ingredients: Sugar, Corn Syrup (contains corn), Natural Flavor.");
  const scope = element(
    "Classic Jelly Beans",
    {
      "h1, h2, h3": [heading],
      ".product-detail__nutrition .collapse": [nutrition],
      ".product-detail__ingredients .collapse": [ingredientBlock],
      "img, source": [],
    },
    {},
    "product-detail__bottom",
  );
  const document = {
    title: "Brach's Classic Jelly Beans",
    body: scope,
    querySelectorAll(selector) {
      if (selector === ".product-detail__bottom") return [scope];
      return [];
    },
  };
  return new Function("input", "document", "location", source)(
    { url },
    document,
    { href: url },
  );
}

const targetUrl = "https://www.brachs.com/products/easter/classic-jelly-beans";
const target = parse({ url: targetUrl });
assert.equal(target.product_name, "Classic Jelly Beans");
assert.equal(target.serving_size.value, 14);
assert.deepEqual(target.ingredients, ["Sugar", "Corn Syrup (contains corn)", "Natural Flavor"]);

const zeroServing = parse({ url: targetUrl, nutritionText: "Serving Size: 0 pieces Calories 150" });
assert.deepEqual(zeroServing.serving_size, { value: null, unit: null, ml: null });
const negativeServing = parse({ url: targetUrl, nutritionText: "Serving Size: -1 pieces Calories 150" });
assert.deepEqual(negativeServing.serving_size, { value: null, unit: null, ml: null });

const wrongVariant = parse({
  url: "https://www.brachs.com/products/easter/jelly-bird-eggs",
});
assert.equal(wrongVariant.product_name, null);
assert.deepEqual(wrongVariant.ingredients, []);

console.log("Brach's parser smoke tests: OK");
