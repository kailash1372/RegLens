/* REIGN Orange Dreamsicle parser for Bright Data Scraper Studio. */
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

function textFor(selector) {
  if (typeof document !== "undefined" && document.querySelector) {
    const element = document.querySelector(selector);
    if (element) return clean(element.innerText || element.textContent);
  }
  if (typeof $ === "function") return clean($(selector).first().text());
  return "";
}

function attributeFor(selector, name) {
  if (typeof document !== "undefined" && document.querySelector) {
    const element = document.querySelector(selector);
    if (element && element.getAttribute) return clean(element.getAttribute(name));
  }
  if (typeof $ === "function") return clean($(selector).first().attr(name));
  return "";
}

function allElements(selector) {
  if (typeof document !== "undefined" && document.querySelectorAll) {
    return Array.from(document.querySelectorAll(selector));
  }
  if (typeof $ === "function") return $(selector).toArray();
  return [];
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

function numberValue(value) {
  const match = String(value || "")
    .replace(/,/g, "")
    .match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function exactTargetUrl(url) {
  return /^https:\/\/(?:www\.)?reignbodyfuel\.com\/en-us\/products\/orange-dreamsicle\/?(?:[?#].*)?$/i.test(
    url,
  );
}

function jsonLdProduct() {
  const scripts = allElements('script[type="application/ld+json"]');
  for (const script of scripts) {
    try {
      const value = JSON.parse(script.textContent || "");
      const products = Array.isArray(value) ? value : [value];
      const product = products.find((candidate) => {
        const type = candidate && candidate["@type"];
        return (
          (type === "Product" || (Array.isArray(type) && type.includes("Product"))) &&
          /^orange dreamsicle$/i.test(clean(candidate.name))
        );
      });
      if (product) return product;
    } catch (error) {
      // Ignore unrelated malformed JSON-LD blocks.
    }
  }
  return null;
}

function advantageTitle(pattern) {
  return allElements(".rtb-title")
    .map((element) => clean(element.innerText || element.textContent))
    .find((title) => pattern.test(title));
}

const url = pageUrl();
const productName = textFor("#product-detail-flavor.product-name");
const brand = attributeFor("#product-detail-flavor.product-name", "data-category");
const product = jsonLdProduct();
const hasExactName =
  /^orange dreamsicle$/i.test(productName) &&
  /^orange dreamsicle$/i.test(clean(product && product.name));
const isTargetProduct = exactTargetUrl(url) && hasExactName;
const caffeineTitle = advantageTitle(/\bcaffeine\b/i);
const productLine = clean(product && product.brand && (product.brand.name || product.brand));
const claims = uniqueStrings(
  allElements(".rtb-title")
    .map((element) => clean(element.innerText || element.textContent))
    .filter((title) => /^(zero sugar|bcaas|vitamins(?:\s+b3,?\s*b6,?\s*b12)?|reduce fatigue)$/i.test(title)),
);

return {
  brand: isTargetProduct ? brand || null : null,
  product_name: isTargetProduct ? productName : null,
  product_line: isTargetProduct ? productLine || null : null,
  flavor: isTargetProduct ? productName : null,
  serving_size: { value: null, unit: null, ml: null },
  caffeine_mg: isTargetProduct ? numberValue(caffeineTitle) : null,
  // The manufacturer page makes a Zero Sugar claim but does not publish a
  // structured Nutrition Facts label, so scalar nutrition remains unverified.
  calories: null,
  sugar_g: null,
  nutrition_facts: [],
  ingredients: [],
  // No product- or product-line-attributable warning is rendered on this page.
  warnings: [],
  claims: isTargetProduct ? claims : [],
  scraper_assets: { nutrition_label_images: [] },
  source: {
    url,
    market: "US",
    scraped_at: new Date().toISOString(),
  },
};
