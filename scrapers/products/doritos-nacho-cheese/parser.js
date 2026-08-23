/* DORITOS Nacho Cheese Flavored Tortilla Chips parser. */
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

function absoluteUrl(value, base) {
  try {
    return new URL(String(value || ""), base || pageUrl()).href;
  } catch (error) {
    return null;
  }
}

function targetProduct() {
  const scope = query("#product-scope")[0];
  const name = clean(
    (scope && scope.getAttribute("data-name")) || textOf(query(".single-product__title h1")[0]),
  );
  return /nacho cheese flavored tortilla chips/i.test(name);
}

function smartLabelFrame() {
  return query("#prod-nutrition iframe, .product-nutrition iframe")[0] || null;
}

function frameRoots() {
  const frame = smartLabelFrame();
  const roots = [];
  try {
    if (frame && frame.contentDocument) roots.push(frame.contentDocument);
    if (frame && frame.contentWindow && frame.contentWindow.document) {
      roots.push(frame.contentWindow.document);
    }
  } catch (error) {
    // Cross-origin SmartLabel frames may not expose their document. In that
    // case the canonical fields remain empty instead of being guessed.
  }
  return roots;
}

function firstFrameMatch(selector) {
  for (const root of frameRoots()) {
    const match = query(selector, root)[0];
    if (match) return match;
  }
  return null;
}

function parseNutritionRow(row) {
  const spans = query("span", row);
  const name = textOf(spans[0]);
  if (!name || /% daily value/i.test(name)) return null;
  const amountText = spans
    .slice(1)
    .map(textOf)
    .find((value) => /\d/.test(value) && !/%/.test(value)) || "";
  const amount = amountText.match(/<?\s*([\d,.]+)\s*(kcal|calories?|g|mg|mcg|µg)?/i);
  const percentText = spans.slice(2).map(textOf).find((value) => /%/.test(value));
  const nameAmount = name.match(/(?:^|\s)(<?\s*[\d,.]+)\s*(kcal|calories?|g|mg|mcg|µg)\b/i);
  const parsedAmount = amount || nameAmount;
  let unit = parsedAmount && parsedAmount[2] ? clean(parsedAmount[2]).toLowerCase() : null;
  if (unit === "calorie" || unit === "calories") unit = "kcal";
  return {
    name,
    value: parsedAmount && !/<\s*/.test(parsedAmount[0]) ? numberValue(parsedAmount[1]) : null,
    unit,
    daily_value_percent: percentText ? numberValue(percentText) : null,
  };
}

function nutritionFacts() {
  const root = frameRoots()[0];
  if (!root) return [];
  return query(".nfp__values > .nfp__row", root)
    .map(parseNutritionRow)
    .filter(Boolean);
}

function factValue(facts, names) {
  const match = facts.find((fact) => names.includes(fact.name.toLowerCase()));
  return match ? match.value : null;
}

function servingSize() {
  const header = firstFrameMatch(".nfp__header");
  const text = textOf(header);
  const grams = text.match(/\((\d+(?:\.\d+)?)\s*g\)/i);
  if (grams) return { value: numberValue(grams[1]), unit: "g", ml: null };
  const amount = text.match(/serving size\s+(.+)/i);
  return amount
    ? { value: null, unit: clean(amount[1]), ml: null }
    : { value: null, unit: null, ml: null };
}

function ingredients() {
  const root = frameRoots()[0];
  if (!root) return [];
  return uniqueStrings(
    query("#ingredient-list .list-title", root)
      .map(textOf)
      .filter((value) => !/^and less than \d+% of:?$/i.test(value)),
  );
}

function nutritionLabelImages() {
  const frame = smartLabelFrame();
  if (!frame) return [];
  const frameUrl = absoluteUrl(frame.getAttribute("src"));
  if (!frameUrl) return [];
  for (const root of frameRoots()) {
    const images = query("img", root)
      .map((image) => absoluteUrl(image.getAttribute("src"), frameUrl))
      .filter(Boolean)
      .filter((url) => /nutrition|fact|label/i.test(url));
    if (images.length) {
      return uniqueStrings(images).map((url) => ({
        url,
        content_type: "image",
        purpose: "nutrition_label",
      }));
    }
  }
  return [];
}

const url = pageUrl();
const target = targetProduct();
const facts = target ? nutritionFacts() : [];
const scope = query("#product-scope")[0];
const sourceName = scope && scope.getAttribute("data-name");

return {
  brand: target ? "DORITOS" : null,
  product_name: target ? clean(sourceName) || "DORITOS Nacho Cheese Flavored Tortilla Chips" : null,
  product_line: target ? "DORITOS" : null,
  flavor: target ? "Nacho Cheese" : null,
  serving_size: target ? servingSize() : { value: null, unit: null, ml: null },
  caffeine_mg: null,
  calories: target ? factValue(facts, ["calories"]) : null,
  sugar_g: target ? factValue(facts, ["total sugars", "sugars"]) : null,
  nutrition_facts: facts,
  ingredients: target ? ingredients() : [],
  warnings: [],
  claims: [],
  scraper_assets: { nutrition_label_images: target ? nutritionLabelImages() : [] },
  source: { url, market: "US", scraped_at: new Date().toISOString() },
};
