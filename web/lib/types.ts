export type EmbeddingProviderName = "openai" | "bedrock";
export type RankerName = "rrf" | "naive" | "linear";
export type GraphMode = "duplicates" | "global" | "category" | "layer" | "prompt_family";
export type HierarchyKind = "prompt_path" | "category" | "layer_path";
export type DashboardTab = "load" | "embeddings" | "similar" | "search" | "clusters" | "graph";
export type DuplicateScopeMode = "category" | "hierarchy" | "prompt_family";
export type ClusterRunScopeMode = "global" | "category" | "hierarchy" | "prompt_family";
export type TenantSeedType = "empty" | "sample" | "benchmark_1k";

export interface PromptInput {
  prompt_id: string;
  category: string;
  layer: string;
  name?: string | null;
  content: string;
}

export interface TenantSummary {
  tenant_id: string;
  name: string;
  prompt_count: number;
  is_builtin: boolean;
  created_at?: string | null;
}

export interface PromptStorageInfo {
  prompt_id: string;
  bucket: string;
  key: string;
  version_id?: string | null;
  s3_uri: string;
}

export interface PromptLoadResponse {
  loaded_count: number;
  prompt_ids: string[];
  stored_prompts: PromptStorageInfo[];
}

export interface PromptListItem {
  prompt_id: string;
  name?: string | null;
  category: string;
  layer: string;
  layer_path: string;
  prompt_parent: string;
  available_embedding_models: string[];
}

export interface GenerateEmbeddingsResponse {
  generated_count: number;
  prompt_ids: string[];
  provider: EmbeddingProviderName;
  model: string;
}

export interface SimilarPromptResult {
  prompt_id: string;
  similarity_score?: number | null;
  fulltext_score?: number | null;
  ranking_score: number;
  content_preview: string;
  category?: string | null;
  layer_path?: string | null;
  prompt_parent?: string | null;
  prompt_path_lineage: string[];
  layer_lineage: string[];
  category_lineage: string[];
  input_variables: string[];
  match_sources: string[];
}

export interface ClusterEdge {
  source: string;
  target: string;
  similarity_score: number;
  ranking_score: number;
  shared_layer_path: boolean;
  shared_category: boolean;
  shared_prompt_path_parent: boolean;
}

export interface MergeSuggestion {
  canonical_prompt_id: string;
  rationale: string;
  optional_variables: string[];
  unified_prompt_template: string;
}

export interface DuplicateCluster {
  cluster_id: string;
  scope_mode?: string | null;
  scope_key?: string | null;
  member_count?: number | null;
  avg_similarity?: number | null;
  prompts: SimilarPromptResult[];
  edges: ClusterEdge[];
  merge_suggestion: MergeSuggestion;
}

export interface ClusterRunResponse {
  run_id: string;
  scope_mode: ClusterRunScopeMode;
  scope_key?: string | null;
  provider: EmbeddingProviderName | string;
  model: string;
  top_k: number;
  threshold: number;
  algorithm_version: string;
  created_at: string;
  category_filter?: string | null;
  hierarchy_filter?: string | null;
  cluster_count: number;
  clusters: DuplicateCluster[];
}

export interface ClusterRunSummary {
  run_id: string;
  scope_mode: ClusterRunScopeMode;
  scope_key?: string | null;
  provider: EmbeddingProviderName | string;
  model: string;
  top_k: number;
  threshold: number;
  algorithm_version: string;
  created_at: string;
  category_filter?: string | null;
  hierarchy_filter?: string | null;
  cluster_count: number;
}

export interface MergeAnalysisClusterInput {
  cluster_id: string;
  prompt_ids: string[];
}

export interface MergeAnalysisResult {
  cluster_id: string;
  prompt_ids: string[];
  analysis: {
    can_merge: boolean;
    confidence: number;
    canonical_prompt_id: string;
    merged_prompt_name: string;
    unified_prompt_template: string;
    variables_to_parameterize: string[];
    differences_to_preserve: string[];
    reasoning: string;
    migration_steps: string[];
  } | null;
  error?: string | null;
}

export interface MergeAnalysisResponse {
  scope: {
    hierarchy?: string | null;
    category?: string | null;
  };
  results: MergeAnalysisResult[];
}

export interface VisualizationNode {
  id: string;
  label: string;
  category?: string;
  layer_path?: string;
  prompt_parent?: string;
  input_variables?: string[];
}

export interface ClusterVisualizationResponse {
  nodes: VisualizationNode[];
  edges: ClusterEdge[];
  clusters: DuplicateCluster[];
}

export interface ExplorerGraphResponse {
  tenant_id: string;
  view: string;
  filters: {
    category?: string | null;
    hierarchy?: string | null;
    layer_path?: string | null;
    prompt_query?: string | null;
  };
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
  summary: {
    prompt_count: number;
    category_count: number;
    layer_count?: number;
  };
}

export interface PromptGraphResponse {
  prompt_id: string;
  name?: string | null;
  category: string;
  layer_path: string;
  prompt_parent: string;
  prompt_path_lineage: string[];
  layer_lineage: string[];
  category_lineage: string[];
  variables: string[];
  storage: {
    bucket?: string | null;
    key?: string | null;
    version_id?: string | null;
    s3_uri?: string | null;
  };
}

export interface ScopeClusterGroup {
  scope_type: string;
  scope_value: string;
  prompt_count: number;
  clusters: DuplicateCluster[];
}

export interface DuplicateScopeGroup {
  scope_type: DuplicateScopeMode;
  scope_value: string;
  prompt_count: number;
  clusters: DuplicateCluster[];
}

export interface ScopeClustersResponse {
  prompt_id: string;
  category: ScopeClusterGroup;
  layer: ScopeClusterGroup;
  prompt_family: ScopeClusterGroup;
}

export interface SimilarDrilldownResponse {
  prompt_id: string;
  global: SimilarPromptResult[];
  same_layer: SimilarPromptResult[];
  same_category: SimilarPromptResult[];
  same_prompt_family: SimilarPromptResult[];
}

export interface HierarchyUpsertResponse {
  kind: HierarchyKind;
  path: string;
  node_ids: string[];
}

export interface SearchParamsPayload {
  limit?: number;
  threshold?: number;
  ranker?: RankerName;
  provider?: EmbeddingProviderName;
  model?: string;
  alpha?: number;
  rrf_k?: number;
  candidate_multiplier?: number;
  neighbor_limit?: number;
  category_filter?: string;
  hierarchy_filter?: string;
}

export interface ApiLabResult {
  ok: boolean;
  status?: number;
  body?: unknown;
  error?: string;
  timestamp: string;
}
