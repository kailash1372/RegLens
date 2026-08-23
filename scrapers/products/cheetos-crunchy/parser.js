/* Cheetos Crunchy Cheese Flavored Snacks SmartLabel parser. */
function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function pageUrl() {
  if (typeof location !== "undefined" && location.href) return location.href;
  return typeof input !== "undefined" && input.url ? input.url : "";
}

function allElements(selector, root) {
  const scope = root || (typeof document !== "undefined" ? document : null);
  if (scope && scope.querySelectorAll) return Array.from(scope.querySelectorAll(selector));
  if (typeof $ === "function") return $(selector).toArray();
  return [];
}

function textOf(element) {
  return clean(element && (element.innerText || element.textContent));
}

function numberValue(value) {
  const text = clean(value);
  if (!text || /^[<>]/.test(text)) return null;
  const match = text.replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function unitValue(value) {
  const match = clean(value).match(/\b(g|mg|mcg|kcal)\b/i);
  return match ? match[1].toLowerCase() : null;
}

function exactSmartLabelUrl(url) {
  try {
    const parsed = new URL(url);
    return (
      parsed.hostname === "smartlabel.pepsico.info" &&
      /\/028400589864-0028-en-US\/index\.html$/i.test(parsed.pathname)
    );
  } catch (error) {
    return false;
  }
}

function nutritionRows() {
  return allElements("li.nfp__row")
    .map((row) => allElements("span", row).map(textOf).filter(Boolean))
    .filter((cells) => cells.length >= 2)
    .map((cells) => ({ name: cells[0], amount: cells[1], dailyValue: cells[2] || "" }));
}

function nutritionFacts(rows) {
  return rows.map((row) => ({
    name: row.name,
    value: numberValue(row.amount),
    unit: unitValue(row.amount),
    daily_value_percent: /%$/.test(row.dailyValue) ? numberValue(row.dailyValue) : null,
  }));
}

function currentIngredients() {
  return allElements("#ingredient-list .list-title")
    .map(textOf)
    .filter((value, index, values) => value && values.indexOf(value) === index);
}

function servingSize() {
  const text = textOf(allElements(".nfp__header")[0]);
  const match = text.match(/about\s+\d+\s+pieces\s*\((\d+(?:\.\d+)?)\s*g\)/i);
  return match ? Number(match[1]) : null;
}

const url = pageUrl();
const pageText = textOf(typeof document !== "undefined" ? document.body : null);
const rows = nutritionRows();
const isTargetProduct =
  exactSmartLabelUrl(url) &&
  /\bcheetos,\s*crunchy,\s*cheese flavored snacks\b/i.test(pageText) &&
  rows.length > 0;
const calories = rows.find((row) => /^calories$/i.test(row.name));
const sugars = rows.find((row) => /^total sugars$/i.test(row.name));

return {
  brand: isTargetProduct ? "Cheetos" : null,
  product_name: isTargetProduct ? "Cheetos, Crunchy, Cheese Flavored Snacks" : null,
  product_line: isTargetProduct ? "Crunchy" : null,
  flavor: isTargetProduct ? "Cheese" : null,
  serving_size: isTargetProduct ? { value: servingSize(), unit: "g", ml: null } : { value: null, unit: null, ml: null },
  caffeine_mg: null,
  calories: isTargetProduct ? numberValue(calories && calories.amount) : null,
  sugar_g: isTargetProduct ? numberValue(sugars && sugars.amount) : null,
  nutrition_facts: isTargetProduct ? nutritionFacts(rows) : [],
  ingredients: isTargetProduct ? currentIngredients() : [],
  warnings: [],
  claims: [],
  scraper_assets: { nutrition_label_images: [] },
  source: { url, market: "US", scraped_at: new Date().toISOString() },
};
