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

function parse({ url, headingText = "Fanta Orange", serving = "per 100 ml" }) {
  const heading = element(headingText);
  const scope = element(
    `${headingText} ${serving}`,
    {
      "h1, h2, h3, h4": [heading],
      ".nutritional-information__row": [element("Energy 180 kJ 43 kcal")],
      p: [element("Ingredients: Carbonated water, Sugar, Orange juice.")],
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

const targetUrl = "https://www.coca-cola.com/sa/en/brands/fanta";
const target = parse({ url: targetUrl });
assert.equal(target.product_name, "Fanta Orange");
assert.equal(target.source.market, "SA");
assert.equal(target.serving_size.ml, 100);
assert.deepEqual(target.ingredients, ["Carbonated water", "Sugar", "Orange juice"]);

const zeroServing = parse({ url: targetUrl, serving: "per 0 ml" });
assert.deepEqual(zeroServing.serving_size, { value: null, unit: null, ml: null });
const negativeServing = parse({ url: targetUrl, serving: "per -1 ml" });
assert.deepEqual(negativeServing.serving_size, { value: null, unit: null, ml: null });

const wrongVariant = parse({
  url: "https://www.coca-cola.com/sa/en/brands/fanta-strawberry",
});
assert.equal(wrongVariant.product_name, null);
assert.deepEqual(wrongVariant.ingredients, []);

console.log("Fanta Saudi Arabia parser smoke tests: OK");
