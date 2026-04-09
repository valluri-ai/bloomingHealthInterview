from __future__ import annotations

from html import escape
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.api.dependencies import (
    get_embedding_service,
    get_analysis_service,
    get_merge_analysis_service,
    get_prompt_ingestion_service,
    get_prompt_repository,
    get_prompt_store,
    get_tenant_context,
    get_tenant_service,
)
from app.domain.models import TenantContext
from app.repositories.prompt_repository import PromptGraphRepository
from app.schemas.prompt import (
    ClusterVisualizationResponse,
    ClusterRunCreateRequest,
    ClusterRunResponse,
    ClusterRunSummary,
    EmbeddingGenerateRequest,
    ExplorerGraphResponse,
    HierarchyUpsertRequest,
    MergeSuggestionRequest,
    MergeSuggestionResponse,
    PromptListItem,
    PromptLoadRequest,
    PromptLoadResponse,
    SemanticSearchRequest,
    TenantCreateRequest,
    TenantSummary,
)
from app.services.analysis_service import ClusterAnalysisService
from app.services.embedding_service import EmbeddingService
from app.services.hierarchy_service import HierarchyService
from app.services.merge_analysis_service import PromptMergeAnalysisService
from app.services.prompt_ingestion_service import PromptIngestionService
from app.services.similarity_service import SimilarityService
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/api", tags=["prompts"])


