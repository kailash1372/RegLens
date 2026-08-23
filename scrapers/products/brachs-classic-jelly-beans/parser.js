/* Brach's Classic Jelly Beans parser. */
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
  return /^https:\/\/(?:www\.)?brachs\.com\/products\/easter\/classic-jelly-beans\/?(?:[?#].*)?$/i.test(
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

function fact(text, labels) {
  const labelPattern = labels.join("|");
  const match = String(text || "").match(
    new RegExp(`(?:^|\\s)(?:${labelPattern})\\s*:?[\\s]+(<?\\d[\\d,.]*)\\s*(kcal|calories?|g|mg)?`, "i"),
  );
  if (!match) return null;
  return {
    value: numberValue(match[1]),
    unit: match[2] ? clean(match[2]).toLowerCase().replace("calories", "kcal").replace("calorie", "kcal") : null,
  };
}

function nutritionFacts(text) {
  const definitions = [
    ["Calories", ["Calories"]],
    ["Fat", ["Fat"]],
    ["Sugars", ["Sugars"]],
    ["Sodium", ["Sodium"]],
  ];
  return definitions
    .map(([name, labels]) => {
      const parsed = fact(text, labels);
      return parsed && parsed.value !== null
        ? { name, value: parsed.value, unit: parsed.unit, daily_value_percent: null }
        : null;
    })
    .filter(Boolean);
}

function ingredients(scope) {
  const block = query(".product-detail__ingredients .collapse", scope)[0];
  const value = textOf(block).replace(/^ingredients?\s*:?[\s]*/i, "");
  return splitIngredients(value.replace(/[.]\s*$/, ""));
}

const url = pageUrl();
const scope =
  query(".product-detail__bottom")[0] ||
  query("main, [role='main']")[0] ||
  (typeof document !== "undefined" ? document.body : null);
const name = textOf(query("h1, h2, h3", scope)[0]);
const isTargetProduct = exactTargetUrl(url) && /^classic jelly beans$/i.test(name);
const mainText = textOf(scope);
const nutritionBlock = textOf(query(".product-detail__nutrition .collapse", scope)[0]);
const servingMatch = nutritionBlock.match(
  /serving size\s*:?\s*(\d+(?:\.\d+)?)\s*(pieces?|servings?|g|mg|ml|oz)\b/i,
);
const facts = nutritionFacts(nutritionBlock);
const calories = fact(nutritionBlock, ["Calories"]);
const sugar = fact(nutritionBlock, ["Sugars"]);
const title = typeof document !== "undefined" ? clean(document.title) : "";
const brandMatch = title.match(/\b(Brach['’]?s)\b/i);
const facilityWarning = mainText.match(
  /This product was manufactured in a facility where[^.]+\./i,
);

return {
  brand: isTargetProduct ? (brandMatch ? brandMatch[1] : null) : null,
  product_name: isTargetProduct ? name : null,
  product_line: isTargetProduct ? name : null,
  flavor: null,
  serving_size: {
    value: isTargetProduct && servingMatch ? numberValue(servingMatch[1]) : null,
    unit: isTargetProduct && servingMatch ? clean(servingMatch[2]) : null,
    ml: null,
  },
  caffeine_mg: null,
  calories: isTargetProduct && calories ? calories.value : null,
  sugar_g: isTargetProduct && sugar ? sugar.value : null,
  nutrition_facts: isTargetProduct ? facts : [],
  ingredients: isTargetProduct ? ingredients(scope) : [],
  warnings: isTargetProduct ? uniqueStrings([facilityWarning && facilityWarning[0]]) : [],
  claims: [],
  scraper_assets: {
    nutrition_label_images: isTargetProduct ? nutritionLabelImages(scope) : [],
  },
  source: {
    url,
    market: "US",
    scraped_at: new Date().toISOString(),
  },
};
