const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "parser.js"), "utf8");

function element(text, children = {}, attributes = {}, className = "") {
  return {
    className,
    innerText: text,
    textContent: text,
    parentElement: null,
    getAttribute(name) {
      return attributes[name] || null;
    },
    querySelectorAll(selector) {
      return children[selector] || [];
    },
  };
}

function parse({ url, headingText = "Fanta Orange", serving = "per 500 ml" }) {
  const heading = element(headingText);
  const facts = [element("Energy 240 kJ 60 kcal")];
  const ingredient = element("Ingredients: Carbonated water, Sugar, Natural orange flavour.");
  const scope = element(
    `${headingText} ${serving}`,
    {
      "h1, h2, h3, h4": [heading],
      ".nutritional-information__row": facts,
      p: [ingredient],
      "img, source": [],
    },
    {},
    "product-information",
  );
  heading.parentElement = scope;
  const document = {
    querySelector(selector) {
      return selector === "meta[name='brand']" ? element("", {}, { content: "Fanta" }) : null;
    },
    querySelectorAll(selector) {
      return selector === "h1, h2, h3, h4" || ["h1", "h2", "h3", "h4"].includes(selector) ? [heading] : [];
    },
  };
  return new Function("input", "document", "location", source)(
    { url },
    document,
    { href: url },
  );
}

const targetUrl = "https://www.coca-cola.com/ca/en/brands/fanta";
const target = parse({ url: targetUrl });
assert.equal(target.product_name, "Fanta Orange");
assert.equal(target.source.market, "CA");
assert.equal(target.serving_size.ml, 500);
assert.deepEqual(target.ingredients, ["Carbonated water", "Sugar", "Natural orange flavour"]);

const zeroServing = parse({ url: targetUrl, serving: "per 0 ml" });
assert.deepEqual(zeroServing.serving_size, { value: null, unit: null, ml: null });
const negativeServing = parse({ url: targetUrl, serving: "per -1 ml" });
assert.deepEqual(negativeServing.serving_size, { value: null, unit: null, ml: null });

const wrongVariant = parse({
  url: "https://www.coca-cola.com/ca/en/brands/fanta-zero",
});
assert.equal(wrongVariant.product_name, null);
assert.deepEqual(wrongVariant.nutrition_facts, []);

console.log("Fanta Canada parser smoke tests: OK");
