import type {
  ApiLabResult,
  ClusterVisualizationResponse,
  ClusterRunResponse,
  ClusterRunSummary,
  DuplicateCluster,
  DuplicateScopeGroup,
  DuplicateScopeMode,
  EmbeddingProviderName,
  ExplorerGraphResponse,
  GenerateEmbeddingsResponse,
  HierarchyKind,
  HierarchyUpsertResponse,
  MergeAnalysisClusterInput,
  MergeAnalysisResponse,
  PromptInput,
  PromptListItem,
  PromptLoadResponse,
  RankerName,
  SearchParamsPayload,
  SimilarPromptResult,
  ClusterRunScopeMode,
  TenantSeedType,
  TenantSummary,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8001" : "");

function buildQueryString(params: Record<string, string | number | undefined>) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") {
      continue;
    }
    searchParams.set(key, String(value));
  }
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

async function request<T>(path: string, init?: RequestInit, tenantId?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(tenantId ? { "X-Tenant-Id": tenantId } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.text();
      if (body) {
        try {
          detail = JSON.stringify(JSON.parse(body), null, 2);
        } catch {
          detail = body;
        }
      }
    } catch {
      detail = response.statusText;
    }
    throw new Error(`${response.status} ${detail}`);
  }

  return (await response.json()) as T;
}

async function requestText(path: string, init?: RequestInit, tenantId?: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(tenantId ? { "X-Tenant-Id": tenantId } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.text();
      if (body) {
        try {
          detail = JSON.stringify(JSON.parse(body), null, 2);
        } catch {
          detail = body;
        }
      }
    } catch {
      detail = response.statusText;
    }
    throw new Error(`${response.status} ${detail}`);
  }
  return response.text();
}

export async function getPromptPreviewHtml(tenantId: string, promptId: string) {
  return requestText(`/api/prompts/${encodeURIComponent(promptId)}/preview`, undefined, tenantId);
}

export async function getTenants() {
  return request<TenantSummary[]>("/api/tenants");
}

