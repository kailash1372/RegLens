import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  ApiError,
  askRegLens,
  compareProducts,
  getFindings,
  getDiscoveries,
  getProduct,
  getProductAssets,
  getProducts,
  getRecalls,
  getRules,
  getScraperHealth,
  getSources,
  refreshProduct,
  refreshSources,
} from "./api";
import type {
  AskResponse,
  ProductRecord,
  ProductScraperAssets,
  ProductSnapshot,
  ProductSummary,
  RecallRecord,
  RegulatoryDiscovery,
  RegulatoryFinding,
  RegulatorySource,
  ScraperAsset,
  ScraperAssets,
  ScraperHealth,
} from "./types";

type Page = "catalog" | "compare" | "ask" | "evidence" | "health" | "passport";

interface RouteState {
  page: Page;
  passportId: string | null;
  question: string;
}

const pagePaths: Record<Exclude<Page, "passport">, string> = {
  catalog: "/",
  compare: "/compare",
  ask: "/ask",
  evidence: "/evidence",
  health: "/data-health",
};

function currentRoute(): RouteState {
  const { pathname, search } = window.location;
  const productMatch = pathname.match(/^\/products\/([^/]+)$/);
  if (productMatch) {
    return { page: "passport", passportId: decodeURIComponent(productMatch[1]), question: "" };
  }
  const page = (Object.entries(pagePaths).find(([, path]) => path === pathname)?.[0] ?? "catalog") as Exclude<Page, "passport">;
  return { page, passportId: null, question: page === "ask" ? new URLSearchParams(search).get("q") ?? "" : "" };
}

function routePath(page: Page, passportId: string | null = null, question = ""): string {
  if (page === "passport" && passportId) return `/products/${encodeURIComponent(passportId)}`;
  const basePath = page === "passport" ? "/" : pagePaths[page];
  return page === "ask" && question ? `${basePath}?q=${encodeURIComponent(question)}` : basePath;
}

const exampleQuestions = [
  "Is Celsius okay for children to drink?",
  "Which drink has the least caffeine?",
  "Which drinks exceed the verified Canadian caffeine threshold?",
  "Compare CELSIUS, C4 Energy and Alani Nu.",
  "Have any of these brands appeared in official recall data?",
];

function displayNumber(value: number | null | undefined, unit = ""): string {
  return value === null || value === undefined ? "—" : `${value}${unit}`;
}

function displayDate(value: string | null | undefined, includeTime = false): string {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(includeTime ? { hour: "numeric", minute: "2-digit" } : {}),
  }).format(date);
}

