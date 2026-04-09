from app.domain.models import HierarchyNodeRecord, PromptGraphPayload, PromptRecord
from app.repositories.neo4j_prompt_repository import Neo4jPromptRepository


class StubDriver:
    def __init__(self, responses=None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def execute_query(self, query, parameters_=None, **kwargs):
        self.calls.append(
            {
                "query": query,
                "parameters": parameters_ or {},
                "kwargs": kwargs,
            }
        )
        if self.responses:
            return self.responses.pop(0), None, None
        return [], None, None

    def close(self) -> None:
        return None


class StubVectorRetriever:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._node_label = None
        self._node_embedding_property = None
        self._embedding_dimension = None

    def search(self, **kwargs):
        self.calls.append(kwargs)
        item = type("Item", (), {"metadata": {"prompt_id": "verification.identity"}})()
        return type("Result", (), {"items": [item]})()


def _payload() -> PromptGraphPayload:
    prompt = PromptRecord(
        prompt_id="survey.question.base",
        category="survey",
        layer="engine",
        layer_path="org.os.team.engine",
        layer_lineage=("org", "org.os", "org.os.team", "org.os.team.engine"),
        name="Base Question Template",
        content_preview="Ask naturally: [VAR]",
        normalized_content="Ask naturally: [VAR]",
        input_variables=("question_text",),
        prompt_parent="survey.question",
        prompt_path_lineage=("survey", "survey.question", "survey.question.base"),
        category_lineage=("survey",),
        embedding_text="prompt_id: survey.question.base\ncontent: Ask naturally: [VAR]",
        search_text="prompt_id: survey.question.base\ncontent: Ask naturally: [VAR]",
        storage_bucket="core-prompts-057286249135",
        storage_key="prompts/survey.question.base.json",
        storage_version_id="v1",
        storage_uri="s3://core-prompts-057286249135/prompts/survey.question.base.json",
        embedding=None,
    )
    path_nodes = (
        HierarchyNodeRecord("prompt_path:survey", "prompt_path", "survey", "survey", 0, None),
        HierarchyNodeRecord("prompt_path:survey.question", "prompt_path", "question", "survey.question", 1, "survey"),
        HierarchyNodeRecord("prompt_path:survey.question.base", "prompt_path", "base", "survey.question.base", 2, "survey.question"),
    )
    category_nodes = (
        HierarchyNodeRecord("category:survey", "category", "survey", "survey", 0, None),
    )
    layer_nodes = (
        HierarchyNodeRecord("layer_path:org", "layer_path", "org", "org", 0, None),
        HierarchyNodeRecord("layer_path:org.os", "layer_path", "os", "org.os", 1, "org"),
        HierarchyNodeRecord("layer_path:org.os.team", "layer_path", "team", "org.os.team", 2, "org.os"),
        HierarchyNodeRecord("layer_path:org.os.team.engine", "layer_path", "engine", "org.os.team.engine", 3, "org.os.team"),
    )
    return PromptGraphPayload(prompt=prompt, prompt_path_nodes=path_nodes, category_nodes=category_nodes, layer_nodes=layer_nodes)


def test_generate_embeddings_uses_application_embedder_and_persists_vectors() -> None:
    driver = StubDriver(
        responses=[
            [{"prompt_id": "survey.question.base", "embedding_text": "prompt_id: survey.question.base"}],
            [{"updated": 1}],
        ]
    )
    repo = Neo4jPromptRepository(
        driver=driver,
        database="neo4j",
        vector_index_name="prompt_embedding_index",
        fulltext_index_name="prompt_fulltext_index",
    )

    captured_texts: list[list[str]] = []

    def embed_batch(texts: list[str]) -> list[list[float]]:
        captured_texts.append(texts)
        return [[0.1, 0.2, 0.3]]

    count = repo.generate_embeddings(
        prompt_ids=["survey.question.base"],
        embed_batch=embed_batch,
        batch_size=32,
        vector_dimensions=3072,
    )

    assert count == 1
    assert captured_texts == [["prompt_id: survey.question.base"]]
    assert "genai.vector.encodeBatch" not in driver.calls[-1]["query"]
    assert "db.create.setNodeVectorProperty" in driver.calls[-1]["query"]
    assert driver.calls[-1]["parameters"]["prompt_ids"] == ["survey.question.base"]
    assert driver.calls[-1]["parameters"]["embedding_vectors"] == [[0.1, 0.2, 0.3]]


def test_ensure_schema_recreates_vector_index_when_dimensions_change() -> None:
    driver = StubDriver(
        responses=[
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [{"dimensions": 3072}],
            [],
            [],
        ]
    )
    repo = Neo4jPromptRepository(
        driver=driver,
        database="neo4j",
        vector_index_name="prompt_embedding_index",
        fulltext_index_name="prompt_fulltext_index",
    )

    repo.ensure_schema(vector_dimensions=1536)

    queries = [call["query"] for call in driver.calls]
    assert any("SHOW VECTOR INDEXES" in query for query in queries)
    assert any("DROP INDEX prompt_embedding_index" in query for query in queries)
    assert any("`vector.dimensions`: 1536" in query for query in queries)


def test_upsert_prompt_graph_merges_prompt_storage_and_relationships() -> None:
    driver = StubDriver()
    repo = Neo4jPromptRepository(
        driver=driver,
        database="neo4j",
        vector_index_name="prompt_embedding_index",
        fulltext_index_name="prompt_fulltext_index",
    )

    repo.upsert_prompt_graph(_payload())

    assert "MERGE (p:Prompt {prompt_id: $prompt.prompt_id})" in driver.calls[-1]["query"]
    assert driver.calls[-1]["parameters"]["prompt"]["storage_bucket"] == "core-prompts-057286249135"
    assert driver.calls[-1]["parameters"]["input_variables"] == ["question_text"]


def test_get_prompt_for_tenant_queries_prompt_by_tenant_and_prompt_id() -> None:
    driver = StubDriver(
        responses=[
            [
                {
                    "prompt": {
                        "prompt_id": "survey.question.base",
                        "category": "survey",
                        "layer": "engine",
                        "layer_path": "org.os.team.engine",
                        "layer_lineage": ["org", "org.os", "org.os.team", "org.os.team.engine"],
                        "name": "Base Question Template",
                        "content_preview": "Ask naturally: [VAR]",
                        "normalized_content": "Ask naturally: [VAR]",
                        "input_variables": ["question_text"],
                        "prompt_parent": "survey.question",
                        "prompt_path_lineage": ["survey", "survey.question", "survey.question.base"],
                        "category_lineage": ["survey"],
                        "embedding_text": "prompt_id: survey.question.base\ncontent: Ask naturally: [VAR]",
                        "search_text": "prompt_id: survey.question.base\ncontent: Ask naturally: [VAR]",
                        "storage_bucket": "core-prompts-057286249135",
                        "storage_key": "prompts/tenants/sample-prompts/survey.question.base.json",
                        "storage_version_id": "v1",
                        "storage_uri": "s3://core-prompts-057286249135/prompts/tenants/sample-prompts/survey.question.base.json",
                    }
                }
            ]
        ]
    )
    repo = Neo4jPromptRepository(
        driver=driver,
        database="neo4j",
        vector_index_name="prompt_embedding_index",
        fulltext_index_name="prompt_fulltext_index",
    )

    prompt = repo.get_prompt_for_tenant("sample-prompts", "survey.question.base")

    assert prompt is not None
    assert prompt.prompt_id == "survey.question.base"
    assert "tenant_id" in driver.calls[-1]["parameters"]
    assert driver.calls[-1]["parameters"]["tenant_id"] == "sample-prompts"


def test_upsert_prompt_graph_for_tenant_merges_prompt_with_tenant_scoped_node_id() -> None:
    driver = StubDriver()
    repo = Neo4jPromptRepository(
        driver=driver,
        database="neo4j",
        vector_index_name="prompt_embedding_index",
        fulltext_index_name="prompt_fulltext_index",
    )

    repo.upsert_prompt_graph_for_tenant("sample-prompts", _payload())

    assert "MERGE (tenant:Tenant {tenant_id: $tenant_id})" in driver.calls[-1]["query"]
    assert "MERGE (p:Prompt {node_id: $prompt_node_id})" in driver.calls[-1]["query"]
    assert driver.calls[-1]["parameters"]["tenant_id"] == "sample-prompts"
    assert driver.calls[-1]["parameters"]["prompt_node_id"] == "sample-prompts:survey.question.base"


def test_vector_search_sets_retriever_filter_metadata_before_search() -> None:
    repo = Neo4jPromptRepository(
        driver=StubDriver(),
        database="neo4j",
        vector_index_name="prompt_embedding_index",
        fulltext_index_name="prompt_fulltext_index",
    )
    retriever = StubVectorRetriever()
    repo._vector_retrievers["prompt_embedding_index__openai_text_embedding_3_large"] = retriever

    results = repo.vector_search(
        query_text="verify identity",
        query_vector=None,
        limit=5,
        filters={"tenant_id": "sample-prompts"},
        index_name="prompt_embedding_index__openai_text_embedding_3_large",
        node_label="Prompt",
        embedding_node_property="embedding_openai_text_embedding_3_large",
        embedding_dimension=3072,
    )

    assert results == [{"prompt_id": "verification.identity"}]
    assert retriever._node_label == "Prompt"
    assert retriever._node_embedding_property == "embedding_openai_text_embedding_3_large"
    assert retriever._embedding_dimension == 3072
    assert retriever.calls == [
        {
            "query_text": "verify identity",
            "top_k": 5,
            "filters": {"tenant_id": "sample-prompts"},
        }
    ]


def test_get_explorer_graph_for_tenant_global_builds_layer_category_family_prompt_chain() -> None:
    driver = StubDriver(
        responses=[
            [
                {
                    "prompt_id": "os.style.empathetic",
                    "name": "Empathetic Style",
                    "category": "os",
                    "layer_path": "org.os",
                    "prompt_parent": "os.style",
                    "prompt_path_lineage": ["os", "os.style", "os.style.empathetic"],
                    "layer_lineage": ["org", "org.os"],
                    "category_lineage": ["os"],
                }
            ]
        ]
    )
    repo = Neo4jPromptRepository(
        driver=driver,
        database="neo4j",
        vector_index_name="prompt_embedding_index",
        fulltext_index_name="prompt_fulltext_index",
    )

    graph = repo.get_explorer_graph_for_tenant("sample-prompts", view="global")

    node_ids = {node["id"] for node in graph["nodes"]}
    edge_ids = {edge["id"] for edge in graph["edges"]}

    assert {
        "layer:org",
        "layer:org.os",
        "category:os",
        "family:os.style",
        "prompt:os.style.empathetic",
    }.issubset(node_ids)
    assert {
        "layer:org->layer:org.os",
        "layer:org.os->category:os",
        "category:os->family:os.style",
        "family:os.style->prompt:os.style.empathetic",
    }.issubset(edge_ids)


def test_get_explorer_graph_for_tenant_changes_projection_by_view() -> None:
    row = {
        "prompt_id": "os.style.empathetic",
        "name": "Empathetic Style",
        "category": "os",
        "layer_path": "org.os",
        "prompt_parent": "os.style",
        "prompt_path_lineage": ["os", "os.style", "os.style.empathetic"],
        "layer_lineage": ["org", "org.os"],
        "category_lineage": ["os"],
    }
    driver = StubDriver(
        responses=[
            [row],
            [row],
        ]
    )
    repo = Neo4jPromptRepository(
        driver=driver,
        database="neo4j",
        vector_index_name="prompt_embedding_index",
        fulltext_index_name="prompt_fulltext_index",
    )

    category_graph = repo.get_explorer_graph_for_tenant("sample-prompts", view="category")
    family_graph = repo.get_explorer_graph_for_tenant("sample-prompts", view="prompt_family")

    category_node_ids = {node["id"] for node in category_graph["nodes"]}
    family_node_ids = {node["id"] for node in family_graph["nodes"]}
    category_edge_ids = {edge["id"] for edge in category_graph["edges"]}
    family_edge_ids = {edge["id"] for edge in family_graph["edges"]}

    assert "category:os" in category_node_ids
    assert "family:os.style" not in category_node_ids
    assert "family:os.style" in family_node_ids
    assert "category:os" not in family_node_ids
    assert "category:os->prompt:os.style.empathetic" in category_edge_ids
    assert "family:os.style->prompt:os.style.empathetic" in family_edge_ids


def test_list_cluster_runs_for_tenant_returns_latest_run_summaries() -> None:
    driver = StubDriver(
        responses=[
            [
                {
                    "run": {
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
                    },
                    "cluster_count": 3,
                },
                {
                    "run": {
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
                    },
                    "cluster_count": 1,
                },
            ]
        ]
    )
    repo = Neo4jPromptRepository(
        driver=driver,
        database="neo4j",
        vector_index_name="prompt_embedding_index",
        fulltext_index_name="prompt_fulltext_index",
    )

    runs = repo.list_cluster_runs_for_tenant("sample-prompts")

    assert [row["run_id"] for row in runs] == ["run_999", "run_123"]
    assert runs[0]["cluster_count"] == 3
    assert runs[0]["category_filter"] == "verification"
    assert "MATCH (run:ClusterRun {tenant_id: $tenant_id})" in driver.calls[-1]["query"]
    assert driver.calls[-1]["parameters"]["tenant_id"] == "sample-prompts"
