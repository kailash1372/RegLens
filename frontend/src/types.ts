export interface NutritionFact {
  name: string;
  value: number | null;
  unit: string | null;
  daily_value_percent: number | null;
}

export interface ServingSize {
  value: number | null;
  unit: string | null;
  ml: number | null;
}

export interface ProductSource {
  url: string;
  market: string;
  scraped_at: string;
}

export interface ScraperAsset {
  url: string;
  content_type: string;
  purpose: string;
}

export interface ScraperAssets {
  nutrition_label_images: ScraperAsset[];
}

export interface ProductScraperAssets {
  product_id: string;
  scraper_assets: ScraperAssets;
  updated_at: string | null;
}

export interface RegulatoryRule {
  id?: string;
  source_id?: string;
  authority?: string;
  jurisdiction?: string;
  title?: string;
  source_url?: string;
  evidence_excerpt?: string;
  verification_status?: "VERIFIED" | "SUPPORTED" | "NEEDS_REVIEW" | string;
  retrieved_at?: string;
}

export interface RegulatoryFinding {
  id?: string;
  rule_id?: string;
  finding_type?: string;
  status?: string;
  explanation?: string;
  explanation_template?: string;
  observed_value?: number | null;
  threshold_value?: number | null;
  difference?: number | null;
  unit?: string | null;
  rule?: RegulatoryRule;
}

export interface RecallRecord {
  id: string;
  authority: string;
  jurisdiction: string;
  product_description: string;
  brand_manufacturer?: string | null;
  reason: string;
  classification_status?: string | null;
  event_date?: string | null;
  source_url: string;
  retrieved_at?: string;
  match_type?: "exact_product" | "product_family" | "brand" | "no_match" | string;
}

export interface ProductSnapshot {
  brand: string | null;
  product_name: string | null;
  product_line: string | null;
  flavor: string | null;
  serving_size: ServingSize;
  caffeine_mg: number | null;
  calories: number | null;
  sugar_g: number | null;
  nutrition_facts: NutritionFact[];
  ingredients: string[];
  warnings: string[];
  claims: string[];
  source: ProductSource;
}

export interface ProductSummary {
  id: string;
  display_name: string;
  manufacturer: string;
  category: string;
  canonical_family: string | null;
  market: string;
  caffeine_mg: number | null;
  sugar_g: number | null;
  refreshed_at: string | null;
}

export interface ProductRecord {
  id: string;
  display_name: string;
  manufacturer: string;
  category: string;
  canonical_family: string | null;
  market: string;
  active_snapshot: ProductSnapshot | null;
  regulatory_findings?: RegulatoryFinding[];
  findings?: RegulatoryFinding[];
  recalls?: RecallRecord[];
}

export interface ScraperHealth {
  product_id: string;
  source_url: string | null;
  collector_id: string | null;
  status: "Healthy" | "Stale" | "Invalid output" | "Refresh failed" | "Not configured";
  schema_valid: boolean | null;
  last_successful_refresh: string | null;
  last_error: string | null;
}

export interface RegulatorySource {
  id: string;
  authority: string;
  jurisdiction: string;
  title: string;
  source_url: string;
  retrieved_at: string;
  source_type?: string;
  content: string;
  status: "current" | "refresh_failed";
  last_error: string | null;
  verification_status?: "VERIFIED" | "SUPPORTED" | "NEEDS_REVIEW" | string;
  evidence_text?: string;
}

export interface RegulatoryDiscovery {
  id: string;
  topic: string;
  title: string;
  summary: string;
  authority: string;
  jurisdiction: string;
  evidence_status: "VERIFIED" | "SUPPORTED" | "NEEDS_REVIEW";
  source_title: string;
  source_url: string;
  source_retrieved_at: string;
  ask_prompt: string;
  related_product_ids: string[];
}

export interface AskSection {
  heading: string;
  content: string;
  kind?: "manufacturer_fact" | "computed_finding" | "regulatory_context" | "interpretation" | string;
}

export interface AskResponse {
  answer: string;
  sections?: AskSection[];
  sources: Array<RegulatorySource | string>;
  products?: string[];
  product_facts?: Array<{
    product_id: string;
    display_name: string;
    manufacturer: string;
    market: string;
    source_url: string;
    scraped_at: string;
    caffeine_mg: number | null;
    sugar_g: number | null;
    calories: number | null;
    serving_size: ServingSize;
  }>;
  evidence?: Array<{
    source_id: string;
    title: string;
    authority: string;
    jurisdiction: string;
    url: string;
    text: string;
  }>;
  findings?: RegulatoryFinding[];
  recalls?: RecallRecord[];
  answer_mode: "openrouter" | "deterministic";
  model: string | null;
}

export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
}
