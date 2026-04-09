from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.models import PromptGraphPayload, PromptRecord, StoredPromptVersion
from app.schemas.prompt import PromptInput


@dataclass
class FakePromptStore:
    bucket: str = "core-prompts-057286249135"
    version_id: str = "v1"

    def __post_init__(self) -> None:
        self.calls: list[PromptInput] = []
        self.documents: dict[str, dict[str, Any]] = {}

    def store_prompt(self, prompt: PromptInput) -> StoredPromptVersion:
        self.calls.append(prompt)
        key = f"prompts/{prompt.prompt_id}.json"
        self.documents[prompt.prompt_id] = prompt.model_dump(mode="json")
        return StoredPromptVersion(
            bucket=self.bucket,
            key=key,
            version_id=self.version_id,
            etag="fake-etag",
            s3_uri=f"s3://{self.bucket}/{key}",
        )

    def get_prompt(self, prompt_id: str) -> dict[str, Any] | None:
        return self.documents.get(prompt_id)


class FakePromptRepository:
    def __init__(self) -> None:
        self.vector_index_name = "prompt_embedding_index"
        self.prompts: dict[str, PromptRecord] = {}
        self.saved_payloads: list[PromptGraphPayload] = []
        self.saved_hierarchy_nodes: list[Any] = []
        self.ensure_schema_calls: list[dict[str, Any]] = []
        self.generate_embedding_calls: list[dict[str, Any]] = []
        self.vector_search_calls: list[dict[str, Any]] = []
        self.fulltext_search_calls: list[dict[str, Any]] = []
        self.vector_search_results: dict[tuple[str, tuple[tuple[str, Any], ...]], list[dict[str, Any]]] = {}
        self.fulltext_search_results: dict[tuple[str, tuple[tuple[str, Any], ...]], list[dict[str, Any]]] = {}
        self.prompt_embeddings: dict[tuple[str, str], list[float]] = {}
        self.candidate_generation_calls: list[dict[str, Any]] = []
        self.generated_candidates: list[dict[str, Any]] | None = None
        self.saved_cluster_runs: dict[str, dict[str, Any]] = {}

    def ensure_schema(self, **kwargs: Any) -> None:
        self.ensure_schema_calls.append(kwargs)

    def upsert_hierarchy_nodes(self, nodes: list[Any]) -> None:
        self.saved_hierarchy_nodes.extend(nodes)

    def upsert_prompt_graph(self, payload: PromptGraphPayload) -> None:
        self.saved_payloads.append(payload)
        self.prompts[payload.prompt.prompt_id] = payload.prompt

    def get_prompt(self, prompt_id: str) -> PromptRecord | None:
        return self.prompts.get(prompt_id)

    def list_prompt_ids(
        self,
        *,
        requires_embedding: bool = False,
        embedding_property: str | None = None,
    ) -> list[str]:
        prompt_ids = []
        for prompt_id, prompt in self.prompts.items():
            if requires_embedding:
                if embedding_property and (prompt_id, embedding_property) in self.prompt_embeddings:
                    pass
                elif not prompt.embedding:
                    continue
            prompt_ids.append(prompt_id)
        return prompt_ids

    def list_prompts(self) -> list[dict[str, Any]]:
        rows = []
        for prompt in self.prompts.values():
            rows.append(
                {
                    "prompt_id": prompt.prompt_id,
                    "name": prompt.name,
                    "category": prompt.category,
                    "layer": prompt.layer,
                    "layer_path": prompt.layer_path,
                    "prompt_parent": prompt.prompt_parent,
                    "available_embedding_models": [],
                }
            )
        return sorted(rows, key=lambda row: row["prompt_id"])

    def get_prompt_embedding(
        self,
        prompt_id: str,
        *,
        embedding_property: str | None = None,
    ) -> list[float] | None:
        if embedding_property:
            return self.prompt_embeddings.get((prompt_id, embedding_property))
        prompt = self.prompts.get(prompt_id)
        return prompt.embedding if prompt else None

    def generate_embeddings(self, **kwargs: Any) -> int:
        self.generate_embedding_calls.append(kwargs)
        embedding_property = kwargs.get("embedding_property")
        for prompt_id in kwargs.get("prompt_ids") or self.list_prompt_ids():
            if embedding_property:
                self.prompt_embeddings[(prompt_id, embedding_property)] = [0.1, 0.2, 0.3]
        return len(kwargs.get("prompt_ids") or self.list_prompt_ids())

    def vector_search(
        self,
        *,
        query_text: str | None,
        query_vector: list[float] | None,
        limit: int,
        filters: dict[str, Any] | None = None,
        index_name: str | None = None,
        node_label: str | None = None,
        embedding_node_property: str | None = None,
        embedding_dimension: int | None = None,
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        self.vector_search_calls.append(
            {
                "query_text": query_text,
                "query_vector": query_vector,
                "limit": limit,
                "filters": filters,
                "index_name": index_name,
                "node_label": node_label,
                "embedding_node_property": embedding_node_property,
                "embedding_dimension": embedding_dimension,
            }
        )
        key = ((query_text or ""), tuple(sorted(filters.items())))
        return self.vector_search_results.get(key, [])[:limit]

    def fulltext_search(
        self,
        *,
        query_text: str,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        self.fulltext_search_calls.append(
            {
                "query_text": query_text,
                "limit": limit,
                "filters": filters,
            }
        )
        key = (query_text, tuple(sorted(filters.items())))
        return self.fulltext_search_results.get(key, [])[:limit]

    def generate_similarity_candidates(self, **kwargs: Any) -> list[dict[str, Any]] | None:
        self.candidate_generation_calls.append(kwargs)
        return self.generated_candidates

    def save_cluster_run(self, **kwargs: Any) -> None:
        run = kwargs["run"]
        self.saved_cluster_runs[run["run_id"]] = run

    def get_cluster_run(self, run_id: str) -> dict[str, Any] | None:
        return self.saved_cluster_runs.get(run_id)

    def get_prompt_graph(self, prompt_id: str) -> dict[str, Any]:
        prompt = self.prompts[prompt_id]
        return {
            "prompt_id": prompt.prompt_id,
            "category": prompt.category,
            "layer_path": prompt.layer_path,
            "prompt_path_lineage": list(prompt.prompt_path_lineage),
            "variables": list(prompt.input_variables),
            "storage": {
                "bucket": prompt.storage_bucket,
                "key": prompt.storage_key,
                "version_id": prompt.storage_version_id,
                "s3_uri": prompt.storage_uri,
            },
        }
