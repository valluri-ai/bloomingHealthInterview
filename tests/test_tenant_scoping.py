from __future__ import annotations

from app.repositories.tenant_scoped_prompt_repository import TenantScopedPromptRepository
from app.repositories.tenant_scoped_prompt_store import TenantScopedPromptStore
from app.schemas.prompt import PromptInput


class StubBaseRepo:
    vector_index_name = "prompt_embedding_index"

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def get_prompt_for_tenant(self, tenant_id: str, prompt_id: str):
        self.calls.append(("get_prompt_for_tenant", (tenant_id, prompt_id), {}))
        return {"tenant_id": tenant_id, "prompt_id": prompt_id}

    def list_prompts_for_tenant(self, tenant_id: str):
        self.calls.append(("list_prompts_for_tenant", (tenant_id,), {}))
        return [{"tenant_id": tenant_id, "prompt_id": "verification.identity"}]

    def save_cluster_run_for_tenant(self, tenant_id: str, **kwargs):
        self.calls.append(("save_cluster_run_for_tenant", (tenant_id,), kwargs))

    def get_cluster_run_for_tenant(self, tenant_id: str, run_id: str):
        self.calls.append(("get_cluster_run_for_tenant", (tenant_id, run_id), {}))
        return {"tenant_id": tenant_id, "run_id": run_id}

    def list_cluster_runs_for_tenant(self, tenant_id: str):
        self.calls.append(("list_cluster_runs_for_tenant", (tenant_id,), {}))
        return [{"tenant_id": tenant_id, "run_id": "run_123"}]

    def vector_search_for_tenant(
        self,
        tenant_id: str,
        *,
        query_text: str | None,
        query_vector: list[float] | None,
        limit: int,
        filters: dict[str, object] | None = None,
        index_name: str | None = None,
        node_label: str | None = None,
        embedding_node_property: str | None = None,
        embedding_dimension: int | None = None,
    ):
        self.calls.append(
            (
                "vector_search_for_tenant",
                (tenant_id,),
                {
                    "query_text": query_text,
                    "query_vector": query_vector,
                    "limit": limit,
                    "filters": filters,
                    "index_name": index_name,
                    "node_label": node_label,
                    "embedding_node_property": embedding_node_property,
                    "embedding_dimension": embedding_dimension,
                },
            )
        )
        return []


class StubBaseStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def store_prompt_for_tenant(self, tenant_id: str, prompt: PromptInput):
        self.calls.append(("store_prompt_for_tenant", (tenant_id, prompt.prompt_id), {}))
        return {"tenant_id": tenant_id, "prompt_id": prompt.prompt_id}

    def get_prompt_for_tenant(self, tenant_id: str, prompt_id: str):
        self.calls.append(("get_prompt_for_tenant", (tenant_id, prompt_id), {}))
        return {"tenant_id": tenant_id, "prompt_id": prompt_id}

    def get_prompt_by_storage(self, **kwargs):
        self.calls.append(("get_prompt_by_storage", tuple(), kwargs))
        return {"key": kwargs["key"]}


def test_tenant_scoped_repository_forwards_active_tenant_to_base_repo() -> None:
    base = StubBaseRepo()
    repo = TenantScopedPromptRepository(base_repo=base, tenant_id="sample-prompts")

    prompt = repo.get_prompt("verification.identity")
    prompts = repo.list_prompts()
    repo.save_cluster_run(run={"run_id": "run_123"})
    run = repo.get_cluster_run("run_123")
    runs = repo.list_cluster_runs()

    assert prompt["tenant_id"] == "sample-prompts"
    assert prompts[0]["tenant_id"] == "sample-prompts"
    assert run["tenant_id"] == "sample-prompts"
    assert runs[0]["tenant_id"] == "sample-prompts"
    assert base.calls == [
        ("get_prompt_for_tenant", ("sample-prompts", "verification.identity"), {}),
        ("list_prompts_for_tenant", ("sample-prompts",), {}),
        ("save_cluster_run_for_tenant", ("sample-prompts",), {"run": {"run_id": "run_123"}}),
        ("get_cluster_run_for_tenant", ("sample-prompts", "run_123"), {}),
        ("list_cluster_runs_for_tenant", ("sample-prompts",), {}),
    ]


def test_tenant_scoped_repository_forwards_vector_search_metadata() -> None:
    base = StubBaseRepo()
    repo = TenantScopedPromptRepository(base_repo=base, tenant_id="sample-prompts")

    repo.vector_search(
        query_text="verify identity",
        query_vector=None,
        limit=5,
        filters={"category": "verification"},
        index_name="prompt_embedding_index__openai_text_embedding_3_large",
        node_label="Prompt",
        embedding_node_property="embedding_openai_text_embedding_3_large",
        embedding_dimension=3072,
    )

    assert base.calls == [
        (
            "vector_search_for_tenant",
            ("sample-prompts",),
            {
                "query_text": "verify identity",
                "query_vector": None,
                "limit": 5,
                "filters": {"category": "verification"},
                "index_name": "prompt_embedding_index__openai_text_embedding_3_large",
                "node_label": "Prompt",
                "embedding_node_property": "embedding_openai_text_embedding_3_large",
                "embedding_dimension": 3072,
            },
        )
    ]


def test_tenant_scoped_store_forwards_active_tenant_to_base_store() -> None:
    base = StubBaseStore()
    store = TenantScopedPromptStore(base_store=base, tenant_id="benchmark-1k")

    stored = store.store_prompt(
        PromptInput(
            prompt_id="verification.identity",
            category="verification",
            layer="engine",
            content="Verify identity using {{date_of_birth}}",
        )
    )
    document = store.get_prompt("verification.identity")
    by_key = store.get_prompt_by_storage(key="prompts/tenants/benchmark-1k/verification.identity.json")

    assert stored["tenant_id"] == "benchmark-1k"
    assert document["tenant_id"] == "benchmark-1k"
    assert by_key["key"] == "prompts/tenants/benchmark-1k/verification.identity.json"
    assert base.calls == [
        ("store_prompt_for_tenant", ("benchmark-1k", "verification.identity"), {}),
        ("get_prompt_for_tenant", ("benchmark-1k", "verification.identity"), {}),
        ("get_prompt_by_storage", tuple(), {"key": "prompts/tenants/benchmark-1k/verification.identity.json"}),
    ]
