const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "parser.js"), "utf8");

function element(text, children = {}) {
  return { innerText: text, textContent: text, querySelectorAll: (selector) => children[selector] || [] };
}
const row = (cells) => element(cells.join(" "), { span: cells.map((cell) => element(cell)) });
const document = {
  body: element("Cheetos, Crunchy, Cheese Flavored Snacks"),
  querySelectorAll(selector) {
    if (selector === "li.nfp__row") return [row(["Calories", "160"]), row(["Total Fat", "10 g", "13%"]), row(["Total Sugars", "1 g"])];
    if (selector === ".nfp__header") return [element("Serving Size About 21 Pieces (28g)")];
    if (selector === "#ingredient-list .list-title") return [element("Enriched Corn Meal"), element("Artificial Color (Yellow 6)")];
    return [];
  },
};
const url = "https://smartlabel.pepsico.info/028400589864-0028-en-US/index.html?stylekey=cheetos-10";
const result = new Function("input", "document", "location", source)({ url }, document, { href: url });
assert.equal(result.calories, 160);
assert.equal(result.sugar_g, 1);
assert.equal(result.serving_size.value, 28);
assert.deepEqual(result.ingredients, ["Enriched Corn Meal", "Artificial Color (Yellow 6)"]);
console.log("Cheetos parser smoke tests: OK");
