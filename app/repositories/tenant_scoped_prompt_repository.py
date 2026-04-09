from __future__ import annotations

from typing import Any

from app.repositories.prompt_repository import PromptGraphRepository


class TenantScopedPromptRepository(PromptGraphRepository):
    def __init__(self, *, base_repo: Any, tenant_id: str) -> None:
        self.base_repo = base_repo
        self.tenant_id = tenant_id
        self.vector_index_name = getattr(base_repo, "vector_index_name", "prompt_embedding_index")
        self.fulltext_index_name = getattr(base_repo, "fulltext_index_name", "prompt_fulltext_index")

    def ensure_schema(self, **kwargs: Any) -> None:
        self.base_repo.ensure_schema(**kwargs)

    def upsert_hierarchy_nodes(self, nodes):
        shared_nodes = [node for node in nodes if getattr(node, "kind", None) == "layer_path"]
        tenant_nodes = [node for node in nodes if getattr(node, "kind", None) != "layer_path"]
        if shared_nodes:
            self.base_repo.upsert_hierarchy_nodes(shared_nodes)
        if tenant_nodes:
            self.base_repo.upsert_hierarchy_nodes_for_tenant(self.tenant_id, tenant_nodes)

    def upsert_prompt_graph(self, payload):
        self.base_repo.upsert_prompt_graph_for_tenant(self.tenant_id, payload)

    def get_prompt(self, prompt_id: str):
        return self.base_repo.get_prompt_for_tenant(self.tenant_id, prompt_id)

    def list_prompt_ids(self, *, requires_embedding: bool = False, embedding_property: str | None = None):
        return self.base_repo.list_prompt_ids_for_tenant(
            self.tenant_id,
            requires_embedding=requires_embedding,
            embedding_property=embedding_property,
        )

    def list_prompts(self):
        return self.base_repo.list_prompts_for_tenant(self.tenant_id)

    def get_prompt_embedding(self, prompt_id: str, *, embedding_property: str | None = None):
        return self.base_repo.get_prompt_embedding_for_tenant(
            self.tenant_id,
            prompt_id,
            embedding_property=embedding_property,
        )

    def generate_embeddings(self, **kwargs: Any) -> int:
        return self.base_repo.generate_embeddings_for_tenant(self.tenant_id, **kwargs)

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
    ):
        return self.base_repo.vector_search_for_tenant(
            self.tenant_id,
            query_text=query_text,
            query_vector=query_vector,
            limit=limit,
            filters=filters,
            index_name=index_name,
            node_label=node_label,
            embedding_node_property=embedding_node_property,
            embedding_dimension=embedding_dimension,
        )

    def fulltext_search(
        self,
        *,
        query_text: str,
        limit: int,
        filters: dict[str, Any] | None = None,
    ):
        return self.base_repo.fulltext_search_for_tenant(
            self.tenant_id,
            query_text=query_text,
            limit=limit,
            filters=filters,
        )

    def generate_similarity_candidates(self, **kwargs: Any):
        return self.base_repo.generate_similarity_candidates_for_tenant(self.tenant_id, **kwargs)

    def save_cluster_run(self, **kwargs: Any) -> None:
        self.base_repo.save_cluster_run_for_tenant(self.tenant_id, **kwargs)

    def get_cluster_run(self, run_id: str):
        return self.base_repo.get_cluster_run_for_tenant(self.tenant_id, run_id)

    def list_cluster_runs(self):
        return self.base_repo.list_cluster_runs_for_tenant(self.tenant_id)

    def get_prompt_graph(self, prompt_id: str):
        return self.base_repo.get_prompt_graph_for_tenant(self.tenant_id, prompt_id)

    def get_explorer_graph(
        self,
        *,
        view: str,
        category: str | None = None,
        hierarchy: str | None = None,
        layer_path: str | None = None,
        prompt_query: str | None = None,
    ):
        return self.base_repo.get_explorer_graph_for_tenant(
            self.tenant_id,
            view=view,
            category=category,
            hierarchy=hierarchy,
            layer_path=layer_path,
            prompt_query=prompt_query,
        )

    def close(self) -> None:
        self.base_repo.close()
