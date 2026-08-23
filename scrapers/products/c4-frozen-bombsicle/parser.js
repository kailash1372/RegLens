/* C4 Performance Energy Frozen Bombsicle parser. */
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

function numberValue(value) {
  const match = String(value || "")
    .replace(/,/g, "")
    .match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
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

function productFromLd(html) {
  const scripts =
    html.match(/<script[^>]*application\/ld\+json[^>]*>[\s\S]*?<\/script>/gi) ||
    [];
  for (const script of scripts) {
    try {
      const value = JSON.parse(
        script
          .replace(/^[\s\S]*?>/, "")
          .replace(/<\/script>\s*$/i, "")
          .trim(),
      );
      const nodes = Array.isArray(value)
        ? value
        : value && value["@graph"]
          ? value["@graph"]
          : [value];
      const isFrozenPerformance = (node) =>
        node &&
        /c4\s+performance\s+energy/i.test(node.name || "") &&
        /frozen\s+bombsicle/i.test(node.name || "") &&
        !/ultimate|pre-?workout/i.test(node.name || "");
      const productGroup = nodes.find(isFrozenPerformance);
      if (productGroup) return productGroup;
      const variants = nodes.flatMap((node) =>
        Array.isArray(node && node.hasVariant) ? node.hasVariant : [],
      );
      const product = variants.find(isFrozenPerformance);
      if (product) return product;
    } catch (_) {}
  }
  return null;
}

function servingSize(text) {
  const raw = firstMatch(text, [
    /serving\s+size\s*:\s*((?:\d+(?:\.\d+)?)\s*(?:fl\.?\s*oz|oz|ml))/i,
  ]);
  if (!raw) return { value: null, unit: null, ml: null };
  const value = numberValue(raw);
  const unit = firstMatch(raw, [/(fl\.?\s*oz|oz|ml)/i]);
  if (value === null || !unit) return { value: null, unit: null, ml: null };
  if (/ml/i.test(unit)) return { value, unit: "ml", ml: value };
  return { value, unit: "fl oz", ml: Math.round(value * 29.5735) };
}

function nutritionLabelAssets(selectors, pageUrl) {
  const bestByImage = new Map();
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
      const parsedUrl = new URL(absoluteUrl);
      const imageKey = `${parsedUrl.origin}${parsedUrl.pathname}`;
      const requestedWidth = Number(parsedUrl.searchParams.get("width")) || 0;
      const existing = bestByImage.get(imageKey);
      if (!existing || requestedWidth > existing.width) {
        bestByImage.set(imageKey, { url: absoluteUrl, width: requestedWidth });
      }
    } catch (_) {}
  };
  selectors.forEach((selector) => {
    if (typeof document !== "undefined" && document.querySelectorAll) {
      document.querySelectorAll(selector).forEach(addImage);
    } else if (typeof $ === "function") {
      $(selector).each((_, element) => addImage(element));
    }
  });
  return Array.from(bestByImage.values()).map(({ url }) => ({
    url,
    content_type: "image",
    purpose: "nutrition_label",
  }));
}

const html = pageHtml();
const rawText = pageText();
const url =
  typeof location !== "undefined" && location.href
    ? location.href
    : typeof input !== "undefined" && input
      ? input.url
      : "";
const product = productFromLd(html);
const targetUrl = /\/products\/c4-performance-energy-frozen-bombsicle\/?(?:[?#].*)?$/i.test(
  url,
);
const scopedName = textFor(".product__info-container .product__title h1");
const fallbackName = firstMatch(rawText, [
  /^(C4\s+Performance\s+Energy[^\n]*Frozen\s+Bombsicle[^\n]*)$/im,
]);
const name =
  clean(product && product.name ? product.name : scopedName || fallbackName) ||
  null;
const isTargetProduct = Boolean(
  name &&
    /c4\s+performance\s+energy/i.test(name) &&
    /frozen\s+bombsicle/i.test(name) &&
    !/ultimate|pre-?workout/i.test(name) &&
    (targetUrl || !url),
);

// These selectors stay inside the active product section. The page also
// renders an Ultimate Frozen Bombsicle recommendation elsewhere in the DOM.
const productMainText = isTargetProduct ? textFor("#product-main") : "";
const productInfoText = isTargetProduct
  ? textFor(".product__info-container")
  : "";
const description = clean(product && product.description ? product.description : "");
const factText = clean([productMainText, description].filter(Boolean).join(" "));
const serving = servingSize(productInfoText);
const statedSugar = firstMatch(factText, [
  /total sugars?\s*:?\s*(\d[\d,]*(?:\.\d+)?)\s*g/i,
  /sugars?\s*:?\s*(\d[\d,]*(?:\.\d+)?)\s*g/i,
]);
const sugar = statedSugar
  ? numberValue(statedSugar)
  : /\bzero\s+sugar\b/i.test(factText)
    ? 0
    : null;
const warningText = isTargetProduct ? textFor("#panel-product-warning") : "";
const warnings = warningText ? [warningText] : [];
const claimPatterns = [
  ["Zero sugar", /\bzero\s+sugar\b/i],
  ["No artificial colors", /\bartificial\s+colors\b/i],
  ["Sharp focus", /\bsharp\s+focus\b/i],
  ["NSF Certified for Sport", /\bNSF\s+CERTIFIED\s+FOR\s+SPORT/i],
];
const claims = uniqueStrings(
  claimPatterns
    .filter(([, pattern]) => pattern.test(factText))
    .map(([label]) => label),
);

const productLine = name
  ? firstMatch(name, [/(C4\s+Performance\s+Energy)/i])
  : null;
const flavor = name ? firstMatch(name, [/(Frozen\s+Bombsicle)/i]) : null;
const scraperAssets = isTargetProduct
  ? nutritionLabelAssets(
      [
        'img[src*="C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_StylizedPDPs_Nutrition"]',
        'img[src*="C4BEV_3114_Digital_FrozenBomb_Wave0_Performance_BasicPDPs-NFP-Fun"]',
      ],
      url,
    )
  : [];

return {
  brand: isTargetProduct
    ? clean(product && product.brand && (product.brand.name || product.brand)) ||
      firstMatch(name || "", [/(C4)/i]) ||
      null
    : null,
  product_name: isTargetProduct ? name : null,
  product_line: isTargetProduct ? productLine : null,
  flavor: isTargetProduct ? flavor : null,
  serving_size: input.schema_seed
    ? { value: 0, unit: "fl oz", ml: 0 }
    : serving,
  caffeine_mg: isTargetProduct
    ? numberValue(
        firstMatch(factText, [
          /(\d[\d,]*(?:\.\d+)?)\s*mg\s*(?:of\s*)?caffeine/i,
          /caffeine[^\d]{0,30}(\d[\d,]*(?:\.\d+)?)\s*mg/i,
        ]),
      )
    : null,
  // The nutrition panel is an image on the first-party page.
  calories: null,
  sugar_g: sugar,
  nutrition_facts: [],
  ingredients: [],
  warnings,
  claims,
  source: {
    url: url || "",
    market: "US",
    scraped_at: new Date().toISOString(),
  },
  scraper_assets: { nutrition_label_images: scraperAssets },
};
