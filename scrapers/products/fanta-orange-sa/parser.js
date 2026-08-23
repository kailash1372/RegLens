/* Fanta Orange, Saudi Arabia parser. */
function clean(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
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

function exactTargetUrl(url) {
  return /^https:\/\/(?:www\.)?coca-cola\.com\/sa\/en\/brands\/fanta\/?(?:[?#].*)?$/i.test(
    url,
  );
}

function query(selector, root) {
  const container = root || (typeof document !== "undefined" ? document : null);
  if (!container || typeof container.querySelectorAll !== "function") return [];
  return Array.from(container.querySelectorAll(selector));
}

function textOf(element) {
  return clean(element && (element.textContent || element.innerText));
}

function targetScope() {
  const headings = query("h1, h2, h3, h4");
  const heading = headings.find((item) => /^fanta orange$/i.test(textOf(item)));
  if (!heading) return null;
  let node = heading;
  while (node && node !== document) {
    if (String(node.className || "").split(/\s+/).includes("product-information")) {
      return node;
    }
    node = node.parentElement;
  }
  return heading.parentElement;
}

function absoluteUrl(value) {
  try {
    return new URL(String(value || ""), pageUrl()).href;
  } catch (error) {
    return null;
  }
}

function registeredDomain(value) {
  try {
    const parts = new URL(value).hostname.toLowerCase().split(".");
    return parts.length > 1 ? parts.slice(-2).join(".") : parts[0];
  } catch (error) {
    return null;
  }
}

function nutritionLabelImages(scope) {
  const pageDomain = registeredDomain(pageUrl());
  const urls = [];
  for (const image of query("img, source", scope)) {
    const source = image.getAttribute("src") || image.getAttribute("srcset") || "";
    const candidate = source.split(",")[0].trim().split(/\s+/)[0];
    const signal = `${image.getAttribute("alt") || ""} ${source}`.toLowerCase();
    const url = absoluteUrl(candidate);
    if (
      url &&
      registeredDomain(url) === pageDomain &&
      /nutrition|facts|label/.test(signal)
    ) {
      urls.push(url);
    }
  }
  return uniqueStrings(urls).map((url) => ({
    url,
    content_type: "image",
    purpose: "nutrition_label",
  }));
}

function parseRow(value) {
  const match = clean(value).match(
    /^(Energy|Calories|Total Fat|Fat|Saturated Fat|Trans Fat|Cholesterol|Total Carbohydrates|Carbohydrate|Dietary Fibers|Fiber|Total Sugars|Sugars|Added Sugars|Sodium|Protein)\s*:?\s*(<?\d[\d,.]*)\s*(kcal|calories?|g|mg|mcg|µg)?\s*(?:(\d[\d,.]*)\s*%)?/i,
  );
  if (!match) return null;
  let unit = match[3] ? clean(match[3]).toLowerCase() : null;
  if (unit === "calorie" || unit === "calories") unit = "kcal";
  return {
    name: match[1],
    value: numberValue(match[2]),
    unit,
    daily_value_percent: match[4] ? numberValue(match[4]) : null,
  };
}

function nutritionFacts(scope) {
  return query(".nutritional-information__row", scope)
    .map((row) => parseRow(textOf(row)))
    .filter(Boolean);
}

function textMetric(facts, names) {
  const wanted = names.map((name) => name.toLowerCase());
  const match = facts.find((item) => wanted.includes(item.name.toLowerCase()));
  return match ? match.value : null;
}

function ingredientText(scope) {
  const paragraph = query("p", scope).find((item) => /\bingredients?\s*:/i.test(textOf(item)));
  if (!paragraph) return [];
  const match = textOf(paragraph).match(/\bingredients?\s*:?\s*([\s\S]*?)(?=\.\s*\*|$)/i);
  return splitIngredients(match ? match[1].replace(/[.]\s*$/, "") : "");
}

function warningText(scope) {
  const match = textOf(scope).match(/\*This material\b[\s\S]*?(?:[.!?](?=\s|$)|$)/i);
  return match ? [clean(match[0])] : [];
}

const url = pageUrl();
const scope = targetScope();
const name = scope ? textOf(query("h1, h2, h3, h4", scope)[0]) : "";
const isTargetProduct = exactTargetUrl(url) && /^fanta orange$/i.test(name);
const facts = isTargetProduct ? nutritionFacts(scope) : [];
const scopeText = textOf(scope);
const servingMatch = scopeText.match(/\bper\s+(-?\d+(?:\.\d+)?)\s*(ml|mL|l|g)\b/i);
const servingValue = servingMatch ? numberValue(servingMatch[1]) : null;
const hasValidServing = servingValue !== null && servingValue > 0;
const serving = servingMatch && hasValidServing
  ? { value: servingValue, unit: servingMatch[2].toLowerCase(), ml: /ml/i.test(servingMatch[2]) ? servingValue : null }
  : { value: null, unit: null, ml: null };
const brandElement = typeof document !== "undefined" ? document.querySelector("meta[name='brand']") : null;
const brand = clean(brandElement && brandElement.getAttribute("content")) || null;
const calories = textMetric(facts, ["Energy", "Calories"]);
const sugars = textMetric(facts, ["Total Sugars", "Sugars"]);
const productLine = name.match(/\bfanta\b/i);
const flavor = name.match(/\borange\b/i);

return {
  brand: isTargetProduct ? brand || (productLine ? productLine[0] : null) : null,
  product_name: isTargetProduct ? name : null,
  product_line: isTargetProduct && productLine ? productLine[0] : null,
  flavor: isTargetProduct && flavor ? flavor[0] : null,
  serving_size: isTargetProduct ? serving : { value: null, unit: null, ml: null },
  caffeine_mg: null,
  calories: isTargetProduct ? calories : null,
  sugar_g: isTargetProduct ? sugars : null,
  nutrition_facts: facts,
  ingredients: isTargetProduct ? ingredientText(scope) : [],
  warnings: isTargetProduct ? warningText(scope) : [],
  claims: [],
  scraper_assets: {
    nutrition_label_images: isTargetProduct ? nutritionLabelImages(scope) : [],
  },
  source: {
    url,
    market: "SA",
    scraped_at: new Date().toISOString(),
  },
};
