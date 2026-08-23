/* Red Bull Original 8.4 fl oz parser for Bright Data Scraper Studio. */
function clean(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function pageUrl() {
  if (typeof location !== "undefined" && location.href) return location.href;
  if (typeof input !== "undefined" && input.url) return input.url;
  return "";
}

function pageText() {
  if (typeof document !== "undefined" && document.body) {
    return clean(document.body.innerText || document.body.textContent);
  }
  if (typeof $ === "function") return clean($("body").text());
  return "";
}

function allElements(selector, root) {
  const scope = root || (typeof document !== "undefined" ? document : null);
  if (scope && typeof scope.querySelectorAll === "function") {
    return Array.from(scope.querySelectorAll(selector));
  }
  if (typeof $ === "function") return $(selector).toArray();
  return [];
}

function textOf(element) {
  return clean(element && (element.innerText || element.textContent));
}

function firstMatch(text, pattern) {
  const match = String(text || "").match(pattern);
  return match ? clean(match[1] || match[0]) : null;
}

function numberValue(value) {
  const match = String(value || "")
    .replace(/,/g, "")
    .match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function normalizedUnit(value) {
  const unit = clean(value).toLowerCase().replace(/\./g, "");
  if (/^fl\s*oz$/.test(unit)) return "fl oz";
  if (/^(g|mg|kcal|calories)$/.test(unit)) return unit;
  return null;
}

function uniqueStrings(values) {
  const seen = new Set();
  return values
    .map(clean)
    .filter((value) => {
      const key = value.toLowerCase();
      if (!value || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function exactTargetUrl(url) {
  return /^https:\/\/(?:www\.)?redbull\.com\/us-en\/energydrink\/products\/red-bull-energy-drink-ingredients-list\/?(?:[?#].*)?$/i.test(
    url,
  );
}

function nutritionTable() {
  return allElements("table").find((table) => {
    const text = textOf(table);
    return /\bnutrition declaration\b/i.test(text) && /\bper\s+8\.4\s+fl\.?\s*oz\b/i.test(text);
  });
}

function tableRows(table) {
  if (!table) return [];
  return allElements("tbody tr", table)
    .map((row) => {
      const cells = allElements("th, td", row).map(textOf).filter(Boolean);
      return cells.length >= 2 ? { name: cells[0], rawValue: cells[1] } : null;
    })
    .filter(Boolean);
}

function nutritionFact(name, rawValue) {
  const dailyValue = firstMatch(rawValue, /(?:\/\s*)?(\d+(?:\.\d+)?)\s*%\s*DV\b/i);
  const percentOnly = /^\d+(?:\.\d+)?\s*%$/.test(clean(rawValue));
  const unit = firstMatch(rawValue, /\b(mg|g|kcal|calories)\b/i);
  return {
    name,
    value: percentOnly ? null : numberValue(rawValue),
    unit: percentOnly ? null : normalizedUnit(unit),
    daily_value_percent: dailyValue ? numberValue(dailyValue) : percentOnly ? numberValue(rawValue) : null,
  };
}

function nutritionFacts(rows) {
  return rows.map((row) => nutritionFact(row.name, row.rawValue));
}

function rowValue(rows, name) {
  const row = rows.find((candidate) => clean(candidate.name).toLowerCase() === name.toLowerCase());
  return row ? row.rawValue : null;
}

function declaredIngredients() {
  // This page labels these anchor targets as the formula's ingredients. It does
  // not publish a package-style, comma-separated ingredient statement.
  return uniqueStrings(
    allElements('a[href^="#Ingredient"]')
      .filter((anchor) => /^#Ingredient\s*-\s*/i.test(anchor.getAttribute("href") || ""))
      .map(textOf),
  );
}

function exactOriginalName(text) {
  return /\bred\s*bull\s+energy\s+drink\b/i.test(text)
    ? "Red Bull Energy Drink"
    : null;
}

const url = pageUrl();
const text = pageText();
const table = nutritionTable();
const rows = tableRows(table);
const servingText = table ? textOf(table) : "";
const exactServing = /\bper\s+8\.4\s+fl\.?\s*oz\b/i.test(servingText);
const name = exactOriginalName(text);
const isTargetProduct = exactTargetUrl(url) && Boolean(name) && exactServing;
const caffeineRaw = rowValue(rows, "Caffeine");
const caloriesRaw = rowValue(rows, "Calories");
const sugarRaw = rowValue(rows, "Sugars");

return {
  brand: isTargetProduct ? "Red Bull" : null,
  product_name: isTargetProduct ? name : null,
  product_line: isTargetProduct ? "Red Bull Energy Drink" : null,
  flavor: isTargetProduct ? "Original" : null,
  serving_size: {
    value: isTargetProduct ? 8.4 : null,
    unit: isTargetProduct ? "fl oz" : null,
    ml: null,
  },
  caffeine_mg: isTargetProduct ? numberValue(caffeineRaw) : null,
  calories: isTargetProduct ? numberValue(caloriesRaw) : null,
  sugar_g: isTargetProduct ? numberValue(sugarRaw) : null,
  nutrition_facts: isTargetProduct ? nutritionFacts(rows) : [],
  ingredients: isTargetProduct ? declaredIngredients() : [],
  // No product-specific warning statement is published on the target page.
  warnings: [],
  claims:
    isTargetProduct && /\bgives you wiiings\b/i.test(text)
      ? ["Gives you wiiings"]
      : [],
  scraper_assets: { nutrition_label_images: [] },
  source: {
    url,
    market: "US",
    scraped_at: new Date().toISOString(),
  },
};
