from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import dependencies
from app.domain.models import TenantContext
from app.main import app


class StubAnalysisService:
    def __init__(self) -> None:
        self.duplicate_calls: list[dict[str, object]] = []
        self.scoped_duplicate_calls: list[dict[str, object]] = []
        self.scope_cluster_calls: list[dict[str, object]] = []
        self.visualization_calls: list[dict[str, object]] = []
        self.cluster_detail_calls: list[dict[str, object]] = []
        self.run_calls: list[dict[str, object]] = []
        self.run_lookup_calls: list[str] = []
        self.list_run_calls = 0

    def analyze_duplicates(self, **kwargs):
        self.duplicate_calls.append(kwargs)
        return [
            {
                "cluster_id": "cluster_1",
                "prompts": [
                    {
                        "prompt_id": "verification.dob",
                        "content_preview": "preview",
                        "category": "verification",
                        "layer_path": "org.os.team.engine",
                        "prompt_parent": "verification",
                        "prompt_path_lineage": ["verification", "verification.dob"],
                        "layer_lineage": ["org", "org.os", "org.os.team", "org.os.team.engine"],
                        "category_lineage": ["verification"],
                        "input_variables": [],
                        "similarity_score": 0.99,
                        "fulltext_score": 6.0,
                        "ranking_score": 1.0,
                        "match_sources": ["vector"],
                    }
                ],
                "edges": [],
                "merge_suggestion": {
                    "canonical_prompt_id": "verification.dob",
                    "rationale": "Same scope.",
                    "optional_variables": [],
                    "unified_prompt_template": "template",
                },
            }
        ]

    def analyze_scoped_duplicates(self, **kwargs):
        self.scoped_duplicate_calls.append(kwargs)
        return [
            {
                "scope_type": kwargs["scope_mode"],
                "scope_value": "verification",
                "prompt_count": 2,
                "clusters": [
                    {
                        "cluster_id": "category_cluster_1",
                        "prompts": [
                            {
                                "prompt_id": "verification.dob",
                                "content_preview": "preview",
                                "category": "verification",
                                "layer_path": "org.os.team.engine",
                                "prompt_parent": "verification",
                                "prompt_path_lineage": ["verification", "verification.dob"],
                                "layer_lineage": ["org", "org.os", "org.os.team", "org.os.team.engine"],
                                "category_lineage": ["verification"],
                                "input_variables": [],
                                "similarity_score": 0.99,
                                "fulltext_score": 6.0,
                                "ranking_score": 1.0,
                                "match_sources": ["vector"],
                            }
                        ],
                        "edges": [],
                        "merge_suggestion": {
                            "canonical_prompt_id": "verification.dob",
                            "rationale": "Same scope.",
                            "optional_variables": [],
                            "unified_prompt_template": "template",
                        },
                    }
                ],
            }
        ]

    def build_cluster_run_visualization(self, *, run_id: str):
        self.visualization_calls.append({"run_id": run_id})
        return {"nodes": [{"id": "n1"}], "edges": [], "clusters": []}

    def analyze_scope_clusters(self, **kwargs):
        self.scope_cluster_calls.append(kwargs)
        return {
            "prompt_id": kwargs["prompt_id"],
            "category": {"scope_value": "verification", "clusters": []},
            "layer": {"scope_value": "org.os.team.engine", "clusters": []},
            "prompt_family": {"scope_value": "verification", "clusters": []},
        }

    def get_cluster_run_detail(self, *, run_id: str, cluster_id: str):
        self.cluster_detail_calls.append({"run_id": run_id, "cluster_id": cluster_id})
        return {
            "cluster_id": cluster_id,
            "scope_mode": "global",
            "scope_key": None,
            "member_count": 2,
            "avg_similarity": 0.97,
            "prompts": [],
            "edges": [],
            "merge_suggestion": {},
        }

    def create_cluster_run(self, **kwargs):
        self.run_calls.append(kwargs)
        return {
            "run_id": "run_123",
            "scope_mode": kwargs["scope_mode"],
            "scope_key": kwargs.get("scope_key"),
            "provider": kwargs["provider"],
            "model": kwargs["model"],
            "top_k": kwargs["neighbor_limit"],
            "threshold": kwargs["threshold"],
            "algorithm_version": "strict-v1",
            "created_at": "2026-04-08T12:00:00Z",
            "clusters": [
                {
                    "cluster_id": "cluster_1",
                    "scope_mode": kwargs["scope_mode"],
                    "scope_key": kwargs.get("scope_key"),
                    "member_count": 2,
                    "avg_similarity": 0.97,
                    "prompts": [],
                    "edges": [],
                    "merge_suggestion": {},
                }
            ],
        }

    def get_cluster_run(self, run_id: str):
        self.run_lookup_calls.append(run_id)
        return {
            "run_id": run_id,
            "scope_mode": "global",
            "scope_key": None,
            "provider": "openai",
            "model": "text-embedding-3-large",
            "top_k": 10,
            "threshold": 0.9,
            "algorithm_version": "strict-v1",
            "created_at": "2026-04-08T12:00:00Z",
            "clusters": [
                {
                    "cluster_id": "cluster_1",
                    "scope_mode": "global",
                    "scope_key": None,
                    "member_count": 2,
                    "avg_similarity": 0.97,
                    "prompts": [],
                    "edges": [],
                    "merge_suggestion": {},
                }
            ],
        }

    def list_cluster_runs(self):
        self.list_run_calls += 1
        return [
            {
                "run_id": "run_999",
                "scope_mode": "hierarchy",
                "scope_key": None,
                "provider": "openai",
                "model": "text-embedding-3-large",
                "top_k": 10,
                "threshold": 0.92,
                "algorithm_version": "strict-v2",
                "created_at": "2026-04-08T13:00:00Z",
                "category_filter": "verification",
                "hierarchy_filter": "os",
                "cluster_count": 3,
            },
            {
                "run_id": "run_123",
                "scope_mode": "global",
                "scope_key": None,
                "provider": "openai",
                "model": "text-embedding-3-large",
                "top_k": 10,
                "threshold": 0.9,
                "algorithm_version": "strict-v2",
                "created_at": "2026-04-08T12:00:00Z",
                "category_filter": None,
                "hierarchy_filter": None,
                "cluster_count": 1,
            },
        ]


