/* Nongshim Shin Ramyun Original Big Bowl parser for Bright Data Scraper Studio. */
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
  const match = clean(value).replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function unitValue(value) {
  const match = clean(value).match(/(?:\d\s*|\s)(mg|mcg|kcal|g)\b/i);
  return match ? match[1].toLowerCase() : null;
}

function splitIngredients(value) {
  const result = [];
  let current = "";
  let depth = 0;
  for (const character of String(value || "")) {
    if (character === "(" || character === "[") depth += 1;
    if (character === ")" || character === "]") depth = Math.max(0, depth - 1);
    if (character === "," && depth === 0) {
      if (clean(current)) result.push(clean(current));
      current = "";
    } else {
      current += character;
    }
  }
  if (clean(current)) result.push(clean(current));
  return result;
}

function exactTargetUrl(url) {
  try {
    const parsed = new URL(url);
    return (
      /(^|\.)nongshimusa\.com$/i.test(parsed.hostname) &&
      parsed.pathname === "/product-detail" &&
      parsed.searchParams.get("pid") === "21"
    );
  } catch (error) {
    return false;
  }
}

function primaryTitle() {
  return allElements("p.n-h2").map(textOf).find((value) => /^shin ramyun original bowl$/i.test(value)) || "";
}

function hasBigBowlImage() {
  return allElements(".product-detail-sub-img").some((element) =>
    /(?:data-img-url|style)/i.test("data-img-url style") &&
    /shin_ramyun_big_bowl\.png/i.test(
      `${element.getAttribute("data-img-url") || ""} ${element.getAttribute("style") || ""}`,
    ),
  );
}

function nutritionRows() {
  const table = allElements("#collapseOne table")[0];
  if (!table) return [];
  return allElements("tbody tr", table)
    .map((row) => allElements("th, td", row).map(textOf).filter(Boolean))
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

function ingredientStatement() {
  const body = textOf(allElements("#collapseTwo .accordion-body")[0]);
  if (!body) return "";
  return clean(body.split(/†\s*POWDERED\b/i)[0]);
}

function warningsFromBody() {
  const body = textOf(allElements("#collapseTwo .accordion-body")[0]);
  if (!body) return [];
  return body
    .split(/(?=CONTAINS\s+WHEAT|MANUFACTURED\s+IN\s+A\s+FACILITY|INGREDIENTS,\s+NUTRITION)/i)
    .map(clean)
    .filter((value) => /^(?:CONTAINS\s+WHEAT|MANUFACTURED\s+IN\s+A\s+FACILITY|INGREDIENTS,\s+NUTRITION)/i.test(value));
}

function servingSize() {
  const text = textOf(allElements("#collapseOne .accordion-body")[0]);
  const match = text.match(/serving size:\s*1\s+bowl\s*\((\d+(?:\.\d+)?)\s*g\)/i);
  return match ? Number(match[1]) : null;
}

const url = pageUrl();
const title = primaryTitle();
const rows = nutritionRows();
const nutritionBody = textOf(allElements("#collapseOne .accordion-body")[0]);
const descriptionText = allElements("main p").map(textOf).join(" ");
const caloriesMatch = nutritionBody.match(/\bcalories\s+per serving\s+(\d+(?:\.\d+)?)/i);
const isTargetProduct =
  exactTargetUrl(url) &&
  /^shin ramyun original bowl$/i.test(title) &&
  hasBigBowlImage() &&
  /\bbig bowl version\b/i.test(descriptionText || document.body.innerText) &&
  rows.length > 0;
const sugar = rows.find((row) => /^total sugars$/i.test(row.name));

return {
  brand: isTargetProduct ? "Nongshim" : null,
  product_name: isTargetProduct ? title : null,
  product_line: isTargetProduct ? "Shin Ramyun" : null,
  flavor: isTargetProduct ? "Original Big Bowl" : null,
  serving_size: isTargetProduct ? { value: servingSize(), unit: "g", ml: null } : { value: null, unit: null, ml: null },
  caffeine_mg: null,
  calories: isTargetProduct && caloriesMatch ? Number(caloriesMatch[1]) : null,
  sugar_g: isTargetProduct ? numberValue(sugar && sugar.amount) : null,
  nutrition_facts: isTargetProduct ? nutritionFacts(rows) : [],
  ingredients: isTargetProduct ? splitIngredients(ingredientStatement()) : [],
  warnings: isTargetProduct ? warningsFromBody() : [],
  claims: [],
  scraper_assets: { nutrition_label_images: [] },
  source: { url, market: "US", scraped_at: new Date().toISOString() },
};
