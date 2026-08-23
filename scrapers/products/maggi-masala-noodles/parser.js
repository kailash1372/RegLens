/* MAGGI 2-Minute Masala Noodles parser for Bright Data Scraper Studio. */
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
  const text = clean(value);
  if (!text || /^[<>]/.test(text)) return null;
  const match = text.replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function unitFromName(name) {
  const match = clean(name).match(/\((kcal|g|mg)\)/i);
  return match ? match[1].toLowerCase() : null;
}

function exactTargetUrl(url) {
  return /^https:\/\/(?:www\.)?maggi\.in\/en\/product\/maggi-2-minute-noodles-masala\/?(?:[?#].*)?$/i.test(
    url,
  );
}

function nutritionTable() {
  return allElements("table").find((table) => {
    const text = textOf(table);
    return /\bper 100g\b/i.test(text) && /\bper serve \(75g\)/i.test(text);
  });
}

function nutritionRows(table) {
  if (!table) return [];
  return allElements("tbody tr", table)
    .map((row) => allElements("th, td", row).map(textOf).filter(Boolean))
    .filter((cells) => cells.length >= 3)
    .map((cells) => ({
      name: cells[0],
      per100g: cells[1],
      perServing: cells[2],
      gda: cells[3] || "",
      rda: cells[4] || "",
    }));
}

function percentage(value) {
  const match = clean(value).match(/^(\d+(?:\.\d+)?)%$/);
  return match ? Number(match[1]) : null;
}

function nutritionFacts(rows) {
  const facts = [];
  for (const row of rows) {
    const unit = unitFromName(row.name);
    facts.push({
      name: `${row.name} (per 100g)`,
      value: numberValue(row.per100g),
      unit,
      daily_value_percent: null,
    });
    const gda = percentage(row.gda);
    const rda = percentage(row.rda);
    facts.push({
      name: `${row.name} (per serving: 75g)${rda !== null && gda === null ? "; RDA" : ""}`,
      value: numberValue(row.perServing),
      unit,
      daily_value_percent: gda !== null ? gda : rda,
    });
  }
  return facts;
}

function rowFor(rows, label) {
  return rows.find((row) => clean(row.name).toLowerCase() === label.toLowerCase());
}

const url = pageUrl();
const productName = textOf(allElements("h1")[0]);
const table = nutritionTable();
const rows = nutritionRows(table);
const isTargetProduct =
  exactTargetUrl(url) &&
  /^maggi®?\s*2-minute noodles$/i.test(productName) &&
  rows.length > 0;
const energy = rowFor(rows, "Energy (kcal)");
const totalSugars = rowFor(rows, "-Total Sugars(g)");

return {
  brand: isTargetProduct ? "MAGGI" : null,
  product_name: isTargetProduct ? productName : null,
  product_line: isTargetProduct ? "2-Minute Noodles" : null,
  // The official product header does not state Masala as a separate flavor field.
  flavor: null,
  serving_size: isTargetProduct ? { value: 75, unit: "g", ml: null } : { value: null, unit: null, ml: null },
  caffeine_mg: null,
  calories: isTargetProduct ? numberValue(energy && energy.perServing) : null,
  sugar_g: isTargetProduct ? numberValue(totalSugars && totalSugars.perServing) : null,
  nutrition_facts: isTargetProduct ? nutritionFacts(rows) : [],
  // This manufacturer page does not publish an ingredient statement as text.
  ingredients: [],
  warnings: [],
  claims: [],
  scraper_assets: { nutrition_label_images: [] },
  source: { url, market: "IN", scraped_at: new Date().toISOString() },
};
