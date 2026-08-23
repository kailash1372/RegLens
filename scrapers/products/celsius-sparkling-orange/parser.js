/* CELSIUS Sparkling Orange parser. */
function pageHtml() {
  if (typeof document !== "undefined" && document.documentElement)
    return document.documentElement.outerHTML || "";
  if (typeof $ === "function" && typeof $.html === "function") return $.html();
  return "";
}

function pageText() {
  if (typeof document !== "undefined" && document.body)
    return document.body.innerText || document.body.textContent || "";
  if (typeof $ === "function") return $("body").text() || "";
  return pageHtml().replace(/<[^>]+>/g, " ");
}

function clean(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function textFor(selector) {
  if (typeof $ === "function") {
    const selection = $(selector);
    const first =
      selection && typeof selection.first === "function"
        ? selection.first()
        : selection;
    if (first && typeof first.text_sane === "function")
      return clean(first.text_sane());
    if (first && typeof first.text === "function") return clean(first.text());
  }
  if (typeof document !== "undefined") {
    const element = document.querySelector(selector);
    if (element) return clean(element.innerText || element.textContent || "");
  }
  return "";
}

function firstMatch(text, patterns) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return match[1] || match[0];
  }
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

function attribute(element, name) {
  if (element && typeof element.getAttribute === "function")
    return element.getAttribute(name) || "";
  if (typeof $ === "function") {
    const value = $(element).attr(name);
    return value || "";
  }
  return "";
}

function nutritionLabelAssets(selectors, pageUrl) {
  const urls = [];
  const seen = new Set();
  const addImage = (element) => {
    const candidates = [];
    const src = attribute(element, "src").replace(/&amp;/g, "&");
    if (src) candidates.push({ url: src, width: 0 });
    const srcset = attribute(element, "srcset");
    srcset.split(",").forEach((entry) => {
      const match = entry.trim().match(/^(\S+)(?:\s+(\d+(?:\.\d+)?)w)?$/i);
      if (match) {
        candidates.push({
          url: match[1].replace(/&amp;/g, "&"),
          width: match[2] ? Number(match[2]) : 0,
        });
      }
    });
    candidates.sort((left, right) => right.width - left.width);
    if (!candidates[0]) return;
    try {
      const absoluteUrl = new URL(candidates[0].url, pageUrl).href;
      if (seen.has(absoluteUrl)) return;
      seen.add(absoluteUrl);
      urls.push({ url: absoluteUrl, content_type: "image", purpose: "nutrition_label" });
    } catch (_) {}
  };
  selectors.forEach((selector) => {
    if (typeof document !== "undefined" && document.querySelectorAll) {
      document.querySelectorAll(selector).forEach(addImage);
    } else if (typeof $ === "function") {
      $(selector).each((_, element) => addImage(element));
    }
  });
  return urls;
}

const html = pageHtml();
const rawText = pageText();
const url =
  typeof location !== "undefined" && location.href
    ? location.href
    : typeof input !== "undefined" && input
      ? input.url
      : "";

// The product header has separate mobile and desktop copies. Selecting the
// first desktop product node avoids the flavor navigation and Essentials links.
const productName =
  textFor(".single-products .product-header .desktop .top .left h3") ||
  textFor(".single-products .product-header .mobile .top-info h3") ||
  firstMatch(rawText, [/^Sparkling Orange$/im]);
const productDescription =
  textFor(
    ".single-products .product-header .desktop .top .left .product-description",
  ) ||
  textFor(
    ".single-products .product-header .mobile .top-info .product-description",
  );
const brandText = textFor(".single-products .product-header .power-words");
const targetUrl = /\/products\/celsius\/sparkling-orange\/?(?:[?#].*)?$/i.test(
  url,
);
const isTargetProduct = Boolean(
  productName &&
    /sparkling\s+orange/i.test(productName) &&
    !/essentials|270\s*mg/i.test(`${url} ${productName}`),
);
const target = targetUrl && isTargetProduct;
const claims = uniqueStrings(
  target && /clinically\s+proven\s+ingredients/i.test(productDescription)
    ? ["Clinically proven ingredients"]
    : [],
);
const brand = firstMatch(brandText, [/(CELSIUS)/i]);
const flavor = firstMatch(productName || "", [/(Orange)/i]);
const productLine =
  firstMatch(productName || "", [/(CELSIUS\s+Sparkling)/i]) ||
  firstMatch(productDescription || "", [/(CELSIUS\s+Sparkling)/i]) ||
  firstMatch(brandText || "", [/(CELSIUS\s+Sparkling)/i]);
const scraperAssets = target
  ? nutritionLabelAssets(['img[src*="/Orange-supp.png"]'], url)
  : [];

return {
  brand: target ? (brand ? brand.toUpperCase() : null) : null,
  product_name: target ? clean(productName) : null,
  product_line: target ? productLine : null,
  flavor: target ? flavor : null,
  // Serving size and nutrition are printed only on the label image.
  serving_size: input.schema_seed
    ? { value: 0, unit: "fl oz", ml: 0 }
    : { value: null, unit: null, ml: null },
  caffeine_mg: null,
  calories: null,
  sugar_g: null,
  nutrition_facts: [],
  ingredients: [],
  warnings: [],
  claims,
  source: {
    url: url || "",
    market: "US",
    scraped_at: new Date().toISOString(),
  },
  scraper_assets: { nutrition_label_images: scraperAssets },
};
