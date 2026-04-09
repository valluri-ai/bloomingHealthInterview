from __future__ import annotations

from typing import Any, Protocol

from app.domain.models import HierarchyNodeRecord, PromptGraphPayload, PromptRecord, StoredPromptVersion
from app.domain.models import TenantRecord
from app.schemas.prompt import PromptInput


class PromptGraphRepository(Protocol):
    def ensure_schema(self, **kwargs: Any) -> None: ...

    def upsert_hierarchy_nodes(self, nodes: list[HierarchyNodeRecord]) -> None: ...

    def upsert_prompt_graph(self, payload: PromptGraphPayload) -> None: ...

    def get_prompt(self, prompt_id: str) -> PromptRecord | None: ...

    def list_prompt_ids(
        self,
        *,
        requires_embedding: bool = False,
        embedding_property: str | None = None,
    ) -> list[str]: ...

    def list_prompts(self) -> list[dict[str, Any]]: ...

    def get_prompt_embedding(
        self,
        prompt_id: str,
        *,
        embedding_property: str | None = None,
    ) -> list[float] | None: ...

    def generate_embeddings(self, **kwargs: Any) -> int: ...

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
    ) -> list[dict[str, Any]]: ...

    def fulltext_search(
        self,
        *,
        query_text: str,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    def generate_similarity_candidates(self, **kwargs: Any) -> list[dict[str, Any]] | None: ...

    def save_cluster_run(self, **kwargs: Any) -> None: ...

    def get_cluster_run(self, run_id: str) -> dict[str, Any] | None: ...

    def list_cluster_runs(self) -> list[dict[str, Any]]: ...

    def get_prompt_graph(self, prompt_id: str) -> dict[str, Any]: ...

    def get_explorer_graph(
        self,
        *,
        view: str,
        category: str | None = None,
        hierarchy: str | None = None,
        layer_path: str | None = None,
        prompt_query: str | None = None,
    ) -> dict[str, Any]: ...

    def close(self) -> None: ...


class PromptTemplateStore(Protocol):
    def store_prompt(self, prompt: PromptInput) -> StoredPromptVersion: ...

    def get_prompt(self, prompt_id: str) -> dict[str, Any] | None: ...

    def get_prompt_by_storage(
        self,
        *,
        key: str,
        bucket: str | None = None,
        version_id: str | None = None,
    ) -> dict[str, Any] | None: ...


class TenantAdminRepository(Protocol):
    def ensure_schema(self, **kwargs: Any) -> None: ...

    def list_tenants(self) -> list[TenantRecord]: ...

    def create_tenant(
        self,
        *,
        tenant_id: str,
        name: str,
        is_builtin: bool = False,
    ) -> TenantRecord: ...

    def get_tenant(self, tenant_id: str) -> TenantRecord | None: ...

    def tenant_exists(self, tenant_id: str) -> bool: ...

    def count_prompts_for_tenant(self, tenant_id: str) -> int: ...
