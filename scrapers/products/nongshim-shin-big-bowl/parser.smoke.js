const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "parser.js"), "utf8");

function element(text, attrs = {}, children = {}) {
  return { innerText: text, textContent: text, getAttribute: (name) => attrs[name] || null, querySelectorAll: (selector) => children[selector] || [] };
}
const row = (cells) => element(cells.join(" "), {}, { "th, td": cells.map((cell) => element(cell)) });
const nutritionBody = element("1 Servings per container Serving Size: 1 bowl (114g) Calories Per serving 500", {}, {
  "tbody tr": [row(["Total Fat", "17g", "22%"]), row(["Sodium", "1670mg", "73%"]), row(["Total Sugars", "4g", ""])],
});
const ingredientBody = element("WHEAT FLOUR (WHEAT FLOUR, NIACIN), SALT, NATURAL FLAVORS (CONTAINS SESAME), SUGAR †POWDERED CONTAINS WHEAT, SOY, AND SESAME. MANUFACTURED IN A FACILITY THAT ALSO PROCESSES MILK. INGREDIENTS, NUTRITION FACTS, AND ALLERGEN STATEMENTS CAN CHANGE.");
const document = {
  body: { innerText: "Big Bowl version" },
  querySelectorAll(selector) {
    if (selector === "p.n-h2") return [element("Shin Ramyun Original Bowl")];
    if (selector === ".product-detail-sub-img") return [element("", { "data-img-url": "shin_ramyun_big_bowl.png" })];
    if (selector === "#collapseOne table") return [element("", {}, { "tbody tr": nutritionBody.querySelectorAll("tbody tr") })];
    if (selector === "#collapseOne .accordion-body") return [nutritionBody];
    if (selector === "#collapseTwo .accordion-body") return [ingredientBody];
    if (selector === "main p") return [element("Big Bowl version")];
    return [];
  },
};
const url = "https://nongshimusa.com/product-detail?pid=21";
const result = new Function("input", "document", "location", source)({ url }, document, { href: url });
assert.equal(result.product_name, "Shin Ramyun Original Bowl");
assert.equal(result.calories, 500);
assert.equal(result.serving_size.value, 114);
assert.equal(result.nutrition_facts[1].daily_value_percent, 73);
assert.deepEqual(result.ingredients, ["WHEAT FLOUR (WHEAT FLOUR, NIACIN)", "SALT", "NATURAL FLAVORS (CONTAINS SESAME)", "SUGAR"]);
assert.equal(result.warnings.length, 3);
console.log("Nongshim Big Bowl parser smoke tests: OK");
