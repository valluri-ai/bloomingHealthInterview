from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EmbeddingProviderName = Literal["openai", "bedrock"]
RankerName = Literal["rrf", "naive", "linear"]
ClusterRunScopeMode = Literal["global", "category", "hierarchy", "prompt_family"]
TenantSeedType = Literal["empty", "sample", "benchmark_1k"]


class PromptInput(BaseModel):
    prompt_id: str
    category: str
    layer: str
    name: str | None = None
    content: str


class PromptStorageInfo(BaseModel):
    prompt_id: str
    bucket: str
    key: str
    version_id: str | None = None
    s3_uri: str


class PromptLoadRequest(BaseModel):
    prompts: list[PromptInput]


class PromptLoadResponse(BaseModel):
    loaded_count: int
    prompt_ids: list[str]
    stored_prompts: list[PromptStorageInfo]


class TenantSummary(BaseModel):
    tenant_id: str
    name: str
    prompt_count: int = 0
    is_builtin: bool = False
    created_at: str | None = None


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    tenant_id: str | None = None
    seed_type: TenantSeedType = "empty"


class PromptListItem(BaseModel):
    prompt_id: str
    name: str | None = None
    category: str
    layer: str
    layer_path: str
    prompt_parent: str
    available_embedding_models: list[str] = Field(default_factory=list)


class EmbeddingGenerateRequest(BaseModel):
    prompt_ids: list[str] | None = None
    batch_size: int = Field(default=32, ge=1, le=512)
    provider: EmbeddingProviderName = "openai"
    model: str = "text-embedding-3-large"


class SimilarityOptions(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)
    threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    ranker: RankerName = "rrf"
    alpha: float | None = Field(default=None, ge=0.0, le=1.0)
    rrf_k: int = Field(default=60, ge=1, le=500)
    candidate_multiplier: int = Field(default=5, ge=1, le=50)
    provider: EmbeddingProviderName = "openai"
    model: str = "text-embedding-3-large"


class SemanticSearchRequest(SimilarityOptions):
    query: str = Field(min_length=1)


class SimilarPromptResult(BaseModel):
    prompt_id: str
    similarity_score: float | None = None
    fulltext_score: float | None = None
    ranking_score: float
    content_preview: str
    category: str | None = None
    layer_path: str | None = None
    prompt_parent: str | None = None
    prompt_path_lineage: list[str] = Field(default_factory=list)
    layer_lineage: list[str] = Field(default_factory=list)
    category_lineage: list[str] = Field(default_factory=list)
    input_variables: list[str] = Field(default_factory=list)
    match_sources: list[str] = Field(default_factory=list)


class DuplicateCluster(BaseModel):
    cluster_id: str
    scope_mode: str | None = None
    scope_key: str | None = None
    member_count: int | None = None
    avg_similarity: float | None = None
    prompts: list[SimilarPromptResult]
    edges: list[dict[str, Any]]
    merge_suggestion: dict[str, Any]


class ClusterRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_mode: ClusterRunScopeMode = "global"
    scope_key: str | None = None
    threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    neighbor_limit: int = Field(default=10, ge=1, le=100)
    ranker: RankerName = "rrf"
    alpha: float | None = Field(default=None, ge=0.0, le=1.0)
    rrf_k: int = Field(default=60, ge=1, le=500)
    candidate_multiplier: int = Field(default=5, ge=1, le=50)
    provider: EmbeddingProviderName = "openai"
    model: str = "text-embedding-3-large"
    category_filter: str | None = None
    hierarchy_filter: str | None = None


class ClusterRunSummary(BaseModel):
    run_id: str
    scope_mode: ClusterRunScopeMode
    scope_key: str | None = None
    provider: EmbeddingProviderName | str
    model: str
    top_k: int
    threshold: float
    algorithm_version: str
    created_at: str
    category_filter: str | None = None
    hierarchy_filter: str | None = None
    cluster_count: int = 0


class ClusterRunResponse(ClusterRunSummary):
    clusters: list[DuplicateCluster] = Field(default_factory=list)


class MergeSuggestionClusterInput(BaseModel):
    cluster_id: str
    prompt_ids: list[str] = Field(min_length=2)


class MergeSuggestionRequest(BaseModel):
    clusters: list[MergeSuggestionClusterInput] = Field(min_length=1)
    scope_hierarchy: str | None = None
    scope_category: str | None = None
    analysis_model: str | None = None


class MergeSuggestionClusterResult(BaseModel):
    cluster_id: str
    prompt_ids: list[str]
    analysis: dict[str, Any] | None = None
    error: str | None = None


class MergeSuggestionResponse(BaseModel):
    scope: dict[str, str | None]
    results: list[MergeSuggestionClusterResult]


class ClusterVisualizationResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    clusters: list[dict[str, Any]]


class ExplorerGraphResponse(BaseModel):
    tenant_id: str
    view: str
    filters: dict[str, str | None]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    summary: dict[str, int]


class HierarchyUpsertRequest(BaseModel):
    kind: Literal["prompt_path", "category", "layer_path"]
    path: str = Field(min_length=1)
