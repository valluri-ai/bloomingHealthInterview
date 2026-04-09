from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    embedding_provider: str
    embedding_model: str
    aws_region: str
    frontend_origins: tuple[str, ...]
    neo4j_uri: str | None
    neo4j_username: str | None
    neo4j_password: str | None
    neo4j_database: str
    prompt_vector_index_name: str
    prompt_fulltext_index_name: str
    prompt_s3_bucket: str | None
    prompt_s3_prefix: str
    prompt_store_root: str
    benchmark_dataset_path: str
    openai_api_key: str | None
    hybrid_ranker: str
    hybrid_alpha: float | None
    hybrid_rrf_k: int
    hybrid_candidate_multiplier: int
    merge_analysis_model: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv()
    hybrid_alpha = os.getenv("HYBRID_ALPHA")
    frontend_origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    )
    return Settings(
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "openai"),
        embedding_model=os.getenv("EMBEDDING_MODEL", os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")),
        aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
        frontend_origins=frontend_origins,
        neo4j_uri=os.getenv("NEO4J_URI"),
        neo4j_username=os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        prompt_vector_index_name=os.getenv("PROMPT_VECTOR_INDEX_NAME", "prompt_embedding_index"),
        prompt_fulltext_index_name=os.getenv("PROMPT_FULLTEXT_INDEX_NAME", "prompt_fulltext_index"),
        prompt_s3_bucket=os.getenv("PROMPT_S3_BUCKET"),
        prompt_s3_prefix=os.getenv("PROMPT_S3_PREFIX", "prompts"),
        prompt_store_root=os.getenv("PROMPT_STORE_ROOT", "tmp/prompt_store"),
        benchmark_dataset_path=os.getenv("BENCHMARK_DATASET_PATH", "tmp/benchmark-dataset-1000.json"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        hybrid_ranker=os.getenv("HYBRID_RANKER", "rrf"),
        hybrid_alpha=float(hybrid_alpha) if hybrid_alpha is not None else None,
        hybrid_rrf_k=int(os.getenv("HYBRID_RRF_K", "60")),
        hybrid_candidate_multiplier=int(os.getenv("HYBRID_CANDIDATE_MULTIPLIER", "5")),
        merge_analysis_model=os.getenv("MERGE_ANALYSIS_MODEL", "openai:gpt-4o-mini"),
    )
