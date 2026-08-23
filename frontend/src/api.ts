import type {
  AskResponse,
  ChatHistoryMessage,
  ProductRecord,
  ProductRefreshOutcome,
  ProductScraperAssets,
  ProductSummary,
  RecallRecord,
  RegulatoryDiscovery,
  RegulatoryFinding,
  RegulatoryRule,
  RegulatorySource,
  ScraperHealth,
} from "./types";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      message = body.detail ?? message;
    } catch {
      // A reverse proxy may return an HTML error page. The status remains useful.
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export function getProducts(): Promise<ProductSummary[]> {
  return request<ProductSummary[]>("/api/products");
}

export function getProduct(id: string): Promise<ProductRecord> {
  return request<ProductRecord>(`/api/products/${encodeURIComponent(id)}`);
}

export function getProductAssets(id: string): Promise<ProductScraperAssets> {
  return request<ProductScraperAssets>(`/api/products/${encodeURIComponent(id)}/assets`);
}

export function compareProducts(ids: string[]): Promise<ProductRecord[]> {
  const query = new URLSearchParams({ ids: ids.join(",") });
  return request<ProductRecord[]>(`/api/products/compare?${query.toString()}`);
}

export function refreshProduct(id: string): Promise<ProductRefreshOutcome> {
  return request<ProductRefreshOutcome>(`/api/products/${encodeURIComponent(id)}/refresh`, {
    method: "POST",
  });
}

export function getScraperHealth(): Promise<ScraperHealth[]> {
  return request<ScraperHealth[]>("/api/scrapers/health");
}

export function getFindings(productId?: string): Promise<RegulatoryFinding[]> {
  const query = productId ? `?${new URLSearchParams({ product_id: productId }).toString()}` : "";
  return request<RegulatoryFinding[]>(`/api/findings${query}`);
}

export function getRecalls(productId?: string): Promise<RecallRecord[]> {
  const query = productId ? `?${new URLSearchParams({ product_id: productId }).toString()}` : "";
  return request<RecallRecord[]>(`/api/recalls${query}`);
}

export function getRules(): Promise<RegulatoryRule[]> {
  return request<RegulatoryRule[]>("/api/rules");
}

export function getDiscoveries(): Promise<RegulatoryDiscovery[]> {
  return request<RegulatoryDiscovery[]>("/api/discoveries");
}

export async function getSources(): Promise<RegulatorySource[]> {
  try {
    return await request<RegulatorySource[]>("/api/sources");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return [];
    throw error;
  }
}

export function refreshSources(): Promise<RegulatorySource[]> {
  return request<RegulatorySource[]>("/api/sources/refresh", { method: "POST" });
}

export function askRegLens(
  question: string,
  history: ChatHistoryMessage[] = [],
  contextProducts: string[] = [],
): Promise<AskResponse> {
  return request<AskResponse>("/api/ask", {
    method: "POST",
    body: JSON.stringify({
      question,
      history,
      context_products: contextProducts,
    }),
  });
}