class StubMergeAnalysisService:
    def analyze_clusters(self, **kwargs):
        return {
            "scope": {"hierarchy": kwargs.get("scope_hierarchy"), "category": kwargs.get("scope_category")},
            "results": [
                {
                    "cluster_id": "cluster_1",
                    "prompt_ids": ["common.error_handling", "common.error_recovery"],
                    "analysis": {
                        "can_merge": True,
                        "confidence": 0.91,
                        "canonical_prompt_id": "common.error_recovery",
                        "merged_prompt_name": "Unified Error Recovery Prompt",
                        "unified_prompt_template": "Remain calm, acknowledge the issue, and offer recovery options.",
                        "variables_to_parameterize": [],
                        "differences_to_preserve": ["Keep apology behavior optional."],
                        "reasoning": "Both prompts handle the same failure mode.",
                        "migration_steps": ["Consolidate callers onto the canonical prompt."],
                    },
                }
            ],
        }


class StubRepo:
    def get_prompt(self, prompt_id: str):
        return object()


class PreviewRepo:
    def __init__(self, exists: bool = True) -> None:
        self.exists = exists

    def get_prompt(self, prompt_id: str):
        if not self.exists:
            return None
        return SimpleNamespace(
            prompt_id=prompt_id,
            name="Identity Verification Prompt",
            category="verification",
            layer="engine",
            input_variables=("date_of_birth",),
            storage_bucket="core-prompts-057286249135",
            storage_key=f"prompts/{prompt_id}.json",
            storage_version_id="v123",
            storage_uri=f"s3://core-prompts-057286249135/prompts/{prompt_id}.json",
        )


class PreviewStore:
    def __init__(self) -> None:
        self.storage_calls: list[dict[str, str | None]] = []

    def get_prompt(self, prompt_id: str):
        return {
            "prompt_id": prompt_id,
            "name": "Identity Verification Prompt",
            "category": "verification",
            "layer": "engine",
            "content": "Verify identity using {{date_of_birth}}",
        }

    def get_prompt_by_storage(self, *, key: str, bucket: str | None = None, version_id: str | None = None):
        self.storage_calls.append({"bucket": bucket, "key": key, "version_id": version_id})
        return None