function displaySnapshotAge(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return "Not available";
  if (seconds < 3600) return `${Math.max(1, Math.floor(seconds / 60))} min`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr`;
  return `${Math.floor(seconds / 86400)} day${seconds < 172800 ? "" : "s"}`;
}

function scraperSnapshotAge(item: ScraperHealth): string {
  if (item.snapshot_age_seconds !== null && item.snapshot_age_seconds !== undefined) {
    return displaySnapshotAge(item.snapshot_age_seconds);
  }
  if (!item.last_successful_refresh) return "Not available";
  const refreshedAt = new Date(item.last_successful_refresh).valueOf();
  if (!Number.isFinite(refreshedAt)) return "Not available";
  return displaySnapshotAge(Math.max(0, Math.floor((Date.now() - refreshedAt) / 1000)));
}

function humanizeValue(value: string | null | undefined, fallback = "Not available"): string {
  if (!value) return fallback;
  return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function marketName(market: string | null | undefined): string {
  return ({ US: "United States", CA: "Canada", SA: "Saudi Arabia", IN: "India" } as Record<string, string>)[market ?? ""] ?? market ?? "Unknown";
}

function nutritionLabelAssets(assets: ScraperAssets | null | undefined): ScraperAsset[] {
  const seen = new Set<string>();
  return (assets?.nutrition_label_images ?? []).filter((asset) => {
    if (!asset.url) return false;
    let identity = asset.url;
    try {
      const url = new URL(asset.url);
      url.searchParams.delete("width");
      identity = url.toString();
    } catch {
      // Preserve an unparseable URL for the browser to handle rather than hiding evidence.
    }
    if (seen.has(identity)) return false;
    seen.add(identity);
    return asset.content_type === "image";
  });
}

function hasPendingNutritionExtraction(snapshot: ProductSnapshot, assets: ScraperAssets | null | undefined): boolean {
  return nutritionLabelAssets(assets).length > 0 && snapshot.nutrition_facts.length === 0;
}

function statusClass(status: string): string {
  return `status status-${status.toLowerCase().replaceAll(" ", "-")}`;
}

function visibleHealthStatus(item: ScraperHealth): ScraperHealth["status"] {
  // A missing collector cannot truthfully be presented as a healthy live source.
  if (!item.collector_id && (item.status === "Healthy" || item.status === "Stale")) {
    return "Not configured";
  }
  return item.status;
}

function snapshotMode(health: ScraperHealth | null): string {
  if (health?.status === "Fixture cached") return "Fixture-cached snapshot";
  if (health?.collector_id && health.status !== "Not configured") return "Bright Data live snapshot";
  return "Cached snapshot";
}

function extractFindings(product: ProductRecord): RegulatoryFinding[] {
  return product.regulatory_findings ?? product.findings ?? [];
}

function sourceTitle(source: AskResponse["sources"][number]): string {
  return typeof source === "string" ? source : `${source.authority} · ${source.title}`;
}

function sourceUrl(source: AskResponse["sources"][number]): string | null {
  return typeof source === "string" ? null : source.source_url;
}

function answerParagraphs(answer: string): string[] {
  return answer
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.replaceAll("**", "").replace(/\[[\w-]+\]/g, "").trim())
    .filter(Boolean);
}

function recallAppliesToQuestion(question: string): boolean {
  return /\b(recall|recalled|recalls|enforcement|warning)\b/i.test(question);
}

function Nav({ page, onNavigate }: { page: Page; onNavigate: (page: Page) => void }) {
  const links: Array<{ page: Exclude<Page, "passport">; label: string }> = [
    { page: "catalog", label: "Catalog" },
    { page: "compare", label: "Compare" },
    { page: "ask", label: "Ask RegLens" },
    { page: "evidence", label: "Evidence" },
    { page: "health", label: "Data health" },
  ];
  return (
    <header className="topbar">
      <button className="brand" type="button" onClick={() => onNavigate("catalog")}>
        <span className="brand-mark">R</span>
        <span>RegLens</span>
      </button>
      <nav aria-label="Primary navigation">
        {links.map((link) => (
          <a
            aria-current={page === link.page || (page === "passport" && link.page === "catalog") ? "page" : undefined}
            className={page === link.page || (page === "passport" && link.page === "catalog") ? "active" : ""}
            href={pagePaths[link.page]}
            key={link.page}
            onClick={(event) => {
              event.preventDefault();
              onNavigate(link.page);
            }}
          >
            {link.label}
          </a>
        ))}
      </nav>
      <span className="topbar-note">Evidence-centric product intelligence</span>
    </header>
  );
}

function ProductCard({ product, onOpen }: { product: ProductSummary; onOpen: (id: string) => void }) {
  return (
    <button className="product-card" onClick={() => onOpen(product.id)} type="button">
      <span aria-hidden="true" className="card-arrow">↗</span>
      <p className="eyebrow">{product.manufacturer}</p>
      <strong>{product.display_name}</strong>
      <span className="market-label">{marketName(product.market)} formulation</span>
      <span className="card-facts">
        <span><b>{displayNumber(product.caffeine_mg, " mg")}</b> caffeine</span>
        <span><b>{displayNumber(product.sugar_g, " g")}</b> sugar</span>
      </span>
      <small>{product.refreshed_at ? `Snapshot · ${displayDate(product.refreshed_at)}` : "No valid snapshot"}</small>
    </button>
  );
}

function EmptyEvidence({ children }: { children: string }) {
  return <p className="empty-evidence">{children}</p>;
}

function SectionTitle({ label, title, detail }: { label: string; title: string; detail?: string }) {
  return (
    <div className="section-title">
      <p className="eyebrow">{label}</p>
      <h3>{title}</h3>
      {detail ? <p>{detail}</p> : null}
    </div>
  );
}

function ListBlock({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div className="detail-block">
      <h4>{title}</h4>
      {items.length === 0 ? <EmptyEvidence>{empty}</EmptyEvidence> : <ul className="plain-list">{items.map((item) => <li key={item}>{item}</li>)}</ul>}
    </div>
  );
}

function SnapshotFacts({ snapshot, assets }: { snapshot: ProductSnapshot; assets: ScraperAssets | null }) {
  const serving = snapshot.serving_size;
  const labelAssets = nutritionLabelAssets(assets);
  const nutritionPending = hasPendingNutritionExtraction(snapshot, assets);
  const servingText = serving.value === null
    ? "—"
    : `${serving.value} ${serving.unit ?? ""}${serving.ml ? ` · ${serving.ml} mL` : ""}`.trim();
  return (
    <section className="passport-section fact-section">
      <SectionTitle label="Manufacturer fact" title="Current label facts" detail="These values come from the current manufacturer page and are separate from regulatory context below." />
      {nutritionPending ? (
        <div className="extraction-notice" role="status">
          <strong>Structured nutrition extraction is pending.</strong>
          <span>A manufacturer nutrition-label image is available below. Values shown as — were not extracted from the current source.</span>
        </div>
      ) : null}
      <div className="metric-grid">
        <div><span>Caffeine</span><strong>{displayNumber(snapshot.caffeine_mg, " mg")}</strong><small>per serving</small></div>
        <div><span>Sugar</span><strong>{displayNumber(snapshot.sugar_g, " g")}</strong><small>per serving</small></div>
        <div><span>Calories</span><strong>{displayNumber(snapshot.calories)}</strong><small>per serving</small></div>
        <div><span>Serving size</span><strong>{servingText}</strong><small>as labelled</small></div>
      </div>
      <details className="passport-details">
        <summary>View full label details</summary>
        <div className="detail-grid">
          <div className="detail-block">
            <h4>Nutrition facts</h4>
            {snapshot.nutrition_facts.length === 0 ? <EmptyEvidence>{nutritionPending ? "See the manufacturer label image while structured rows are pending." : "No additional nutrition rows were extracted."}</EmptyEvidence> : (
              <dl className="nutrition-list">
                {snapshot.nutrition_facts.map((fact) => (
                  <div key={`${fact.name}-${fact.unit}`}><dt>{fact.name}</dt><dd>{displayNumber(fact.value, fact.unit ? ` ${fact.unit}` : "")}{fact.daily_value_percent === null ? "" : ` · ${fact.daily_value_percent}% DV`}</dd></div>
                ))}
              </dl>
            )}
          </div>
          <ListBlock title="Ingredients" items={snapshot.ingredients} empty="Ingredients were not extracted from the current source." />
          <ListBlock title="Manufacturer claims" items={snapshot.claims} empty="No manufacturer claims were extracted." />
          <ListBlock title="Manufacturer warnings" items={snapshot.warnings} empty="No manufacturer warnings were extracted." />
        </div>
      </details>
      {labelAssets.length > 0 ? (
        <section className="label-evidence" aria-labelledby="label-evidence-title">
          <div>
            <p className="eyebrow">Scraper asset</p>
            <h4 id="label-evidence-title">Manufacturer nutrition-label evidence</h4>
            <p>Images captured from the source page are retained as evidence, separate from structured nutrition fields.</p>
          </div>
          <div className="label-image-grid">
            {labelAssets.map((asset) => (
              <a href={asset.url} key={asset.url} rel="noreferrer" target="_blank">
                <img alt="Manufacturer nutrition label" loading="lazy" src={asset.url} />
                <span>Open full label ↗</span>
              </a>
            ))}
          </div>
        </section>
      ) : null}
    </section>
  );
}

function EvidenceMeta({ rule }: { rule: NonNullable<RegulatoryFinding["rule"]> }) {
  return (
    <p className="evidence-meta">
      {rule.authority ?? "Authority not supplied"}{rule.jurisdiction ? ` · ${rule.jurisdiction}` : ""}
      {rule.verification_status ? ` · ${rule.verification_status}` : ""}
      {rule.source_url ? <> · <a href={rule.source_url} rel="noreferrer" target="_blank">View source</a></> : null}
    </p>
  );
}

function FindingCard({ finding }: { finding: RegulatoryFinding }) {
  const rule = finding.rule;
  const explanation = finding.explanation ?? finding.explanation_template;
  const math = finding.observed_value === null || finding.observed_value === undefined
    ? null
    : `${finding.observed_value} ${finding.unit ?? ""} compared with ${displayNumber(finding.threshold_value, finding.unit ? ` ${finding.unit}` : "")}`;
  return (
    <article className="finding-card">
      <div className="finding-meta"><span className="tag computed">Computed comparison</span>{finding.status ? <span className="tag">{finding.status}</span> : null}</div>
      <h4>{rule?.title ?? finding.finding_type ?? "Regulatory comparison"}</h4>
      {math ? <p className="finding-math">{math}</p> : null}
      {explanation ? <p>{explanation}</p> : <p>Structured result from a verified rule evaluation.</p>}
      {rule ? <EvidenceMeta rule={rule} /> : null}
    </article>
  );
}

function RecallCard({ recall }: { recall: RecallRecord }) {
  return (
    <article className="recall-card">
      <p><span className="tag regulatory">{recall.authority}</span> <span className="tag">{recall.match_type?.replaceAll("_", " ") ?? "Match context unavailable"}</span></p>
      <h4>{recall.product_description}</h4>
      <p>{recall.reason}</p>
      <small>{recall.jurisdiction}{recall.event_date ? ` · ${displayDate(recall.event_date)}` : ""} · <a href={recall.source_url} rel="noreferrer" target="_blank">Official record</a></small>
    </article>
  );
}

function Passport({ productId, onBack }: { productId: string; onBack: () => void }) {
  const [product, setProduct] = useState<ProductRecord | null>(null);
  const [productAssets, setProductAssets] = useState<ProductScraperAssets | null>(null);
  const [scraperHealth, setScraperHealth] = useState<ScraperHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshSuccess, setRefreshSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setRefreshSuccess(null);
    setScraperHealth(null);
    getScraperHealth()
      .then((items) => {
        if (active) setScraperHealth(items.find((item) => item.product_id === productId) ?? null);
      })
      .catch(() => {
        // Product facts remain useful when the optional health endpoint is unavailable.
      });
    Promise.all([
      getProduct(productId),
      getProductAssets(productId),
      getFindings(productId),
      getRecalls(productId),
      getRules(),
      getSources(),
    ])
      .then(([result, assets, findings, recalls, rules, sources]) => {
        if (!active) return;
        const ruleById = new Map(rules.map((rule) => [rule.id, rule]));
        const sourceById = new Map(sources.map((source) => [source.id, source]));
        const enrichedFindings = findings.map((finding) => {
          const rule = finding.rule_id ? ruleById.get(finding.rule_id) : undefined;
          const source = rule?.source_id ? sourceById.get(rule.source_id) : undefined;
          return {
            ...finding,
            rule: rule
              ? {
                  ...rule,
                  title: source?.title,
                  source_url: source?.source_url,
                  retrieved_at: source?.retrieved_at,
                }
              : undefined,
          };
        });
        setProduct({ ...result, regulatory_findings: enrichedFindings, recalls });
        setProductAssets(assets);
      })
      .catch(() => { if (active) setError("This Product Passport could not be loaded."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [productId]);

  async function refresh(): Promise<void> {
    setRefreshing(true);
    setError(null);
    setRefreshSuccess(null);
    try {
      const outcome = await refreshProduct(productId);
      const refreshed = outcome.product;
      const [assets, findings] = await Promise.all([getProductAssets(productId), getFindings(productId)]);
      setProduct((current) => ({
        ...refreshed,
        regulatory_findings: findings.map((finding) => ({
          ...finding,
          rule: current?.regulatory_findings?.find(
            (existing) => existing.rule_id === finding.rule_id,
          )?.rule,
        })),
        recalls: current?.recalls,
      }));
      setProductAssets(assets);
      if (outcome.accepted) {
        setRefreshSuccess(refreshed.active_snapshot?.source.scraped_at ?? new Date().toISOString());
      } else {
        setError(
          outcome.error ??
            (outcome.served_cached
              ? "The source refresh was not accepted; the last valid snapshot remains shown."
              : "The source refresh was not accepted."),
        );
      }
      getScraperHealth()
        .then((items) => setScraperHealth(items.find((item) => item.product_id === productId) ?? null))
        .catch(() => {
          // The accepted snapshot is already visible; health is supplementary metadata.
        });
    } catch (refreshError) {
      setError(refreshError instanceof ApiError ? refreshError.message : "The refresh request failed.");
    } finally {
      setRefreshing(false);
    }
  }

  if (loading) return <LoadingView label="Loading Product Passport…" />;
  if (error && product === null) return <ErrorView message={error} action={onBack} actionLabel="Return to catalog" />;
  if (product === null) return null;
  const snapshot = product.active_snapshot;
  const findings = extractFindings(product);
  const recalls = product.recalls ?? [];
  return (
    <div className="page passport-page">
      <button className="back-link" type="button" onClick={onBack}>← Back to catalog</button>
      {error ? <div className="inline-error">Refresh issue: {error}. The last valid snapshot remains shown below.</div> : null}
      {refreshSuccess ? <div className="inline-success" role="status">Refresh succeeded. Accepted manufacturer data is current as of {displayDate(refreshSuccess, true)}.</div> : null}
      <section className="passport-hero">
        <div>
          <p className="eyebrow">Product Passport</p>
          <h1>{product.display_name}</h1>
          <p className="passport-subtitle">{product.manufacturer} · {product.category.replaceAll("_", " ").replaceAll("-", " ")} · {marketName(product.market)} formulation</p>
          <p className="snapshot-badge"><span className="tag computed">{snapshotMode(scraperHealth)}</span></p>
        </div>
        <div className="passport-actions">
          <button className="button secondary" disabled={refreshing} onClick={refresh} type="button">{refreshing ? "Refreshing…" : "Refresh source"}</button>
          <p>Refresh validates output before replacing the current snapshot.</p>
        </div>
      </section>
      {snapshot === null ? <EmptyEvidence>No valid manufacturer snapshot is available for this product yet.</EmptyEvidence> : (
        <>
          <section className="passport-section passport-at-a-glance">
            <SectionTitle label="At a glance" title="The essentials before the details" />
            <div className="metric-grid">
              <div><span>Label caffeine</span><strong>{displayNumber(snapshot.caffeine_mg, " mg")}</strong><small>manufacturer fact · per serving</small></div>
              <div><span>Regulatory context</span><strong>{findings.length}</strong><small>{findings.length === 1 ? "computed comparison available" : "computed comparisons available"}</small></div>
              <div><span>Recall context</span><strong>{recalls.length}</strong><small>{recalls.length === 1 ? "official record associated" : "official records associated"}</small></div>
              <div><span>Freshness</span><strong>{displayDate(snapshot.source.scraped_at)}</strong><small>last manufacturer snapshot</small></div>
            </div>
          </section>
          <section className="source-strip">
            <div><span>Manufacturer source</span><a href={snapshot.source.url} rel="noreferrer" target="_blank">Open official page ↗</a></div>
            <div><span>Market formulation</span><strong>{marketName(snapshot.source.market)} ({snapshot.source.market})</strong></div>
            <div><span>Last product snapshot</span><strong>{displayDate(snapshot.source.scraped_at, true)}</strong></div>
            <div><span>Data state</span><strong>{snapshotMode(scraperHealth)}</strong></div>
          </section>
          <SnapshotFacts assets={productAssets?.scraper_assets ?? null} snapshot={snapshot} />
        </>
      )}
      <section className="passport-section regulatory-section">
        <SectionTitle label="Computed comparison" title="Regulatory context" detail="Deterministic findings are separate from manufacturer facts and do not establish legal compliance in another market." />
        {findings.length === 0 ? <EmptyEvidence>No deterministic regulatory comparisons are available for this product yet.</EmptyEvidence> : <div className="finding-grid">{findings.map((finding, index) => <FindingCard finding={finding} key={finding.id ?? finding.rule_id ?? index} />)}</div>}
      </section>
      <section className="passport-section">
        <SectionTitle label="Recall context" title="Official enforcement and recall records" detail="Match level matters: brand-level history is not treated as an exact current-SKU match." />
        {recalls.length === 0 ? <EmptyEvidence>No recall records are currently associated with this product in the available official data.</EmptyEvidence> : <div className="recall-grid">{recalls.map((recall) => <RecallCard key={`${recall.source_url}-${recall.product_description}`} recall={recall} />)}</div>}
      </section>
    </div>
  );
}

function Catalog({ products, loading, error, onOpen, onAsk }: { products: ProductSummary[]; loading: boolean; error: string | null; onOpen: (id: string) => void; onAsk: (question: string) => void }) {
  const [discoveries, setDiscoveries] = useState<RegulatoryDiscovery[]>([]);
  const [discoveriesLoading, setDiscoveriesLoading] = useState(true);
  const [discoveriesError, setDiscoveriesError] = useState(false);
  const [launcherQuestion, setLauncherQuestion] = useState("");

  useEffect(() => {
    getDiscoveries()
      .then(setDiscoveries)
      .catch(() => setDiscoveriesError(true))
      .finally(() => setDiscoveriesLoading(false));
  }, []);

  function launchInvestigation(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onAsk(launcherQuestion.trim());
  }

  const featuredDiscovery = discoveries.find((discovery) => discovery.evidence_status === "VERIFIED") ?? discoveries[0];

  return (
    <div className="page catalog-page">
      <section className="hero">
        <p className="eyebrow">Evidence-backed answers for everyday product questions</p>
        <h1>Understand what’s inside.<br /><em>See what regulators say.</em></h1>
        <p>Product labels rarely show the wider regulatory context. RegLens connects current manufacturer facts with primary government evidence—without turning either into an unsupported safety verdict.</p>
        <form className="question-launcher" onSubmit={launchInvestigation}>
          <input aria-label="Search a product or ask a question" id="homepage-question" onChange={(event) => setLauncherQuestion(event.target.value)} placeholder="Search a product or ask a natural question" value={launcherQuestion} />
          <button className="button" type="submit">Start investigating →</button>
        </form>
        <div className="question-examples">{exampleQuestions.slice(0, 3).map((question) => <button key={question} onClick={() => onAsk(question)} type="button">{question}</button>)}</div>
        <div className="authority-strip"><span>Primary evidence from</span><a href="https://recalls-rappels.canada.ca/en/alert-recall/caffeinated-energy-drinks-what-you-should-know" rel="noreferrer" target="_blank">Health Canada ↗</a><a href="https://www.fda.gov/industry/color-additives" rel="noreferrer" target="_blank">U.S. FDA ↗</a><a href="https://open.canada.ca/data/en/dataset/d38de914-c94c-429b-8ab1-8776c31643e3" rel="noreferrer" target="_blank">Canada Recalls ↗</a></div>
        {featuredDiscovery ? <article className="discovery-card featured-discovery">
          <div className="discovery-card-top"><span>Verified discovery · {featuredDiscovery.jurisdiction}</span><span className="tag computed">{featuredDiscovery.evidence_status}</span></div>
          <h3>{featuredDiscovery.title}</h3>
          <p>{featuredDiscovery.summary}</p>
          <div className="discovery-actions"><button onClick={() => onAsk(featuredDiscovery.ask_prompt)} type="button">Ask RegLens about this →</button><a href={featuredDiscovery.source_url} rel="noreferrer" target="_blank">{featuredDiscovery.authority} evidence ↗</a></div>
        </article> : null}
      </section>
      <section className="discovery-section">
        <div className="discovery-heading"><div><p className="eyebrow">Did you know?</p><h2>Regulatory context hiding behind everyday labels</h2></div><p>Each card comes from current evidence stored in RegLens—not an unsupported health claim.</p></div>
        {discoveriesLoading ? <LoadingView label="Loading source-backed discoveries…" /> : null}
        {discoveriesError ? <p className="discovery-error">Discovery cards are temporarily unavailable. Product Passports and preserved evidence remain accessible.</p> : null}
        <div className="discovery-grid">{discoveries.filter((discovery) => discovery.id !== featuredDiscovery?.id).map((discovery) => <article className="discovery-card" key={discovery.id}>
          <div className="discovery-card-top"><span>{discovery.jurisdiction} · {discovery.topic}</span><span className={`tag ${discovery.evidence_status === "VERIFIED" ? "computed" : "regulatory"}`}>{discovery.evidence_status}</span></div>
          <h3>{discovery.title}</h3>
          <p>{discovery.summary}</p>
          <div className="discovery-source"><span>{discovery.authority}</span><small>Retrieved {displayDate(discovery.source_retrieved_at)}</small></div>
          <div className="discovery-actions"><button onClick={() => onAsk(discovery.ask_prompt)} type="button">Ask RegLens about this →</button><a href={discovery.source_url} rel="noreferrer" target="_blank">Official evidence ↗</a></div>
          {discovery.related_product_ids.length > 0 ? <div className="discovery-products" aria-label="Related Product Passports">{discovery.related_product_ids.slice(0, 3).map((productId) => {
            const relatedProduct = products.find((product) => product.id === productId);
            return relatedProduct ? <button key={productId} onClick={() => onOpen(productId)} type="button">{relatedProduct.display_name} →</button> : null;
          })}</div> : null}
        </article>)}</div>
        <div className="discovery-cta"><div><p className="eyebrow">Follow the evidence</p><h3>Check products and ingredients against the sources RegLens currently indexes.</h3><p>Coverage is shown transparently. Absence of a finding is not proof that no regulation exists anywhere.</p></div><button className="button" onClick={() => onAsk("What regulatory evidence does RegLens have about food ingredients?")} type="button">Ask about an ingredient →</button></div>
      </section>
      <section className="catalog-section">
        <div className="page-heading"><div><p className="eyebrow">Products RegLens currently knows</p><h2>Investigate a specific product</h2></div><p>Every fact links back to its manufacturer source.</p></div>
        {loading ? <LoadingView label="Loading catalog…" /> : null}
        {error ? <ErrorView message={error} /> : null}
        {!loading && !error && products.length === 0 ? <EmptyEvidence>No catalog products are available.</EmptyEvidence> : null}
        <div className="product-grid">{products.map((product) => <ProductCard key={product.id} onOpen={onOpen} product={product} />)}</div>
      </section>
      <section className="principles"><div><span>01</span><h3>Manufacturer fact</h3><p>Current sourced product-label information.</p></div><div><span>02</span><h3>Regulatory source</h3><p>Authority, jurisdiction, evidence, and date visible.</p></div><div><span>03</span><h3>Computed comparison</h3><p>Only verified rules drive automated findings.</p></div></section>
    </div>
  );
}

function Compare({
  products,
  loadingProducts,
  productError,
  onOpen,
}: {
  products: ProductSummary[];
  loadingProducts: boolean;
  productError: string | null;
  onOpen: (id: string) => void;
}) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [results, setResults] = useState<ProductRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectionQuery, setSelectionQuery] = useState("");
  function toggle(id: string): void {
    setResults([]);
    setSelectedIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  }
  async function runCompare(): Promise<void> {
    if (selectedIds.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const compared = await compareProducts(selectedIds);
      const enriched = await Promise.all(compared.map(async (product) => {
        const [findings, recalls] = await Promise.all([
          getFindings(product.id),
          getRecalls(product.id),
        ]);
        return { ...product, regulatory_findings: findings, recalls };
      }));
      setResults(enriched);
    } catch {
      setError("The selected products could not be compared.");
    } finally {
      setLoading(false);
    }
  }
  const rows: Array<{ label: string; value: (item: ProductRecord) => string }> = [
    { label: "Caffeine", value: (item) => displayNumber(item.active_snapshot?.caffeine_mg, " mg") },
    { label: "Sugar", value: (item) => displayNumber(item.active_snapshot?.sugar_g, " g") },
    { label: "Calories", value: (item) => displayNumber(item.active_snapshot?.calories) },
    { label: "Serving size", value: (item) => { const size = item.active_snapshot?.serving_size; return size?.value === null || !size ? "—" : `${size.value} ${size.unit ?? ""}`; } },
    { label: "Regulatory findings", value: (item) => { const findings = extractFindings(item); return findings.length === 0 ? "None available" : findings.map((finding) => humanizeValue(finding.status ?? finding.finding_type, "Context")).join(", "); } },
    { label: "Recall context", value: (item) => { const recalls = item.recalls ?? []; return recalls.length === 0 ? "No associated records" : recalls.map((recall) => humanizeValue(recall.match_type, "Official record")).join(", "); } },
  ];
  const highlights = useMemo(() => {
    const caffeine = results.filter((product) => product.active_snapshot?.caffeine_mg !== null && product.active_snapshot?.caffeine_mg !== undefined);
    const sugar = results.filter((product) => product.active_snapshot?.sugar_g !== null && product.active_snapshot?.sugar_g !== undefined);
    const lowestCaffeine = caffeine.reduce<ProductRecord | null>((lowest, product) => !lowest || (product.active_snapshot?.caffeine_mg ?? Infinity) < (lowest.active_snapshot?.caffeine_mg ?? Infinity) ? product : lowest, null);
    const lowestSugar = sugar.reduce<ProductRecord | null>((lowest, product) => !lowest || (product.active_snapshot?.sugar_g ?? Infinity) < (lowest.active_snapshot?.sugar_g ?? Infinity) ? product : lowest, null);
    const markets = new Set(results.map((product) => product.active_snapshot?.source.market ?? product.market));
    return { lowestCaffeine, lowestSugar, markets };
  }, [results]);
  const normalizedSelectionQuery = selectionQuery.trim().toLowerCase();
  const visibleProducts = normalizedSelectionQuery
    ? products.filter((product) => `${product.display_name} ${product.manufacturer} ${product.market}`.toLowerCase().includes(normalizedSelectionQuery))
    : products;
  const selectedProducts = selectedIds.map((id) => products.find((product) => product.id === id)).filter((product): product is ProductSummary => product !== undefined);
  return (
    <div className="page compare-page">
      <p className="eyebrow">Compare</p><h1>Put the label facts<br />side by side.</h1>
      <p className="page-intro">Select products from the current catalog. Values are always requested from the backend—not set in this interface.</p>
      {loadingProducts ? <LoadingView label="Loading products for comparison…" /> : null}
      {productError ? <ErrorView message={productError} /> : null}
      {!loadingProducts && !productError && products.length === 0 ? <EmptyEvidence>No products are currently available to compare.</EmptyEvidence> : null}
      {!loadingProducts && !productError && products.length > 0 ? <>
        <label className="compare-filter" htmlFor="compare-product-filter">Find a product<input id="compare-product-filter" onChange={(event) => setSelectionQuery(event.target.value)} placeholder="Search by product, manufacturer, or market" type="search" value={selectionQuery} /></label>
        {selectedProducts.length > 0 ? <div className="selected-chips" aria-label="Selected products">{selectedProducts.map((product) => <button className="selected-chip" key={product.id} onClick={() => toggle(product.id)} type="button">{product.display_name} ×</button>)}</div> : null}
        <div className="selector-grid">{visibleProducts.map((product) => <label className={selectedIds.includes(product.id) ? "selection selected" : "selection"} key={product.id}><input checked={selectedIds.includes(product.id)} onChange={() => toggle(product.id)} type="checkbox" /><span><b>{product.display_name}</b><small>{product.manufacturer} · {marketName(product.market)} formulation</small></span></label>)}</div>
        {visibleProducts.length === 0 ? <EmptyEvidence>No catalog products match this search.</EmptyEvidence> : null}
        <div className="compare-action"><span>{selectedIds.length} selected</span><button className="button" disabled={selectedIds.length < 2 || loading} onClick={runCompare} type="button">{loading ? "Comparing…" : "Compare products"}</button></div>
      </> : null}
      {error ? <ErrorView message={error} /> : null}
      {!loadingProducts && !productError && (results.length > 0 ? <><section className="source-strip comparison-highlights" aria-label="Comparison highlights"><div><span>Lowest caffeine</span><strong>{highlights.lowestCaffeine ? `${highlights.lowestCaffeine.display_name} · ${displayNumber(highlights.lowestCaffeine.active_snapshot?.caffeine_mg, " mg")}` : "Not available"}</strong></div><div><span>Lowest sugar</span><strong>{highlights.lowestSugar ? `${highlights.lowestSugar.display_name} · ${displayNumber(highlights.lowestSugar.active_snapshot?.sugar_g, " g")}` : "Not available"}</strong></div><div><span>Market context</span><strong>{highlights.markets.size > 1 ? "Different market formulations" : "Same market formulation"}</strong></div></section><section className="comparison-table-wrap"><p className="compare-mobile-note" role="note">On a small screen, swipe left and right to view every product column.</p><table><thead><tr><th>Current data</th>{results.map((product) => <th key={product.id}><button className="table-product-link" onClick={() => onOpen(product.id)} type="button">{product.display_name}</button><small>{product.active_snapshot?.source.market ?? "—"} market</small></th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.label}><th>{row.label}</th>{results.map((product) => <td key={product.id}>{row.value(product)}</td>)}</tr>)}</tbody></table><p className="table-note">Values retain each manufacturer label's stated serving basis; check the Serving size row before comparing nutrition. — means the structured field is unavailable. Regulatory and recall details remain in each Product Passport.</p></section></> : <section className="compare-placeholder"><h3>Select at least two products</h3><p>Then compare current manufacturer facts alongside available regulatory context.</p></section>)}
    </div>
  );
}

interface ChatTurn {
  question: string;
  result: AskResponse;
}

function AnswerCard({ turn, onOpen }: { turn: ChatTurn; onOpen: (id: string) => void }) {
  const { result } = turn;
  const answerText = result.answer.toLowerCase();
  const questionWantsExceeders = /\b(exceed|above|over|threshold)\b/i.test(turn.question);
  const productFactLimit = questionWantsExceeders ? 6 : /\b(least|lowest|most|highest)\b/i.test(turn.question) ? 3 : 4;
  const rankedProductFacts = (result.product_facts ?? [])
    .map((fact) => ({ fact, position: answerText.indexOf(fact.display_name.toLowerCase()) }))
    .filter(({ position }) => position >= 0)
    .sort((left, right) => left.position - right.position)
    .map(({ fact }) => fact);
  const productFacts = (rankedProductFacts.length > 0 ? rankedProductFacts : result.product_facts ?? []).slice(0, productFactLimit);
  const referencedSourceUrls = new Set(result.sources.map((source) => sourceUrl(source) ?? (typeof source === "string" ? source : "")).filter(Boolean));
  const matchedEvidence = result.evidence?.filter((item) => referencedSourceUrls.has(item.url)) ?? [];
  const evidence = (matchedEvidence.length > 0 ? matchedEvidence : result.evidence ?? []).slice(0, 3);
  const recalls = recallAppliesToQuestion(turn.question) || /\b(recall|recalled|enforcement)\b/i.test(result.answer) ? result.recalls ?? [] : [];
  const matchingFindings = result.findings?.filter((finding) => !questionWantsExceeders || `${finding.finding_type ?? ""} ${finding.status ?? ""}`.toLowerCase().includes("exceed")) ?? [];
  const findings = (matchingFindings.length > 0 ? matchingFindings : result.findings ?? []).slice(0, 6);
  const sourceLinks: Array<{ label: string; url: string }> = [];
  const addSource = (label: string, url: string | null | undefined): void => {
    if (url && !sourceLinks.some((source) => source.url === url)) sourceLinks.push({ label, url });
  };
  result.sources.forEach((source, index) => addSource(typeof source === "string" ? `Regulatory source ${index + 1}` : sourceTitle(source), sourceUrl(source) ?? (typeof source === "string" ? source : null)));
  productFacts.forEach((fact) => addSource(`${fact.manufacturer} · ${fact.display_name}`, fact.source_url));
  evidence.forEach((item) => addSource(`${item.authority} · ${item.title}`, item.url));
  recalls.forEach((recall) => addSource(`${recall.authority} · Official recall record`, recall.source_url));
  return <section className="answer">
    <div className="answer-header"><p className="eyebrow">You asked</p><h2>{turn.question}</h2><span className={`answer-mode answer-mode-${result.answer_mode}`}>{result.answer_mode === "openrouter" ? "AI explanation grounded in available evidence" : "Deterministic evidence-backed answer"}</span></div>
    <article className="answer-copy"><span className="tag interpretation">{result.answer_mode === "openrouter" ? "AI interpretation" : "Evidence-backed explanation"}</span>{answerParagraphs(result.answer).map((paragraph, index) => <p key={`${paragraph.slice(0, 40)}-${index}`}>{paragraph}</p>)}</article>
    {productFacts.length > 0 ? <div className="answer-sections">{productFacts.map((fact) => <article className="manufacturer-answer-card" key={fact.product_id}><span className="tag manufacturer_fact">Manufacturer fact · {fact.market}</span><h3><button className="answer-product-link" onClick={() => onOpen(fact.product_id)} type="button">{fact.display_name} →</button></h3><p className="fact-line"><b>{displayNumber(fact.caffeine_mg, " mg")}</b> caffeine · <b>{displayNumber(fact.sugar_g, " g")}</b> sugar · <b>{displayNumber(fact.calories)}</b> calories</p><a href={fact.source_url} rel="noreferrer" target="_blank">{fact.manufacturer} source · checked {displayDate(fact.scraped_at)} ↗</a></article>)}</div> : null}
    {result.sections && result.sections.length > 0 ? <div className="answer-sections">{result.sections.map((section) => <article key={`${section.heading}-${section.content}`}><span className={`tag ${section.kind ?? ""}`}>{section.kind?.replaceAll("_", " ") ?? "Context"}</span><h3>{section.heading}</h3><p>{section.content}</p></article>)}</div> : null}
    {findings.length > 0 ? <div className="answer-sections">{findings.map((finding, index) => <article className="regulatory-answer-card" key={`${finding.rule_id ?? "finding"}-${index}`}><span className="tag computed">Computed from a verified rule</span><h3>{humanizeValue(finding.finding_type, "Regulatory comparison")}</h3><p>{finding.explanation_template ?? "A deterministic result generated from a verified rule."}</p></article>)}</div> : null}
    {evidence.length > 0 ? <div className="answer-sections">{evidence.map((item) => <article className="regulatory-answer-card" key={item.source_id}><span className="tag regulatory">Regulatory source · {item.jurisdiction}</span><h3>{item.authority}</h3><p>{item.text}</p><a href={item.url} rel="noreferrer" target="_blank">{item.title} ↗</a></article>)}</div> : null}
    {recalls.length > 0 ? <section className="answer-recalls"><h3>Official recall context</h3><p>Match level is shown so brand or product-family history is not presented as an exact current-SKU recall.</p><div className="recall-grid">{recalls.map((recall) => <RecallCard key={`${recall.source_url}-${recall.product_description}`} recall={recall} />)}</div></section> : null}
    <div className="answer-sources"><h3>Sources used</h3>{sourceLinks.length === 0 ? <EmptyEvidence>This answer used only stored deterministic catalog analysis.</EmptyEvidence> : <ul>{sourceLinks.map((source) => <li key={source.url}><a href={source.url} rel="noreferrer" target="_blank">{source.label} ↗</a></li>)}</ul>}</div>
  </section>;
}

function Ask({ initialQuestion, autoSubmit, onOpen }: { initialQuestion: string; autoSubmit: boolean; onOpen: (id: string) => void }) {
  const [question, setQuestion] = useState(initialQuestion);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submittedInitialQuestion = useRef<string | null>(null);
  useEffect(() => {
    if (!autoSubmit) setQuestion(initialQuestion);
  }, [autoSubmit, initialQuestion]);

  const investigate = useCallback(async (submittedQuestion: string): Promise<void> => {
    if (submittedQuestion.length < 3) {
      setError("Enter a question with at least three characters.");
      return;
    }
    const history = turns.flatMap((turn) => [
      { role: "user" as const, content: turn.question },
      { role: "assistant" as const, content: turn.result.answer },
    ]).slice(-12);
    const contextProducts = turns.at(-1)?.result.products ?? [];
    setLoading(true);
    setError(null);
    setQuestion("");
    try {
      const result = await askRegLens(submittedQuestion, history, contextProducts);
      setTurns((current) => [...current, { question: submittedQuestion, result }]);
    } catch {
      setError("RegLens could not complete that investigation. Your earlier conversation remains available.");
      setQuestion(submittedQuestion);
    } finally {
      setLoading(false);
    }
  }, [turns]);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await investigate(question.trim());
  }

  useEffect(() => {
    const questionToSubmit = initialQuestion.trim();
    if (!autoSubmit || questionToSubmit.length < 3 || submittedInitialQuestion.current === questionToSubmit) return;
    submittedInitialQuestion.current = questionToSubmit;
    void investigate(questionToSubmit);
  }, [autoSubmit, initialQuestion, investigate]);

  return (
    <div className="page ask-page"><div className="ask-heading"><div><p className="eyebrow">Ask RegLens</p><h1>Investigate.<br /><em>Then follow up.</em></h1><p className="page-intro">Ask in ordinary language. RegLens assembles current product facts, verified computations, and relevant primary evidence before explaining the result.</p></div>{turns.length > 0 ? <button className="button secondary" onClick={() => { setTurns([]); setError(null); }} type="button">New investigation</button> : null}</div>
      <div className="chat-thread">{turns.map((turn, index) => <AnswerCard key={`${turn.question}-${index}`} onOpen={onOpen} turn={turn} />)}</div>
      <form className="ask-form ask-form-sticky" onSubmit={submit}><label htmlFor="question">{turns.length > 0 ? "Ask a follow-up" : "Your question"}</label><textarea id="question" maxLength={2000} onChange={(event) => setQuestion(event.target.value)} placeholder={turns.length > 0 ? "e.g. What about Bloom?" : "e.g. Is CELSIUS okay for children?"} value={question} /><div><span>{question.length}/2000 · conversation resets on refresh</span><button className="button" disabled={loading} type="submit">{loading ? "Investigating…" : turns.length > 0 ? "Ask follow-up →" : "Investigate →"}</button></div></form>
      {turns.length === 0 ? <div className="example-list"><span>Try an example</span>{exampleQuestions.map((example) => <button key={example} onClick={() => setQuestion(example)} type="button">{example}</button>)}</div> : null}
      {error ? <ErrorView message={error} /> : null}
    </div>
  );
}

function Health({ products, loadingProducts, productError }: { products: ProductSummary[]; loadingProducts: boolean; productError: string | null }) {
  const [health, setHealth] = useState<ScraperHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getScraperHealth().then(setHealth).catch(() => setError("Scraper health could not be loaded.")).finally(() => setLoading(false)); }, []);
  const names = useMemo(() => new Map(products.map((product) => [product.id, product.display_name])), [products]);
  const configuredCount = health.filter((item) => item.collector_id).length;
  const healthyCount = health.filter((item) => item.collector_id && visibleHealthStatus(item) === "Healthy").length;
  const attentionCount = health.filter((item) => ["Stale", "Invalid output", "Refresh failed"].includes(visibleHealthStatus(item))).length;
  const cachedCount = health.length - configuredCount;
  const latestRefresh = health.reduce<string | null>((latest, item) => {
    if (!item.last_successful_refresh) return latest;
    if (!latest) return item.last_successful_refresh;
    return new Date(item.last_successful_refresh) > new Date(latest) ? item.last_successful_refresh : latest;
  }, null);

  return (
    <div className="page health-page">
      <p className="eyebrow">Data / Scraper health</p>
      <h1>Trust starts with<br />the extraction.</h1>
      <p className="page-intro">Bright Data collectors feed validated product snapshots into RegLens. Invalid output stays visible while the last known valid snapshot remains available.</p>
      {!loading && health.length > 0 ? <section className="health-summary" aria-label="Bright Data ingestion overview">
        <div><span>Collectors configured</span><strong>{configuredCount}/{health.length}</strong></div>
        <div><span>Healthy live collectors</span><strong>{healthyCount}</strong></div>
        <div><span>Need attention</span><strong>{attentionCount}</strong></div>
        <div><span>Cached snapshots</span><strong>{cachedCount}</strong></div>
        <div><span>Latest valid ingestion</span><strong>{displayDate(latestRefresh, true)}</strong></div>
      </section> : null}
      {loading ? <LoadingView label="Loading scraper health…" /> : null}
      {error ? <ErrorView message={error} /> : null}
      {!loading && !error && health.length === 0 ? <EmptyEvidence>No source health records are available.</EmptyEvidence> : null}
      {loadingProducts ? <p className="health-catalog-note">Matching collector records to catalog names…</p> : null}
      {productError ? <p className="health-catalog-note">Catalog names are unavailable; product identifiers are shown instead.</p> : null}
      <div className="health-list">
        {health.map((item) => {
          const displayedStatus = visibleHealthStatus(item);
          return <article className="health-row" key={item.product_id}>
            <div><p className="eyebrow">{names.get(item.product_id) ?? item.product_id}</p><h3>{item.source_url ? <a href={item.source_url} rel="noreferrer" target="_blank">Manufacturer source ↗</a> : "Source pending configuration"}</h3></div>
            <div><span>Status</span><b className={statusClass(displayedStatus)}>{displayedStatus}</b></div>
            <div><span>Schema</span><b>{item.schema_valid === null ? "Not checked" : item.schema_valid ? "Valid" : "Invalid"}</b></div>
            <div><span>Last successful refresh</span><b>{displayDate(item.last_successful_refresh, true)}</b></div>
            <div><span>Snapshot age</span><b>{scraperSnapshotAge(item)}</b></div>
            <div title={item.collector_id ?? undefined}><span>Bright Data collector</span><b>{item.collector_id ? "Configured" : "Not configured"}</b></div>
            {item.last_error ? <p className="health-error">Latest error: {item.last_error}</p> : null}
          </article>;
        })}
      </div>
      <section className="health-explainer"><h3>Resilient refresh flow</h3><p>When a configured collector produces malformed output, RegLens marks it unhealthy and preserves the last valid snapshot. Repair happens in Bright Data Scraper Studio; after a valid re-run, this status returns to Healthy.</p></section>
    </div>
  );
}

function EvidenceLibrary() {
  const [sources, setSources] = useState<RegulatorySource[]>([]);
  const [sourceQuery, setSourceQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((): void => {
    setLoading(true);
    setError(null);
    getSources()
      .then(setSources)
      .catch(() => setError("The regulatory source corpus could not be loaded."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => load(), [load]);

  function refresh(): void {
    setRefreshing(true);
    setError(null);
    refreshSources()
      .then(setSources)
      .catch(() => setError("Source refresh failed. Preserved evidence remains available."))
      .finally(() => setRefreshing(false));
  }

  const normalizedSourceQuery = sourceQuery.trim().toLowerCase();
  const visibleSources = normalizedSourceQuery
    ? sources.filter((source) => `${source.title} ${source.authority} ${source.jurisdiction} ${source.source_type ?? ""}`.toLowerCase().includes(normalizedSourceQuery))
    : sources;

  return (
    <div className="page evidence-page">
      <p className="eyebrow">Authoritative source corpus</p>
      <div className="evidence-heading">
        <div>
          <h1>Evidence before<br /><em>interpretation.</em></h1>
          <p className="page-intro">Primary government material is preserved with provenance before RegLens derives rules or findings from it.</p>
        </div>
        <button className="button secondary" disabled={refreshing} onClick={refresh} type="button">
          {refreshing ? "Refreshing sources…" : "Refresh primary sources"}
        </button>
      </div>
      {loading ? <LoadingView label="Loading regulatory sources…" /> : null}
      {error ? <ErrorView action={load} actionLabel="Reload preserved corpus" message={error} /> : null}
      {!loading && !error && sources.length === 0 ? <EmptyEvidence>No regulatory sources are stored.</EmptyEvidence> : null}
      {sources.length > 0 ? <label className="evidence-filter" htmlFor="evidence-filter">Find evidence<input id="evidence-filter" onChange={(event) => setSourceQuery(event.target.value)} placeholder="Search by topic, regulator, or jurisdiction" type="search" value={sourceQuery} /></label> : null}
      {sources.length > 0 && visibleSources.length === 0 ? <EmptyEvidence>No evidence sources match this search.</EmptyEvidence> : null}
      <div className="source-library">
        {visibleSources.map((source) => (
          <article className="source-card" key={source.id}>
            <div className="source-card-header">
              <span className={`source-state source-state-${source.status}`}>{source.status === "current" ? "Current" : "Refresh failed"}</span>
              <span>{source.jurisdiction}</span>
            </div>
            <p className="eyebrow">{source.authority}</p>
            <h2>{source.title}</h2>
            <p className="source-summary">{source.evidence_text ?? source.content}</p>
            <dl className="source-metadata">
              <div><dt>Evidence type</dt><dd>{humanizeValue(source.source_type, "Authoritative source")}</dd></div>
              <div><dt>Verification</dt><dd>{humanizeValue(source.verification_status, "Source preserved")}</dd></div>
              <div><dt>Retrieved</dt><dd>{displayDate(source.retrieved_at, true)}</dd></div>
            </dl>
            {source.last_error ? <p className="source-error">Latest refresh: {source.last_error}</p> : null}
            <details>
              <summary>View the preserved source record</summary>
              <p>This is the captured source text retained for traceability. It may include page navigation or other material outside the evidence excerpt above.</p>
              <p>{source.content}</p>
            </details>
            <a href={source.source_url} rel="noreferrer" target="_blank">Open primary source ↗</a>
          </article>
        ))}
      </div>
    </div>
  );
}

function LoadingView({ label }: { label: string }) { return <p className="loading"><span />{label}</p>; }
function ErrorView({ message, action, actionLabel }: { message: string; action?: () => void; actionLabel?: string }) { return <div className="error-view"><strong>Unable to continue</strong><p>{message}</p>{action ? <button className="button secondary" onClick={action} type="button">{actionLabel ?? "Try again"}</button> : null}</div>; }

export function App() {
  const [route, setRoute] = useState<RouteState>(currentRoute);
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [productError, setProductError] = useState<string | null>(null);
  const [askQuestion, setAskQuestion] = useState(route.question);
  const [askAutoSubmit, setAskAutoSubmit] = useState(route.page === "ask" && route.question.trim().length >= 3);

  useEffect(() => { getProducts().then(setProducts).catch(() => setProductError("RegLens could not reach the local API. Start the FastAPI server and try again.")).finally(() => setLoadingProducts(false)); }, []);
  useEffect(() => {
    const handlePopState = (): void => {
      const nextRoute = currentRoute();
      setRoute(nextRoute);
      setAskQuestion(nextRoute.question);
      setAskAutoSubmit(nextRoute.page === "ask" && nextRoute.question.trim().length >= 3);
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigate(nextPage: Page, passportId: string | null = null, question = ""): void {
    const nextRoute = { page: nextPage, passportId, question };
    window.history.pushState(null, "", routePath(nextPage, passportId, question));
    setRoute(nextRoute);
    window.scrollTo({ top: 0 });
  }

  function openPassport(id: string): void {
    navigate("passport", id);
  }

  function openAsk(question: string): void {
    const normalizedQuestion = question.trim();
    setAskQuestion(normalizedQuestion);
    setAskAutoSubmit(normalizedQuestion.length >= 3);
    navigate("ask", null, normalizedQuestion);
  }

  const { page, passportId } = route;
  return <main><Nav onNavigate={(nextPage) => {
    if (nextPage === "ask") {
      setAskQuestion("");
      setAskAutoSubmit(false);
    }
    navigate(nextPage);
  }} page={page} />{page === "catalog" ? <Catalog error={productError} loading={loadingProducts} onAsk={openAsk} onOpen={openPassport} products={products} /> : null}{page === "passport" && passportId ? <Passport onBack={() => navigate("catalog")} productId={passportId} /> : null}{page === "compare" ? <Compare loadingProducts={loadingProducts} onOpen={openPassport} productError={productError} products={products} /> : null}{page === "ask" ? <Ask autoSubmit={askAutoSubmit} initialQuestion={askQuestion} onOpen={openPassport} /> : null}{page === "evidence" ? <EvidenceLibrary /> : null}{page === "health" ? <Health loadingProducts={loadingProducts} productError={productError} products={products} /> : null}<footer><span>RegLens</span><p>Manufacturer facts, regulatory evidence, computed findings, and interpretation are intentionally distinct.</p></footer></main>;
}