export async function createTenant(input: {
  name: string;
  tenant_id?: string;
  seed_type: TenantSeedType;
}) {
  return request<TenantSummary>("/api/tenants", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function loadPrompts(tenantId: string, prompts: PromptInput[]) {
  return request<PromptLoadResponse>("/api/prompts/load", {
    method: "POST",
    body: JSON.stringify({ prompts }),
  }, tenantId);
}

export async function getPrompts(tenantId: string) {
  return request<PromptListItem[]>("/api/prompts", undefined, tenantId);
}

export async function generateEmbeddings(input: {
  tenantId: string;
  prompt_ids?: string[];
  batch_size: number;
  provider: EmbeddingProviderName;
  model: string;
}) {
  const { tenantId, ...payload } = input;
  return request<GenerateEmbeddingsResponse>("/api/embeddings/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  }, tenantId);
}

export async function getSimilarPrompts(
  tenantId: string,
  promptId: string,
  input: SearchParamsPayload,
) {
  return request<SimilarPromptResult[]>(
    `/api/prompts/${encodeURIComponent(promptId)}/similar${buildQueryString({
      limit: input.limit,
      threshold: input.threshold,
      ranker: input.ranker,
      provider: input.provider,
      model: input.model,
      alpha: input.alpha,
      rrf_k: input.rrf_k,
      candidate_multiplier: input.candidate_multiplier,
    })}`,
    undefined,
    tenantId,
  );
}

export async function semanticSearch(input: {
  tenantId: string;
  query: string;
  limit: number;
  threshold?: number;
  ranker?: RankerName;
  provider: EmbeddingProviderName;
  model: string;
}) {
  const { tenantId, ...payload } = input;
  return request<SimilarPromptResult[]>("/api/search/semantic", {
    method: "POST",
    body: JSON.stringify(payload),
  }, tenantId);
}

export async function getDuplicates(tenantId: string, input: SearchParamsPayload) {
  return request<DuplicateCluster[]>(
    `/api/analysis/duplicates${buildQueryString({
      threshold: input.threshold,
      provider: input.provider,
      model: input.model,
      neighbor_limit: input.neighbor_limit,
      ranker: input.ranker,
      alpha: input.alpha,
      rrf_k: input.rrf_k,
      candidate_multiplier: input.candidate_multiplier,
      category_filter: input.category_filter,
      hierarchy_filter: input.hierarchy_filter,
    })}`,
    undefined,
    tenantId,
  );
}

export async function getScopedDuplicates(tenantId: string, input: SearchParamsPayload & { scope_mode: DuplicateScopeMode }) {
  return request<DuplicateScopeGroup[]>(
    `/api/analysis/duplicates/scoped${buildQueryString({
      scope_mode: input.scope_mode,
      threshold: input.threshold,
      provider: input.provider,
      model: input.model,
      neighbor_limit: input.neighbor_limit,
      ranker: input.ranker,
      alpha: input.alpha,
      rrf_k: input.rrf_k,
      candidate_multiplier: input.candidate_multiplier,
      category_filter: input.category_filter,
      hierarchy_filter: input.hierarchy_filter,
    })}`,
    undefined,
    tenantId,
  );
}

export async function createClusterRun(input: {
  tenantId: string;
  scope_mode: ClusterRunScopeMode;
  scope_key?: string;
  threshold: number;
  neighbor_limit?: number;
  ranker?: RankerName;
  provider: EmbeddingProviderName;
  model: string;
  category_filter?: string;
  hierarchy_filter?: string;
}) {
  const { tenantId, ...payload } = input;
  return request<ClusterRunResponse>("/api/analysis/clusters/run", {
    method: "POST",
    body: JSON.stringify(payload),
  }, tenantId);
}

export async function getClusterRun(tenantId: string, runId: string) {
  return request<ClusterRunResponse>(`/api/analysis/runs/${encodeURIComponent(runId)}`, undefined, tenantId);
}

export async function getClusterRuns(tenantId: string) {
  return request<ClusterRunSummary[]>("/api/analysis/runs", undefined, tenantId);
}

export async function getClusterRunVisualization(tenantId: string, runId: string) {
  return request<ClusterVisualizationResponse>(
    `/api/analysis/runs/${encodeURIComponent(runId)}/visualization`,
    undefined,
    tenantId,
  );
}

export async function getClusterRunDetail(tenantId: string, runId: string, clusterId: string) {
  return request<DuplicateCluster>(
    `/api/analysis/runs/${encodeURIComponent(runId)}/clusters/${encodeURIComponent(clusterId)}`,
    undefined,
    tenantId,
  );
}

export async function analyzeMergeSuggestions(input: {
  tenantId: string;
  clusters: MergeAnalysisClusterInput[];
  scope_hierarchy?: string;
  scope_category?: string;
  analysis_model?: string;
}) {
  const { tenantId, ...payload } = input;
  return request<MergeAnalysisResponse>("/api/analysis/merge-suggestions", {
    method: "POST",
    body: JSON.stringify(payload),
  }, tenantId);
}

export async function upsertHierarchy(input: {
  tenantId: string;
  kind: HierarchyKind;
  path: string;
}) {
  const { tenantId, ...payload } = input;
  return request<HierarchyUpsertResponse>("/api/hierarchy/upsert", {
    method: "POST",
    body: JSON.stringify(payload),
  }, tenantId);
}

export async function getExplorerGraph(
  tenantId: string,
  input: {
    view: string;
    category?: string;
    hierarchy?: string;
    layer_path?: string;
    prompt_query?: string;
  },
) {
  return request<ExplorerGraphResponse>(
    `/api/graph/explorer${buildQueryString({
      view: input.view,
      category: input.category,
      hierarchy: input.hierarchy,
      layer_path: input.layer_path,
      prompt_query: input.prompt_query,
    })}`,
    undefined,
    tenantId,
  );
}

export async function runApiLabRequest(
  action: () => Promise<unknown>,
): Promise<ApiLabResult> {
  const timestamp = new Date().toISOString();
  try {
    const body = await action();
    return { ok: true, body, timestamp };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Unknown error",
      timestamp,
    };
  }
}