class PreviewStoreByStorageOnly:
    def __init__(self) -> None:
        self.storage_calls: list[dict[str, str | None]] = []

    def get_prompt(self, prompt_id: str):
        return None

    def get_prompt_by_storage(self, *, key: str, bucket: str | None = None, version_id: str | None = None):
        self.storage_calls.append({"bucket": bucket, "key": key, "version_id": version_id})
        return {
            "prompt_id": "verification.identity",
            "name": "Identity Verification Prompt",
            "category": "verification",
            "layer": "engine",
            "content": "Verify identity using {{date_of_birth}}",
        }


class PromptListRepo:
    def list_prompts(self):
        return [
            {
                "prompt_id": "verification.dob",
                "name": "DOB Verification",
                "category": "verification",
                "layer": "engine",
                "layer_path": "org.os.team.engine",
                "prompt_parent": "verification",
                "available_embedding_models": ["openai:text-embedding-3-large"],
            },
            {
                "prompt_id": "common.error_handling",
                "name": "Error Handling",
                "category": "common",
                "layer": "engine",
                "layer_path": "org.os.team.engine",
                "prompt_parent": "common",
                "available_embedding_models": [],
            },
        ]


class StubTenantService:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []

    def list_tenants(self):
        return [
            {
                "tenant_id": "sample-prompts",
                "name": "Sample Prompts",
                "prompt_count": 12,
                "is_builtin": True,
            },
            {
                "tenant_id": "benchmark-1k",
                "name": "Benchmark 1K",
                "prompt_count": 1000,
                "is_builtin": True,
            },
        ]

    def create_tenant(self, **kwargs):
        self.create_calls.append(kwargs)
        return {
            "tenant_id": kwargs["tenant_id"],
            "name": kwargs["name"],
            "prompt_count": 12 if kwargs.get("seed_type") == "sample" else 0,
            "is_builtin": False,
        }


class ExplorerRepo:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_explorer_graph(
        self,
        *,
        view: str,
        category: str | None = None,
        hierarchy: str | None = None,
        layer_path: str | None = None,
        prompt_query: str | None = None,
    ):
        self.calls.append(
            {
                "view": view,
                "category": category,
                "hierarchy": hierarchy,
                "layer_path": layer_path,
                "prompt_query": prompt_query,
            }
        )
        return {
            "tenant_id": "sample-prompts",
            "view": view,
            "filters": {
                "category": category,
                "hierarchy": hierarchy,
                "layer_path": layer_path,
                "prompt_query": prompt_query,
            },
            "nodes": [{"id": "prompt:verification.identity", "label": "verification.identity", "kind": "prompt"}],
            "edges": [{"id": "edge-1", "source": "prompt:verification.identity", "target": "category:verification"}],
            "summary": {"prompt_count": 1, "category_count": 1},
        }


def test_run_visualization_route_returns_saved_run_visualization() -> None:
    service = StubAnalysisService()
    app.dependency_overrides[dependencies.get_analysis_service] = lambda: service
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get("/api/analysis/runs/run_123/visualization")
        assert response.status_code == 200
        assert response.json()["nodes"][0]["id"] == "n1"
        assert service.visualization_calls == [{"run_id": "run_123"}]
    finally:
        app.dependency_overrides.clear()


def test_prompt_list_route_requires_tenant_header() -> None:
    app.dependency_overrides[dependencies.get_prompt_repository] = lambda: PromptListRepo()
    try:
        with TestClient(app) as client:
            response = client.get("/api/prompts")
        assert response.status_code == 400
        assert response.json()["detail"] == "X-Tenant-Id header is required"
    finally:
        app.dependency_overrides.clear()


