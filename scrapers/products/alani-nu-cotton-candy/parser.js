const cleanText = (value) => {
  const text = value ? String(value).replace(/\s+/g, " ").trim() : "";
  return text || null;
};

const extractNumber = (text) => {
  const match = cleanText(text)?.match(/-?\d+(?:\.\d+)?/);
  return match ? Number.parseFloat(match[0]) : null;
};

const extractUnit = (text) => {
  const match = cleanText(text)?.match(
    /-?\d+(?:\.\d+)?\s*(mcg|mg|g|kg|ml|l|fl\s*oz)\b/i,
  );
  return match ? match[1].replace(/\s+/g, " ").toLowerCase() : null;
};

const uniqueStrings = (values) => {
  const seen = new Set();

  return values
    .map((value) => cleanText(value))
    .filter((value) => {
      if (!value) return false;

      const key = value.toLowerCase();
      if (seen.has(key)) return false;

      seen.add(key);
      return true;
    });
};

const absoluteUrl = (value) => {
  const candidate = cleanText(value)?.replace(/&amp;/g, "&");
  if (!candidate) return null;

  try {
    return new URL(candidate, String(input.url)).href;
  } catch (error) {
    return null;
  }
};

const splitIngredients = (text) => {
  if (!text) return [];

  const ingredients = [];
  let current = "";
  let parenthesisDepth = 0;

  for (const character of text) {
    if (character === "(") parenthesisDepth += 1;
    if (character === ")") {
      parenthesisDepth = Math.max(0, parenthesisDepth - 1);
    }

    if (character === "," && parenthesisDepth === 0) {
      ingredients.push(current.trim());
      current = "";
    } else {
      current += character;
    }
  }

  ingredients.push(current.trim());
  return uniqueStrings(ingredients);
};

const findProductJsonLd = (value) => {
  if (Array.isArray(value)) {
    for (const item of value) {
      const product = findProductJsonLd(item);
      if (product) return product;
    }
    return null;
  }

  if (!value || typeof value !== "object") return null;

  const types = Array.isArray(value["@type"])
    ? value["@type"]
    : [value["@type"]];

  if (types.some((type) => String(type).toLowerCase() === "product")) {
    return value;
  }

  return findProductJsonLd(value["@graph"]);
};

let productJsonLd = null;

$("script[type=\"application/ld+json\"]").each((_, element) => {
  if (productJsonLd) return;

  try {
    productJsonLd = findProductJsonLd(JSON.parse($(element).text()));
  } catch (error) {
    // Ignore unrelated or invalid JSON-LD blocks.
  }
});

const jsonLdBrand = productJsonLd?.brand;
const brand =
  cleanText(typeof jsonLdBrand === "object" ? jsonLdBrand.name : jsonLdBrand) ||
  cleanText($("meta[property=\"og:site_name\"]").attr("content"));

const product_name =
  cleanText(productJsonLd?.name) ||
  cleanText($(".product-title").first().text_sane());

const product_line = cleanText($(".product__category").first().text_sane());

const explicitFlavor = cleanText(
  $(".product__flavor, [data-flavor]").first().text_sane(),
);
const flavorMatch = product_name?.match(
  /^(.+?)\s+energy(?:\s+drink)?(?:\s*-\s*.+)?$/i,
);
const flavor = explicitFlavor || cleanText(flavorMatch?.[1]) || product_name;

const servingSizeText = cleanText(
  $(".product-benefits_cel__nutrition-info td:nth-child(2)")
    .first()
    .text_sane(),
);
const servingSizeMatch = servingSizeText?.match(
  /([\d.]+)\s*fl\s*oz\s*\(([\d.]+)\s*mL\)/i,
);
const serving_size = input.schema_seed
  ? { value: 0, unit: "fl oz", ml: 0 }
  : {
      value: servingSizeMatch ? Number.parseFloat(servingSizeMatch[1]) : null,
      unit: servingSizeMatch ? "fl oz" : null,
      ml: servingSizeMatch ? Number.parseFloat(servingSizeMatch[2]) : null,
    };

const detailsText = cleanText(
  $(".product-benefits_cel__panel-details-wrapper").text(),
);
const caffeineMatch = detailsText?.match(/(\d+(?:\.\d+)?)\s*mg\s+caffeine/i);
const caffeine_mg = caffeineMatch ? Number.parseFloat(caffeineMatch[1]) : null;

const nutrition_facts = $(".product-benefits_cel__nutrition-table tbody tr")
  .toArray()
  .map((row) => {
    const cells = $(row).find("td");
    const name = cleanText(cells.eq(0).text_sane());

    if (!name || /per serving|% daily value/i.test(name)) return null;

    const valueText = cleanText(cells.eq(1).text_sane());
    const dailyValueText = cleanText(cells.eq(2).text_sane());

    return {
      name,
      value: extractNumber(valueText || name),
      unit: extractUnit(valueText || name),
      daily_value_percent: extractNumber(dailyValueText),
    };
  })
  .filter(Boolean)
  .filter(
    (item, index, items) =>
      items.findIndex(
        (candidate) => candidate.name.toLowerCase() === item.name.toLowerCase(),
      ) === index,
  );

const findNutrient = (name) =>
  nutrition_facts.find(
    (item) => item.name.toLowerCase() === name.toLowerCase(),
  );

const calories = findNutrient("Calories")?.value ?? null;
const sugar_g = findNutrient("Total Sugars")?.value ?? null;

const ingredientsAndWarnings = cleanText(
  $(".product-benefits_cel__nutrition-ingredients").text_sane(),
);
const ingredientsMatch = ingredientsAndWarnings?.match(
  /Ingredients:\s*([\s\S]*?)(?=\bContains:|\bNot recommended\b|$)/i,
);
const ingredients = splitIngredients(ingredientsMatch?.[1]);

const containsMatch = ingredientsAndWarnings?.match(
  /Contains:\s*([\s\S]*?)(?=\bNot recommended\b|$)/i,
);
const recommendationMatch = ingredientsAndWarnings?.match(
  /Not recommended[\s\S]*?(?:[.!?](?=\s|$)|$)/i,
);
const warnings = uniqueStrings([
  containsMatch ? `Contains: ${cleanText(containsMatch[1])}` : null,
  recommendationMatch?.[0],
]);

const claims = uniqueStrings(
  $(".product-benefits_cel__benefit-item p")
    .toArray()
    .map((element) => $(element).text_sane()),
);

const nutritionLabelImage = absoluteUrl(
  $('img[src*="Stretch_AN-Website-12oz-PDP-CTC-03_V1.png"]')
    .first()
    .attr("src"),
);
const scraper_assets = {
  nutrition_label_images: nutritionLabelImage
    ? [
        {
          url: nutritionLabelImage,
          content_type: "image",
          purpose: "nutrition_label",
        },
      ]
    : [],
};

const source = {
  url: String(input.url),
  market: "US",
  scraped_at: new Date().toISOString(),
};

return {
  brand,
  product_name,
  product_line,
  flavor,
  serving_size,
  caffeine_mg,
  calories,
  sugar_g,
  nutrition_facts,
  ingredients,
  warnings,
  claims,
  source,
  scraper_assets,
};
