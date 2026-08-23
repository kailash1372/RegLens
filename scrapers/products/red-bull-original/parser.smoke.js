const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "parser.js"), "utf8");

function element(text, attributes = {}, children = {}) {
  return {
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

function parse({ url, tableText, rows, ingredientLinks = [], bodyText }) {
  const rowElements = rows.map(([name, value]) =>
    element(`${name} ${value}`, {}, { "th, td": [element(name), element(value)] }),
  );
  const table = element(tableText, {}, { "tbody tr": rowElements });
  const document = {
    body: { innerText: bodyText },
    querySelectorAll(selector) {
      if (selector === "table") return [table];
      if (selector === 'a[href^="#Ingredient"]') return ingredientLinks;
      return [];
    },
  };
  return new Function("input", "document", "location", source)(
    { url },
    document,
    { href: url },
  );
}

const targetUrl =
  "https://www.redbull.com/us-en/energydrink/products/red-bull-energy-drink-ingredients-list";
const target = parse({
  url: targetUrl,
  bodyText: "Red Bull Energy Drink gives you wiiings",
  tableText: "Nutrition Declaration per 8.4 fl oz",
  rows: [
    ["Calories", "110"],
    ["Fat", "0 g / 0% DV"],
    ["Sugars", "26 g"],
    ["Caffeine", "80 mg"],
    ["Niacin", "100%"],
  ],
  ingredientLinks: [
    element("Caffeine", { href: "#Ingredient - Caffeine" }),
    element("Taurine", { href: "#Ingredient - Taurine" }),
  ],
});
assert.equal(target.product_name, "Red Bull Energy Drink");
assert.equal(target.flavor, "Original");
assert.deepEqual(target.serving_size, { value: 8.4, unit: "fl oz", ml: null });
assert.equal(target.caffeine_mg, 80);
assert.equal(target.calories, 110);
assert.equal(target.sugar_g, 26);
assert.deepEqual(target.ingredients, ["Caffeine", "Taurine"]);
assert.deepEqual(target.nutrition_facts.at(-1), {
  name: "Niacin",
  value: null,
  unit: null,
  daily_value_percent: 100,
});

const wrongVariant = parse({
  url: "https://www.redbull.com/us-en/energydrink/products/red-bull-zero",
  bodyText: "Red Bull Energy Drink",
  tableText: "Nutrition Declaration per 8.4 fl oz",
  rows: [["Caffeine", "80 mg"]],
});
assert.equal(wrongVariant.product_name, null);
assert.equal(wrongVariant.caffeine_mg, null);
assert.deepEqual(wrongVariant.nutrition_facts, []);

console.log("Red Bull parser smoke tests: OK");