def test_tenant_list_route_returns_available_tenants() -> None:
    service = StubTenantService()
    app.dependency_overrides[dependencies.get_tenant_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/tenants")
        assert response.status_code == 200
        body = response.json()
        assert body[0]["tenant_id"] == "sample-prompts"
        assert body[1]["prompt_count"] == 1000
    finally:
        app.dependency_overrides.clear()


def test_create_tenant_route_creates_seeded_tenant() -> None:
    service = StubTenantService()
    app.dependency_overrides[dependencies.get_tenant_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/tenants",
                json={
                    "tenant_id": "new-tenant",
                    "name": "New Tenant",
                    "seed_type": "sample",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["tenant_id"] == "new-tenant"
        assert body["prompt_count"] == 12
        assert service.create_calls == [
            {
                "tenant_id": "new-tenant",
                "name": "New Tenant",
                "seed_type": "sample",
            }
        ]
    finally:
        app.dependency_overrides.clear()


def test_graph_explorer_route_returns_tenant_scoped_graph() -> None:
    repo = ExplorerRepo()
    app.dependency_overrides[dependencies.get_prompt_repository] = lambda: repo
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/graph/explorer?view=category&category=verification&hierarchy=engine",
                headers={"X-Tenant-Id": "sample-prompts"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["tenant_id"] == "sample-prompts"
        assert body["summary"]["prompt_count"] == 1
        assert repo.calls == [
            {
                "view": "category",
                "category": "verification",
                "hierarchy": "engine",
                "layer_path": None,
                "prompt_query": None,
            }
        ]
    finally:
        app.dependency_overrides.clear()


def test_scope_cluster_route_returns_analysis_payload() -> None:
    service = StubAnalysisService()
    app.dependency_overrides[dependencies.get_analysis_service] = lambda: service
    app.dependency_overrides[dependencies.get_prompt_repository] = lambda: StubRepo()
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/analysis/prompts/verification.dob/scopes?provider=bedrock&model=amazon.titan-embed-text-v2:0"
            )
        assert response.status_code == 200
        body = response.json()
        assert body["prompt_id"] == "verification.dob"
        assert body["category"]["scope_value"] == "verification"
        assert service.scope_cluster_calls[0]["provider"] == "bedrock"
        assert service.scope_cluster_calls[0]["model"] == "amazon.titan-embed-text-v2:0"
    finally:
        app.dependency_overrides.clear()


def test_duplicate_route_forwards_scope_filters() -> None:
    service = StubAnalysisService()
    app.dependency_overrides[dependencies.get_analysis_service] = lambda: service
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get("/api/analysis/duplicates?category_filter=verification&hierarchy_filter=os")
        assert response.status_code == 200
        assert response.json()[0]["cluster_id"] == "cluster_1"
        assert service.duplicate_calls[0]["category_filter"] == "verification"
        assert service.duplicate_calls[0]["hierarchy_filter"] == "os"
    finally:
        app.dependency_overrides.clear()


def test_scoped_duplicate_route_returns_grouped_payload() -> None:
    service = StubAnalysisService()
    app.dependency_overrides[dependencies.get_analysis_service] = lambda: service
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/analysis/duplicates/scoped?scope_mode=category&category_filter=verification"
            )
        assert response.status_code == 200
        body = response.json()
        assert body[0]["scope_type"] == "category"
        assert body[0]["scope_value"] == "verification"
        assert service.scoped_duplicate_calls[0]["scope_mode"] == "category"
        assert service.scoped_duplicate_calls[0]["category_filter"] == "verification"
    finally:
        app.dependency_overrides.clear()


def test_cluster_run_route_returns_persisted_run_payload() -> None:
    service = StubAnalysisService()
    app.dependency_overrides[dependencies.get_analysis_service] = lambda: service
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/analysis/clusters/run",
                json={
                    "scope_mode": "global",
                    "threshold": 0.95,
                    "neighbor_limit": 12,
                    "provider": "openai",
                    "model": "text-embedding-3-large",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == "run_123"
        assert body["clusters"][0]["cluster_id"] == "cluster_1"
        assert service.run_calls[0]["scope_mode"] == "global"
    finally:
        app.dependency_overrides.clear()


def test_cluster_run_route_rejects_unexpected_run_type_field() -> None:
    service = StubAnalysisService()
    app.dependency_overrides[dependencies.get_analysis_service] = lambda: service
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/analysis/clusters/run",
                json={
                    "run_type": "related",
                    "scope_mode": "global",
                    "threshold": 0.95,
                    "neighbor_limit": 12,
                    "provider": "openai",
                    "model": "text-embedding-3-large",
                },
            )
        assert response.status_code == 422
        assert service.run_calls == []
    finally:
        app.dependency_overrides.clear()


def test_cluster_run_lookup_route_returns_saved_run() -> None:
    service = StubAnalysisService()
    app.dependency_overrides[dependencies.get_analysis_service] = lambda: service
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get("/api/analysis/runs/run_123")
        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == "run_123"
        assert body["clusters"][0]["cluster_id"] == "cluster_1"
        assert service.run_lookup_calls == ["run_123"]
    finally:
        app.dependency_overrides.clear()


def test_cluster_run_list_route_returns_saved_runs_for_active_tenant() -> None:
    service = StubAnalysisService()
    app.dependency_overrides[dependencies.get_analysis_service] = lambda: service
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get("/api/analysis/runs")
        assert response.status_code == 200
        body = response.json()
        assert [row["run_id"] for row in body] == ["run_999", "run_123"]
        assert body[0]["cluster_count"] == 3
        assert service.list_run_calls == 1
    finally:
        app.dependency_overrides.clear()


def test_cluster_run_detail_route_reads_from_saved_run() -> None:
    service = StubAnalysisService()
    app.dependency_overrides[dependencies.get_analysis_service] = lambda: service
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get("/api/analysis/runs/run_123/clusters/cluster_1")
        assert response.status_code == 200
        assert response.json()["cluster_id"] == "cluster_1"
        assert service.cluster_detail_calls == [{"run_id": "run_123", "cluster_id": "cluster_1"}]
    finally:
        app.dependency_overrides.clear()


def test_prompt_preview_route_renders_html_document() -> None:
    store = PreviewStore()
    app.dependency_overrides[dependencies.get_prompt_repository] = lambda: PreviewRepo()
    app.dependency_overrides[dependencies.get_prompt_store] = lambda: store
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get("/api/prompts/verification.identity/preview")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Identity Verification Prompt" in response.text
        assert "verification.identity" in response.text
        assert "Verify identity using" in response.text
        assert "date_of_birth" in response.text
        assert store.storage_calls[0]["key"] == "prompts/verification.identity.json"
    finally:
        app.dependency_overrides.clear()


def test_prompt_preview_route_returns_404_for_missing_prompt() -> None:
    app.dependency_overrides[dependencies.get_prompt_repository] = lambda: PreviewRepo(exists=False)
    app.dependency_overrides[dependencies.get_prompt_store] = lambda: PreviewStore()
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get("/api/prompts/missing.prompt/preview")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_prompt_preview_route_falls_back_to_stored_s3_key() -> None:
    store = PreviewStoreByStorageOnly()
    app.dependency_overrides[dependencies.get_prompt_repository] = lambda: PreviewRepo()
    app.dependency_overrides[dependencies.get_prompt_store] = lambda: store
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get("/api/prompts/verification.identity/preview")
        assert response.status_code == 200
        assert "Verify identity using" in response.text
        assert store.storage_calls == [
            {
                "bucket": "core-prompts-057286249135",
                "key": "prompts/verification.identity.json",
                "version_id": "v123",
            }
        ]
    finally:
        app.dependency_overrides.clear()


def test_health_route_allows_local_nextjs_origin() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_health_route_allows_loopback_nextjs_origin() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"origin": "http://127.0.0.1:3000"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_prompt_list_route_returns_prompt_metadata() -> None:
    app.dependency_overrides[dependencies.get_prompt_repository] = lambda: PromptListRepo()
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.get("/api/prompts")
        assert response.status_code == 200
        body = response.json()
        assert body[0]["prompt_id"] == "verification.dob"
        assert body[0]["layer_path"] == "org.os.team.engine"
        assert body[0]["available_embedding_models"] == ["openai:text-embedding-3-large"]
    finally:
        app.dependency_overrides.clear()


def test_merge_suggestions_route_returns_structured_analysis() -> None:
    app.dependency_overrides[dependencies.get_merge_analysis_service] = lambda: StubMergeAnalysisService()
    app.dependency_overrides[dependencies.get_tenant_context] = lambda: TenantContext(tenant_id="sample-prompts")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/analysis/merge-suggestions",
                json={
                    "clusters": [
                        {
                            "cluster_id": "cluster_1",
                            "prompt_ids": ["common.error_handling", "common.error_recovery"],
                        }
                    ],
                    "scope_hierarchy": "engine",
                    "scope_category": "common",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["scope"]["hierarchy"] == "engine"
        assert body["results"][0]["cluster_id"] == "cluster_1"
        assert body["results"][0]["analysis"]["can_merge"] is True
        assert body["results"][0]["analysis"]["canonical_prompt_id"] == "common.error_recovery"
    finally:
        app.dependency_overrides.clear()
