from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, Header, HTTPException

from app.core.config import Settings, get_settings
from app.domain.models import TenantContext
from app.repositories.filesystem_prompt_store import FilesystemPromptStore
from app.repositories.neo4j_prompt_repository import Neo4jPromptRepository
from app.repositories.prompt_repository import PromptTemplateStore
from app.repositories.s3_prompt_store import S3PromptStore
from app.repositories.tenant_scoped_prompt_repository import TenantScopedPromptRepository
from app.repositories.tenant_scoped_prompt_store import TenantScopedPromptStore
from app.services.analysis_service import ClusterAnalysisService
from app.services.embedding_service import EmbeddingService
from app.services.merge_analysis_service import PromptMergeAnalysisService
from app.services.prompt_ingestion_service import PromptIngestionService
from app.services.similarity_service import SimilarityService
from app.services.tenant_service import TenantService


def _require(value: str | None, env_name: str) -> str:
    if not value:
        raise RuntimeError(f"{env_name} is not configured")
    return value


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    settings = get_settings()
    return EmbeddingService(
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        aws_region=settings.aws_region,
    )


@lru_cache(maxsize=1)
def get_base_prompt_repository() -> Neo4jPromptRepository:
    settings = get_settings()
    embedding_service = get_embedding_service()
    return Neo4jPromptRepository(
        uri=_require(settings.neo4j_uri, "NEO4J_URI"),
        username=_require(settings.neo4j_username, "NEO4J_USERNAME"),
        password=_require(settings.neo4j_password, "NEO4J_PASSWORD"),
        database=settings.neo4j_database,
        vector_index_name=settings.prompt_vector_index_name,
        fulltext_index_name=settings.prompt_fulltext_index_name,
        embedder=embedding_service.build_graphrag_embedder(),
    )


@lru_cache(maxsize=1)
def get_base_prompt_store() -> PromptTemplateStore:
    settings = get_settings()
    if not settings.prompt_s3_bucket:
        return FilesystemPromptStore(root=settings.prompt_store_root)
    return S3PromptStore(
        bucket=_require(settings.prompt_s3_bucket, "PROMPT_S3_BUCKET"),
        prefix=settings.prompt_s3_prefix,
    )


def get_tenant_context(x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")) -> TenantContext:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is required")
    repo = get_base_prompt_repository()
    if not repo.tenant_exists(x_tenant_id):
        raise HTTPException(status_code=404, detail=f"Tenant not found: {x_tenant_id}")
    return TenantContext(tenant_id=x_tenant_id)
def get_prompt_repository(tenant: TenantContext = Depends(get_tenant_context)) -> TenantScopedPromptRepository:
    return TenantScopedPromptRepository(
        base_repo=get_base_prompt_repository(),
        tenant_id=tenant.tenant_id,
    )
def get_prompt_store(tenant: TenantContext = Depends(get_tenant_context)) -> TenantScopedPromptStore:
    return TenantScopedPromptStore(
        base_store=get_base_prompt_store(),
        tenant_id=tenant.tenant_id,
    )


def get_prompt_ingestion_service(
    repo: TenantScopedPromptRepository = Depends(get_prompt_repository),
    store: TenantScopedPromptStore = Depends(get_prompt_store),
) -> PromptIngestionService:
    return PromptIngestionService(
        repo=repo,
        prompt_store=store,
    )


def get_similarity_service(
    repo: TenantScopedPromptRepository = Depends(get_prompt_repository),
) -> SimilarityService:
    return SimilarityService(repo)


def get_analysis_service(
    repo: TenantScopedPromptRepository = Depends(get_prompt_repository),
    similarity_service: SimilarityService = Depends(get_similarity_service),
) -> ClusterAnalysisService:
    return ClusterAnalysisService(repo, similarity_service)


def get_merge_analysis_service(
    repo: TenantScopedPromptRepository = Depends(get_prompt_repository),
    store: TenantScopedPromptStore = Depends(get_prompt_store),
) -> PromptMergeAnalysisService:
    settings = get_settings()
    return PromptMergeAnalysisService(
        repo=repo,
        prompt_store=store,
        default_model=settings.merge_analysis_model,
    )


def get_tenant_service() -> TenantService:
    settings = get_settings()
    return TenantService(
        repo=get_base_prompt_repository(),
        prompt_store=get_base_prompt_store(),
        benchmark_dataset_path=settings.benchmark_dataset_path,
    )


def get_runtime_settings() -> Settings:
    return get_settings()
