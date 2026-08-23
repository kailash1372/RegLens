/* Bloom Nutrition Sparkling Energy, Raspberry Lemon variant parser. */
function clean(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
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
  if (unit === "oz" || unit === "ml") return unit;
  return null;
}

function firstMatch(text, patterns) {
  for (const pattern of patterns) {
    const match = String(text || "").match(pattern);
    if (match) return clean(match[1] || match[0]);
  }
  return null;
}

function uniqueStrings(values) {
  const seen = new Set();
  return values
    .map(clean)
    .filter((value) => {
      if (!value) return false;
      const key = value.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function splitIngredients(value) {
  const ingredients = [];
  let current = "";
  let depth = 0;
  for (const character of String(value || "")) {
    if (character === "(") depth += 1;
    if (character === ")") depth = Math.max(0, depth - 1);
    if (character === "," && depth === 0) {
      ingredients.push(current);
      current = "";
    } else {
      current += character;
    }
  }
  ingredients.push(current);
  return uniqueStrings(ingredients);
}

function pageUrl() {
  if (typeof location !== "undefined" && location.href) return location.href;
  if (typeof input !== "undefined" && input.url) return input.url;
  return "";
}

function absoluteUrl(value) {
  try {
    const resolved = new URL(String(value || ""), pageUrl());
    if (/bloomenergy_raspberrylemon_03\.png$/i.test(resolved.pathname)) {
      resolved.searchParams.set("width", "1600");
    }
    return resolved.href;
  } catch (error) {
    return null;
  }
}

function registeredDomain(value) {
  try {
    const parts = new URL(value).hostname.toLowerCase().replace(/\.$/, "").split(".");
    return parts.length >= 2 ? parts.slice(-2).join(".") : parts[0];
  } catch (error) {
    return null;
  }
}

function isFirstPartyUrl(value) {
  const pageDomain = registeredDomain(pageUrl());
  const assetDomain = registeredDomain(value);
  return Boolean(pageDomain && assetDomain && pageDomain === assetDomain);
}

function srcsetCandidate(value, requiredText) {
  return String(value || "")
    .split(",")
    .map((candidate) => candidate.trim().split(/\s+/)[0])
    .find((candidate) => candidate && candidate.toLowerCase().includes(requiredText)) || null;
}

function imageAttributes() {
  if (typeof $ === "function") {
    return $("img, source")
      .toArray()
      .map((element) => ({
        src: $(element).attr("src"),
        srcset: $(element).attr("srcset"),
        alt: $(element).attr("alt"),
      }));
  }
  if (typeof document !== "undefined" && typeof document.querySelectorAll === "function") {
    return Array.from(document.querySelectorAll("img, source")).map((element) => ({
      src: element.getAttribute("src"),
      srcset: element.getAttribute("srcset"),
      alt: element.getAttribute("alt"),
    }));
  }
  return [];
}

function nutritionLabelImages() {
  const filename = "bloomenergy_raspberrylemon_03.png";
  const urls = imageAttributes()
    .map((image) => {
      const src = String(image.src || "");
      const srcset = String(image.srcset || "");
      const candidate =
        (src.toLowerCase().includes(filename) && src) ||
        srcsetCandidate(srcset, filename);
      const url = candidate ? absoluteUrl(candidate) : null;
      return url && isFirstPartyUrl(url) ? url : null;
    })
    .filter(Boolean);
  return uniqueStrings(urls).map((url) => ({
    url,
    content_type: "image",
    purpose: "nutrition_label",
  }));
}

function pageHtml() {
  if (typeof document !== "undefined" && document.documentElement)
    return document.documentElement.outerHTML || "";
  if (typeof $ === "function" && typeof $.html === "function") return $.html();
  return "";
}

function metaContent(selector) {
  if (typeof $ === "function") return clean($(selector).first().attr("content"));
  if (typeof document !== "undefined") {
    const element = document.querySelector(selector);
    return clean(element && element.getAttribute("content"));
  }
  return "";
}

function productPageText() {
  const productSelectors = [
    "main .main-pdp__intro",
    "main .main-pdp__accordion-body",
    "main [data-product-content]",
  ];
  if (typeof $ === "function") {
    const scopedText = clean(
      productSelectors.map((selector) => $(selector).first().text()).join(" "),
    );
    return scopedText || clean($("main, [role='main']").first().text());
  }
  if (typeof document !== "undefined") {
    const texts = productSelectors
      .map((selector) => document.querySelector(selector))
      .filter(Boolean)
      .map((element) => element.innerText || element.textContent || "");
    const scopedText = clean(texts.join(" "));
    if (scopedText) return scopedText;
    const element = document.querySelector("main, [role='main']");
    return clean(element && (element.innerText || element.textContent));
  }
  return "";
}

function productHeading() {
  const selectors = ["main h1", "[role='main'] h1"];
  if (typeof $ === "function") {
    for (const selector of selectors) {
      const text = clean($(selector).first().text());
      if (text) return text;
    }
  }
  if (typeof document !== "undefined") {
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      const text = clean(element && (element.innerText || element.textContent));
      if (text) return text;
    }
  }
  return "";
}

function jsonLdNodes(html) {
  const scripts =
    String(html || "").match(
      /<script[^>]*application\/ld\+json[^>]*>[\s\S]*?<\/script>/gi,
    ) || [];
  const nodes = [];
  function visit(value) {
    if (!value || typeof value !== "object") return;
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    nodes.push(value);
    Object.values(value).forEach((child) => {
      if (child && typeof child === "object") visit(child);
    });
  }
  for (const script of scripts) {
    try {
      visit(
        JSON.parse(
          script
            .replace(/^[\s\S]*?>/, "")
            .replace(/<\/script>\s*$/i, "")
            .trim(),
        ),
      );
    } catch (error) {
      // Ignore malformed unrelated structured-data blocks.
    }
  }
  return nodes;
}

function isProduct(node) {
  const type = node && node["@type"];
  return type === "Product" || (Array.isArray(type) && type.includes("Product"));
}

function isRaspberryLemon(node) {
  const name = clean(node && node.name);
  return /\bsparkling energy\b/i.test(name) && /\braspberry lemon\b/i.test(name);
}

function exactProduct(nodes) {
  return nodes.find((node) => isProduct(node) && isRaspberryLemon(node)) || {};
}

function structuredValues(product, propertyNames) {
  const wanted = propertyNames.map((name) => name.toLowerCase());
  const values = [];
  for (const property of Array.isArray(product.additionalProperty)
    ? product.additionalProperty
    : []) {
    if (!property || !wanted.includes(clean(property.name).toLowerCase())) continue;
    values.push(clean(property.value));
  }
  for (const name of propertyNames) {
    if (product[name] !== undefined) values.push(clean(product[name]));
  }
  return values.filter(Boolean);
}

function explicitIngredients(text) {
  const ingredientText = firstMatch(text, [
    /\bingredients?\s*:\s*([\s\S]*?)(?=\b(?:warning|contains|allergen|directions?|nutrition)\b|$)/i,
  ]);
  return splitIngredients(ingredientText);
}

function explicitWarnings(text) {
  return uniqueStrings(
    String(text || "").match(
      /\b(?:warning|contains|not recommended|consult (?:a )?(?:physician|doctor))[\s\S]*?(?:[.!?](?=\s|$)|$)/gi,
    ) || [],
  );
}

const html = pageHtml();
const product = exactProduct(jsonLdNodes(html));
const mainText = productPageText();
const heading = productHeading();
const name = clean(product.name || heading) || null;
const isTargetProduct =
  isRaspberryLemon(product) ||
  (/\bsparkling energy\b/i.test(name || "") && /\braspberry lemon\b/i.test(name || ""));
const brand =
  clean(product.brand && (product.brand.name || product.brand)) ||
  metaContent("meta[property='og:site_name']") ||
  metaContent("meta[name='application-name']") ||
  null;
const productLine = firstMatch(name, [/\bsparkling energy\b/i]);
const flavor = firstMatch(name, [/\braspberry lemon\b/i]);
const structuredText = clean(
  [product.description, ...structuredValues(product, ["description"])]
    .filter(Boolean)
    .join(" "),
);
const factText = clean([structuredText, mainText].filter(Boolean).join(" "));
const url = pageUrl();

const servingRaw = firstMatch(mainText, [
  /\bserving size\b[\s\S]{0,60}?(\d+(?:\.\d+)?\s*(?:fl\.?\s*oz|oz|ml))\b/i,
]);
const servingUnit = servingRaw
  ? normalizedUnit(firstMatch(servingRaw, [/(fl\.?\s*oz|oz|ml)/i]))
  : null;
const caffeine = numberValue(
  firstMatch(factText, [
    /(\d[\d,]*(?:\.\d+)?)\s*mg\s*(?:of\s*)?(?:natural\s+)?caffeine\b/i,
    /\bcaffeine\b[^\d]{0,30}(\d[\d,]*(?:\.\d+)?)\s*mg\b/i,
  ]),
);
const calories = numberValue(
  firstMatch(factText, [
    /(\d[\d,]*(?:\.\d+)?)\s*[- ]?calorie\b/i,
    /\bcalories?\b[^\d]{0,20}(\d[\d,]*(?:\.\d+)?)/i,
  ]),
);
const statedSugar = firstMatch(factText, [
  /\btotal sugars?\b[^\d]{0,20}(\d[\d,]*(?:\.\d+)?)\s*g\b/i,
]);
const sugar = statedSugar ? numberValue(statedSugar) : /\bzero sugar\b/i.test(factText) ? 0 : null;
const claimPatterns = [
  /\bzero sugar\b/i,
  /\bnatural caffeine(?: from green coffee bean extract)?\b/i,
  /\bno artificial colors\b/i,
  /\bno artificial flavors\b/i,
  /\bno aspartame\b/i,
];
const claims = uniqueStrings(
  claimPatterns.map((pattern) => firstMatch(factText, [pattern])),
);

return {
  brand: isTargetProduct ? brand : null,
  product_name: isTargetProduct ? name : null,
  product_line: isTargetProduct ? productLine : null,
  flavor: isTargetProduct ? flavor : null,
  serving_size: input.schema_seed
    ? { value: 0, unit: "fl oz", ml: 0 }
    : {
        value: isTargetProduct ? numberValue(servingRaw) : null,
        unit: isTargetProduct ? servingUnit : null,
        ml:
          isTargetProduct && servingUnit === "ml"
            ? numberValue(servingRaw)
            : null,
      },
  caffeine_mg: isTargetProduct ? caffeine : null,
  calories: isTargetProduct ? calories : null,
  sugar_g: isTargetProduct ? sugar : null,
  nutrition_facts: [],
  ingredients: isTargetProduct ? explicitIngredients(mainText) : [],
  warnings: isTargetProduct ? explicitWarnings(mainText) : [],
  claims: isTargetProduct ? claims : [],
  scraper_assets: {
    nutrition_label_images: isTargetProduct ? nutritionLabelImages() : [],
  },
  source: {
    url,
    market: "US",
    scraped_at: new Date().toISOString(),
  },
};