def _render_prompt_preview_html(prompt: object, document: dict[str, object]) -> str:
    prompt_id = escape(str(getattr(prompt, "prompt_id", document.get("prompt_id", ""))))
    title = escape(str(getattr(prompt, "name", None) or document.get("name") or prompt_id))
    category = escape(str(getattr(prompt, "category", document.get("category", ""))))
    layer = escape(str(getattr(prompt, "layer", document.get("layer", ""))))
    content = escape(str(document.get("content", "")))
    variables = getattr(prompt, "input_variables", ()) or ()
    variable_markup = "".join(
        f"<li>{escape(str(variable))}</li>"
        for variable in variables
    )
    storage_markup = "".join(
        [
            f"<div><strong>Bucket:</strong> {escape(str(getattr(prompt, 'storage_bucket', '') or ''))}</div>",
            f"<div><strong>Key:</strong> {escape(str(getattr(prompt, 'storage_key', '') or ''))}</div>",
            f"<div><strong>Version:</strong> {escape(str(getattr(prompt, 'storage_version_id', '') or ''))}</div>",
        ]
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        color-scheme: dark;
        --bg: #111212;
        --panel: rgba(25, 27, 29, 0.92);
        --text: #f4efe4;
        --muted: #b8b0a2;
        --accent: #7fe7f2;
        --line: rgba(191, 148, 74, 0.28);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background:
          radial-gradient(circle at top, rgba(127, 231, 242, 0.08), transparent 30%),
          linear-gradient(180deg, #17191b 0%, #101112 100%);
        color: var(--text);
        padding: 24px;
      }}
      .sheet {{
        max-width: 960px;
        margin: 0 auto;
        border: 1px solid var(--line);
        background: var(--panel);
        padding: 28px;
        border-radius: 20px;
        box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
      }}
      .eyebrow {{
        color: var(--accent);
        font: 600 12px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
        text-transform: uppercase;
        letter-spacing: 0.22em;
      }}
      h1 {{
        margin: 10px 0 18px;
        font-size: 40px;
        line-height: 1;
      }}
      .meta {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-bottom: 24px;
        color: var(--muted);
        font: 500 14px/1.5 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      .block {{
        border-top: 1px solid var(--line);
        padding-top: 18px;
        margin-top: 18px;
      }}
      pre {{
        white-space: pre-wrap;
        margin: 0;
        font: 500 16px/1.7 ui-monospace, SFMono-Regular, Menlo, monospace;
      }}
      ul {{
        margin: 0;
        padding-left: 18px;
      }}
    </style>
  </head>
  <body>
    <article class="sheet">
      <div class="eyebrow">Prompt Document</div>
      <h1>{title}</h1>
      <div class="meta">
        <div><strong>ID:</strong> {prompt_id}</div>
        <div><strong>Category:</strong> {category}</div>
        <div><strong>Layer:</strong> {layer}</div>
      </div>
      <section class="block">
        <div class="eyebrow">Variables</div>
        <ul>{variable_markup or '<li>None</li>'}</ul>
      </section>
      <section class="block">
        <div class="eyebrow">Content</div>
        <pre>{content}</pre>
      </section>
      <section class="block">
        <div class="eyebrow">Storage</div>
        <div class="meta">{storage_markup}</div>
      </section>
    </article>
  </body>
</html>"""


@router.post("/prompts/load", response_model=PromptLoadResponse)
def load_prompts(
    request: PromptLoadRequest,
    service: PromptIngestionService = Depends(get_prompt_ingestion_service),
    _: TenantContext = Depends(get_tenant_context),
):
    return service.ingest_prompts(request.prompts)


@router.get("/prompts", response_model=list[PromptListItem])
def list_prompts(
    repo: PromptGraphRepository = Depends(get_prompt_repository),
    _: TenantContext = Depends(get_tenant_context),
):
    return repo.list_prompts()


@router.get("/tenants", response_model=list[TenantSummary])
def list_tenants(
    service: TenantService = Depends(get_tenant_service),
):
    return service.list_tenants()


@router.post("/tenants", response_model=TenantSummary)
def create_tenant(
    request: TenantCreateRequest,
    service: TenantService = Depends(get_tenant_service),
):
    return service.create_tenant(
        tenant_id=request.tenant_id,
        name=request.name,
        seed_type=request.seed_type,
    )


@router.post("/embeddings/generate")
def generate_embeddings(
    request: EmbeddingGenerateRequest,
    repo: PromptGraphRepository = Depends(get_prompt_repository),
    _: TenantContext = Depends(get_tenant_context),
):
    prompt_ids = request.prompt_ids or repo.list_prompt_ids()
    if not prompt_ids:
        raise HTTPException(status_code=400, detail="No prompts available for embedding")

    missing_ids = [prompt_id for prompt_id in prompt_ids if repo.get_prompt(prompt_id) is None]
    if missing_ids:
        raise HTTPException(status_code=404, detail={"missing_prompt_ids": missing_ids})

    embedding_service = EmbeddingService(
        provider=request.provider,
        model=request.model,
    )
    repo.ensure_schema(
        vector_dimensions=embedding_service.dimensions,
        embedding_property=embedding_service.embedding_property(),
        index_name=embedding_service.vector_index_name(repo.vector_index_name),
    )
    generated_count = repo.generate_embeddings(
        prompt_ids=prompt_ids,
        embed_batch=embedding_service.embed_texts,
        batch_size=request.batch_size,
        vector_dimensions=embedding_service.dimensions,
        embedding_property=embedding_service.embedding_property(),
        model_label=embedding_service.model_label(),
    )
    return {
        "generated_count": generated_count,
        "prompt_ids": prompt_ids,
        "provider": request.provider,
        "model": request.model,
    }


@router.get("/prompts/{prompt_id}/similar")
def get_similar_prompts(
    prompt_id: str,
    limit: int = Query(default=5, ge=1, le=100),
    threshold: float = Query(default=0.0, ge=0.0, le=1.0),
    ranker: str = Query(default="rrf"),
    alpha: float | None = Query(default=None, ge=0.0, le=1.0),
    rrf_k: int = Query(default=60, ge=1, le=500),
    candidate_multiplier: int = Query(default=5, ge=1, le=50),
    provider: str = Query(default="openai"),
    model: str = Query(default="text-embedding-3-large"),
    repo: PromptGraphRepository = Depends(get_prompt_repository),
    _: TenantContext = Depends(get_tenant_context),
):
    if repo.get_prompt(prompt_id) is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    service = SimilarityService(repo)
    return service.find_similar_by_prompt_id(
        prompt_id,
        limit=limit,
        threshold=threshold,
        ranker=ranker,
        alpha=alpha,
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
        provider=provider,
        model=model,
    )


@router.get("/prompts/{prompt_id}/similar/drilldown")
def get_similar_prompts_drilldown(
    prompt_id: str,
    limit: int = Query(default=5, ge=1, le=100),
    ranker: str = Query(default="rrf"),
    alpha: float | None = Query(default=None, ge=0.0, le=1.0),
    rrf_k: int = Query(default=60, ge=1, le=500),
    candidate_multiplier: int = Query(default=5, ge=1, le=50),
    service: ClusterAnalysisService = Depends(get_analysis_service),
    repo: PromptGraphRepository = Depends(get_prompt_repository),
    _: TenantContext = Depends(get_tenant_context),
):
    if repo.get_prompt(prompt_id) is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return service.drilldown_for_prompt(
        prompt_id=prompt_id,
        limit=limit,
        ranker=ranker,
        alpha=alpha,
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
    )


@router.get("/prompts/{prompt_id}/graph")
def get_prompt_graph(
    prompt_id: str,
    repo: PromptGraphRepository = Depends(get_prompt_repository),
    _: TenantContext = Depends(get_tenant_context),
):
    try:
        return repo.get_prompt_graph(prompt_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/prompts/{prompt_id}/preview", response_class=HTMLResponse)
def get_prompt_preview(
    prompt_id: str,
    repo: PromptGraphRepository = Depends(get_prompt_repository),
    prompt_store=Depends(get_prompt_store),
    _: TenantContext = Depends(get_tenant_context),
):
    prompt = repo.get_prompt(prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    document = None
    storage_key = getattr(prompt, "storage_key", None)
    if storage_key:
        document = prompt_store.get_prompt_by_storage(
            bucket=getattr(prompt, "storage_bucket", None),
            key=storage_key,
            version_id=getattr(prompt, "storage_version_id", None),
        )
    if document is None:
        document = prompt_store.get_prompt(prompt_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Prompt document not found")
    return HTMLResponse(content=_render_prompt_preview_html(prompt, document))


@router.post("/search/semantic")
def search_semantic(
    request: SemanticSearchRequest,
    repo: PromptGraphRepository = Depends(get_prompt_repository),
    _: TenantContext = Depends(get_tenant_context),
):
    embedding_service = EmbeddingService(
        provider=request.provider,
        model=request.model,
    )
    service = SimilarityService(repo)
    query_vector = embedding_service.embed_query(request.query)
    return service.search_semantic(
        query=request.query,
        query_vector=query_vector,
        limit=request.limit,
        threshold=request.threshold,
        ranker=request.ranker,
        alpha=request.alpha,
        rrf_k=request.rrf_k,
        candidate_multiplier=request.candidate_multiplier,
        provider=request.provider,
        model=request.model,
    )


@router.get("/analysis/duplicates")
def get_duplicates(
    threshold: float = Query(default=0.9, ge=0.0, le=1.0),
    neighbor_limit: int = Query(default=10, ge=1, le=100),
    ranker: str = Query(default="rrf"),
    alpha: float | None = Query(default=None, ge=0.0, le=1.0),
    rrf_k: int = Query(default=60, ge=1, le=500),
    candidate_multiplier: int = Query(default=5, ge=1, le=50),
    provider: str = Query(default="openai"),
    model: str = Query(default="text-embedding-3-large"),
    category_filter: str | None = Query(default=None),
    hierarchy_filter: str | None = Query(default=None),
    service: ClusterAnalysisService = Depends(get_analysis_service),
    _: TenantContext = Depends(get_tenant_context),
):
    return service.analyze_duplicates(
        threshold=threshold,
        neighbor_limit=neighbor_limit,
        ranker=ranker,
        alpha=alpha,
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
        provider=provider,
        model=model,
        category_filter=category_filter,
        hierarchy_filter=hierarchy_filter,
    )


@router.get("/analysis/duplicates/scoped")
def get_scoped_duplicates(
    scope_mode: Literal["category", "hierarchy", "prompt_family"] = Query(default="category"),
    threshold: float = Query(default=0.9, ge=0.0, le=1.0),
    neighbor_limit: int = Query(default=10, ge=1, le=100),
    ranker: str = Query(default="rrf"),
    alpha: float | None = Query(default=None, ge=0.0, le=1.0),
    rrf_k: int = Query(default=60, ge=1, le=500),
    candidate_multiplier: int = Query(default=5, ge=1, le=50),
    provider: str = Query(default="openai"),
    model: str = Query(default="text-embedding-3-large"),
    category_filter: str | None = Query(default=None),
    hierarchy_filter: str | None = Query(default=None),
    service: ClusterAnalysisService = Depends(get_analysis_service),
    _: TenantContext = Depends(get_tenant_context),
):
    return service.analyze_scoped_duplicates(
        scope_mode=scope_mode,
        threshold=threshold,
        neighbor_limit=neighbor_limit,
        ranker=ranker,
        alpha=alpha,
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
        provider=provider,
        model=model,
        category_filter=category_filter,
        hierarchy_filter=hierarchy_filter,
    )


@router.post("/analysis/clusters/run", response_model=ClusterRunResponse)
def create_cluster_run(
    request: ClusterRunCreateRequest,
    service: ClusterAnalysisService = Depends(get_analysis_service),
    _: TenantContext = Depends(get_tenant_context),
):
    return service.create_cluster_run(
        scope_mode=request.scope_mode,
        scope_key=request.scope_key,
        threshold=request.threshold,
        neighbor_limit=request.neighbor_limit,
        ranker=request.ranker,
        alpha=request.alpha,
        rrf_k=request.rrf_k,
        candidate_multiplier=request.candidate_multiplier,
        provider=request.provider,
        model=request.model,
        category_filter=request.category_filter,
        hierarchy_filter=request.hierarchy_filter,
    )


@router.get("/analysis/runs", response_model=list[ClusterRunSummary])
def list_cluster_runs(
    service: ClusterAnalysisService = Depends(get_analysis_service),
    _: TenantContext = Depends(get_tenant_context),
):
    return service.list_cluster_runs()


@router.get("/analysis/runs/{run_id}", response_model=ClusterRunResponse)
def get_cluster_run(
    run_id: str,
    service: ClusterAnalysisService = Depends(get_analysis_service),
    _: TenantContext = Depends(get_tenant_context),
):
    run = service.get_cluster_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Cluster run not found")
    return run


@router.post("/analysis/merge-suggestions", response_model=MergeSuggestionResponse)
def get_merge_suggestions(
    request: MergeSuggestionRequest,
    service: PromptMergeAnalysisService = Depends(get_merge_analysis_service),
    _: TenantContext = Depends(get_tenant_context),
):
    return service.analyze_clusters(
        clusters=[cluster.model_dump(mode="json") for cluster in request.clusters],
        scope_hierarchy=request.scope_hierarchy,
        scope_category=request.scope_category,
        analysis_model=request.analysis_model,
    )


@router.get("/analysis/prompts/{prompt_id}/scopes")
def get_scope_clusters(
    prompt_id: str,
    threshold: float = Query(default=0.9, ge=0.0, le=1.0),
    neighbor_limit: int = Query(default=10, ge=1, le=100),
    ranker: str = Query(default="rrf"),
    alpha: float | None = Query(default=None, ge=0.0, le=1.0),
    rrf_k: int = Query(default=60, ge=1, le=500),
    candidate_multiplier: int = Query(default=5, ge=1, le=50),
    provider: str = Query(default="openai"),
    model: str = Query(default="text-embedding-3-large"),
    service: ClusterAnalysisService = Depends(get_analysis_service),
    repo: PromptGraphRepository = Depends(get_prompt_repository),
    _: TenantContext = Depends(get_tenant_context),
):
    if repo.get_prompt(prompt_id) is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return service.analyze_scope_clusters(
        prompt_id=prompt_id,
        threshold=threshold,
        neighbor_limit=neighbor_limit,
        ranker=ranker,
        alpha=alpha,
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
        provider=provider,
        model=model,
    )


@router.get("/analysis/runs/{run_id}/visualization", response_model=ClusterVisualizationResponse)
def get_cluster_run_visualization(
    run_id: str,
    service: ClusterAnalysisService = Depends(get_analysis_service),
    _: TenantContext = Depends(get_tenant_context),
):
    visualization = service.build_cluster_run_visualization(run_id=run_id)
    if visualization is None:
        raise HTTPException(status_code=404, detail="Cluster run not found")
    return visualization


@router.get("/analysis/runs/{run_id}/clusters/{cluster_id}")
def get_cluster_run_detail(
    run_id: str,
    cluster_id: str,
    service: ClusterAnalysisService = Depends(get_analysis_service),
    _: TenantContext = Depends(get_tenant_context),
):
    result = service.get_cluster_run_detail(
        run_id=run_id,
        cluster_id=cluster_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return result


@router.post("/hierarchy/upsert")
def upsert_hierarchy(
    request: HierarchyUpsertRequest,
    repo: PromptGraphRepository = Depends(get_prompt_repository),
    _: TenantContext = Depends(get_tenant_context),
):
    hierarchy = HierarchyService()
    nodes = hierarchy.build_path(request.kind, request.path)
    repo.upsert_hierarchy_nodes(nodes)
    return {
        "kind": request.kind,
        "path": request.path,
        "node_ids": [node.node_id for node in nodes],
    }


@router.get("/graph/explorer", response_model=ExplorerGraphResponse)
def get_graph_explorer(
    view: str = Query(default="global"),
    category: str | None = Query(default=None),
    hierarchy: str | None = Query(default=None),
    layer_path: str | None = Query(default=None),
    prompt_query: str | None = Query(default=None),
    repo: PromptGraphRepository = Depends(get_prompt_repository),
    _: TenantContext = Depends(get_tenant_context),
):
    return repo.get_explorer_graph(
        view=view,
        category=category,
        hierarchy=hierarchy,
        layer_path=layer_path,
        prompt_query=prompt_query,
    )
