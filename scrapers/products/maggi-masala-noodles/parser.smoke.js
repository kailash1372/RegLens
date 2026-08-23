const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "parser.js"), "utf8");

function element(text, children = {}) {
  return { innerText: text, textContent: text, querySelectorAll: (selector) => children[selector] || [] };
}

const row = (cells) => element(cells.join(" "), { "th, td": cells.map((cell) => element(cell)) });
const table = element("per 100g Per serve (75g)", {
  "tbody tr": [
    row(["Energy (kcal)", "384", "288", "14%", "-"]),
    row(["-Total Sugars(g)", "1.8", "1.4", "2%", "-"]),
    row(["Iron (mg)", "6.90", "5.17", "-", "17%"]),
  ],
});
const document = {
  querySelectorAll(selector) {
    if (selector === "h1") return [element("MAGGI® 2-Minute Noodles")];
    if (selector === "table") return [table];
    return [];
  },
};
const url = "https://www.maggi.in/en/product/maggi-2-minute-noodles-masala/";
const result = new Function("input", "document", "location", source)({ url }, document, { href: url });
assert.equal(result.calories, 288);
assert.equal(result.sugar_g, 1.4);
assert.equal(result.nutrition_facts[0].name, "Energy (kcal) (per 100g)");
assert.equal(result.nutrition_facts[1].daily_value_percent, 14);
assert.equal(result.nutrition_facts.at(-1).name, "Iron (mg) (per serving: 75g); RDA");
console.log("MAGGI parser smoke tests: OK");
