/* Mountain Dew Code Red 20 fl oz (US) parser. */
function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function numberValue(value) {
  const text = clean(value);
  if (!text || /[<>]/.test(text)) return null;
  const match = text.replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function uniqueStrings(values) {
  const seen = new Set();
  return values.map(clean).filter((value) => {
    if (!value) return false;
    const key = value.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function splitIngredients(value) {
  const result = [];
  let current = "";
  let depth = 0;
  for (const character of String(value || "")) {
    if (character === "(") depth += 1;
    if (character === ")") depth = Math.max(0, depth - 1);
    if (character === "," && depth === 0) {
      result.push(current);
      current = "";
    } else {
      current += character;
    }
  }
  result.push(current);
  return uniqueStrings(result);
}

function pageUrl() {
  if (typeof location !== "undefined" && location.href) return location.href;
  return typeof input !== "undefined" && input.url ? input.url : "";
}

function query(selector, root) {
  const container = root || (typeof document !== "undefined" ? document : null);
  if (!container || typeof container.querySelectorAll !== "function") return [];
  return Array.from(container.querySelectorAll(selector));
}

function textOf(element) {
  return clean(element && (element.textContent || element.innerText));
}

function absoluteUrl(value) {
  try {
    return new URL(String(value || ""), pageUrl()).href;
  } catch (error) {
    return null;
  }
}

function targetContainer() {
  const container = query(".pepsico-nf-label")[0];
  return container || (typeof document !== "undefined" ? document : null);
}

function isTargetProduct() {
  const productName = textOf(query(".product-name")[0]);
  const title = typeof document !== "undefined" ? textOf(document.title) : "";
  const container = query(".pepsico-nf-label")[0];
  const size = container && container.getAttribute("data-size");
  return (
    /mountain dew code red/i.test(productName || title) &&
    (!size || size === "20") &&
    (!title || /20\s*fl\s*oz/i.test(title))
  );
}

// Bright Data may expose a rendered iframe as contentDocument. Keeping this
// fallback makes the parser useful both with the injected label and with a
// static page capture where the iframe has not been hydrated yet.
function labelRoots() {
  const roots = [];
  for (const frame of query(".pepsico-nf-label iframe, #product-iframe iframe")) {
    if (frame.contentDocument) roots.push(frame.contentDocument);
  }
  const container = targetContainer();
  if (container) roots.push(container);
  if (typeof document !== "undefined") roots.push(document);
  return roots;
}

function firstMatch(selector) {
  for (const root of labelRoots()) {
    const match = query(selector, root)[0];
    if (match) return match;
  }
  return null;
}

function parseNutritionRow(row) {
  const nutrient = textOf(query("[role='rowheader'], .nutrient", row)[0]);
  const cells = query("[role='cell'], .nutrient-value", row).map(textOf);
  if (!nutrient || !cells.length) return null;
  const amountText = cells.find((value) => /\d/.test(value) && !/%/.test(value)) || "";
  const amount = amountText.match(/<?\s*([\d,.]+)\s*(kcal|calories?|g|mg|mcg|µg)?/i);
  if (!amount || /</.test(amount[0]) || numberValue(amount[1]) === null) {
    return { name: nutrient, value: null, unit: null, daily_value_percent: null };
  }
  let unit = amount[2] ? clean(amount[2]).toLowerCase() : null;
  if (unit === "calorie" || unit === "calories") unit = "kcal";
  const percentText = cells.find((value) => /%/.test(value));
  return {
    name: nutrient,
    value: numberValue(amount[1]),
    unit,
    daily_value_percent: percentText ? numberValue(percentText) : null,
  };
}

function nutritionFacts() {
  for (const root of labelRoots()) {
    const rows = query("#nutrition-facts [role='row']", root)
      .map(parseNutritionRow)
      .filter(Boolean);
    if (rows.length) return rows;
  }
  return [];
}

function factValue(facts, names) {
  const match = facts.find((fact) => names.includes(fact.name.toLowerCase()));
  return match ? match.value : null;
}

function servingSize() {
  const element = firstMatch("#nutrition-facts h6");
  const text =
    textOf(element) || textOf(query(".servings-container .serving-size")[0]);
  const match = text.match(/serving size\s+(.+)/i);
  if (!match) return { value: null, unit: null, ml: null };
  const amount = match[1].match(
    /(\d+(?:\.\d+)?)\s*(fl\s*oz|oz|ml|l|g|bottle|can|servings?)\b/i,
  );
  if (!amount) return { value: null, unit: clean(match[1]), ml: null };
  const unit = clean(amount[2]).toLowerCase().replace(/\s+/g, " ");
  return {
    value: numberValue(amount[1]),
    unit,
    ml: /fl\s*oz/i.test(unit) ? numberValue(amount[1]) * 29.5735 : null,
  };
}

function ingredientList() {
  const ingredientBlock = firstMatch("#ingredients");
  if (!ingredientBlock) return [];
  const value = textOf(ingredientBlock).replace(/\s*\.$/, "");
  return splitIngredients(value);
}

function caffeine() {
  const source = typeof document !== "undefined" ? textOf(document.body) : "";
  const match = source.match(/caffeine\s+([\d,.]+)\s*mg/i);
  return match ? numberValue(match[1]) : null;
}

function nutritionLabelImages() {
  const images = [];
  for (const image of query("#product-iframe img, .product-content-left img")) {
    const source = image.getAttribute("src") || image.getAttribute("data-src");
    const url = absoluteUrl(source);
    const signal = `${image.getAttribute("alt") || ""} ${source || ""}`.toLowerCase();
    if (url && /nutrition|facts|label/.test(signal)) {
      images.push({ url, content_type: "image", purpose: "nutrition_label" });
    }
  }
  return images;
}

const url = pageUrl();
const target = isTargetProduct();
const facts = target ? nutritionFacts() : [];
const productName = target ? "Mountain Dew Code Red" : null;

return {
  brand: target ? "Mountain Dew" : null,
  product_name: productName,
  product_line: target ? "Mountain Dew" : null,
  flavor: target ? "Code Red" : null,
  serving_size: target ? servingSize() : { value: null, unit: null, ml: null },
  caffeine_mg: target ? caffeine() : null,
  calories: target ? factValue(facts, ["calories"]) : null,
  sugar_g: target ? factValue(facts, ["total sugars", "sugars"]) : null,
  nutrition_facts: facts,
  ingredients: target ? ingredientList() : [],
  warnings: [],
  claims: [],
  scraper_assets: { nutrition_label_images: target ? nutritionLabelImages() : [] },
  source: { url, market: "US", scraped_at: new Date().toISOString() },
};
