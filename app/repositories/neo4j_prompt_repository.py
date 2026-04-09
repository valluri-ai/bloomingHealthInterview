from __future__ import annotations

from dataclasses import asdict
import json
import re
from typing import Any, Callable

from neo4j import GraphDatabase
from neo4j.exceptions import ClientError
from neo4j_graphrag.retrievers import VectorCypherRetriever
from neo4j_graphrag.types import RetrieverResultItem

from app.domain.models import HierarchyNodeRecord, PromptGraphPayload, PromptRecord, TenantRecord
from app.repositories.prompt_repository import PromptGraphRepository, TenantAdminRepository

VECTOR_RETRIEVAL_QUERY = """
OPTIONAL MATCH (node)-[:USES_VARIABLE]->(var:InputVariable)
WITH node, score, collect(DISTINCT var.name) AS variable_names
RETURN
  node.prompt_id AS prompt_id,
  coalesce(node.content_preview, substring(node.normalized_content, 0, 160)) AS content_preview,
  node.category AS category,
  node.layer_path AS layer_path,
  node.prompt_parent AS prompt_parent,
  node.prompt_path_lineage AS prompt_path_lineage,
  node.layer_lineage AS layer_lineage,
  node.category_lineage AS category_lineage,
  coalesce(node.input_variables, variable_names) AS input_variables,
  score AS similarity_score
"""


class Neo4jPromptRepository(PromptGraphRepository, TenantAdminRepository):
    def __init__(
        self,
        *,
        driver: Any | None = None,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
        vector_index_name: str = "prompt_embedding_index",
        fulltext_index_name: str = "prompt_fulltext_index",
        embedder: Any | None = None,
    ) -> None:
        if driver is None:
            if not uri or not username or not password:
                raise ValueError("Neo4j connection details are required")
            driver = GraphDatabase.driver(uri, auth=(username, password))
        self.driver = driver
        self.database = database
        self.vector_index_name = vector_index_name
        self.fulltext_index_name = fulltext_index_name
        self.embedder = embedder
        self._vector_retrievers: dict[str, VectorCypherRetriever] = {}

    def close(self) -> None:
        self.driver.close()

    def ensure_schema(
        self,
        *,
        vector_dimensions: int = 3072,
        embedding_property: str = "embedding",
        index_name: str | None = None,
    ) -> None:
        index_name = index_name or self.vector_index_name
        self.driver.execute_query(
            """
            MATCH (cluster:Cluster)
            WITH cluster.node_id AS node_id, collect(cluster) AS nodes
            WHERE node_id IS NOT NULL AND size(nodes) > 1
            FOREACH (duplicate IN tail(nodes) | DETACH DELETE duplicate)
            """,
            database_=self.database,
        )
        drop_queries = [
            "DROP CONSTRAINT prompt_id_unique IF EXISTS",
            "DROP CONSTRAINT input_variable_name_unique IF EXISTS",
        ]
        for query in drop_queries:
            self.driver.execute_query(query, database_=self.database)
        queries = [
            "CREATE CONSTRAINT tenant_id_unique IF NOT EXISTS FOR (t:Tenant) REQUIRE t.tenant_id IS UNIQUE",
            "CREATE CONSTRAINT prompt_node_id_unique IF NOT EXISTS FOR (p:Prompt) REQUIRE p.node_id IS UNIQUE",
            "CREATE CONSTRAINT hierarchy_node_id_unique IF NOT EXISTS FOR (n:HierarchyNode) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT input_variable_node_id_unique IF NOT EXISTS FOR (v:InputVariable) REQUIRE v.node_id IS UNIQUE",
            "CREATE CONSTRAINT cluster_run_id_unique IF NOT EXISTS FOR (r:ClusterRun) REQUIRE r.run_id IS UNIQUE",
            "CREATE CONSTRAINT cluster_node_id_unique IF NOT EXISTS FOR (c:Cluster) REQUIRE c.node_id IS UNIQUE",
            f"CREATE FULLTEXT INDEX {self.fulltext_index_name} IF NOT EXISTS FOR (p:Prompt) ON EACH [p.search_text, p.prompt_id, p.category, p.layer_path, p.name]",
        ]
        for query in queries:
            self.driver.execute_query(query, database_=self.database)

        current_dimensions = self._current_vector_dimensions(index_name=index_name)
        if current_dimensions is not None and current_dimensions != vector_dimensions:
            self.driver.execute_query(
                f"DROP INDEX {index_name} IF EXISTS",
                database_=self.database,
            )

        self.driver.execute_query(
            (
                f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS "
                f"FOR (p:Prompt) ON (p.{embedding_property}) "
                f"OPTIONS {{indexConfig: {{`vector.dimensions`: {vector_dimensions}, `vector.similarity_function`: 'cosine'}}}}"
            ),
            database_=self.database,
        )

    def upsert_hierarchy_nodes(self, nodes: list[HierarchyNodeRecord]) -> None:
        if not nodes:
            return
        query = """
        UNWIND $nodes AS node
        MERGE (current:HierarchyNode {node_id: node.node_id})
        SET
          current.kind = node.kind,
          current.value = node.value,
          current.full_path = node.full_path,
          current.depth = node.depth,
          current.parent_path = node.parent_path
        FOREACH (_ IN CASE WHEN node.parent_path IS NULL THEN [] ELSE [1] END |
          MERGE (parent:HierarchyNode {node_id: node.kind + ':' + node.parent_path})
          MERGE (current)-[:CHILD_OF]->(parent)
        )
        """
        self.driver.execute_query(
            query,
            parameters_={"nodes": [asdict(node) for node in nodes]},
            database_=self.database,
        )

    def upsert_hierarchy_nodes_for_tenant(self, tenant_id: str, nodes: list[HierarchyNodeRecord]) -> None:
        if not nodes:
            return
        scoped_nodes = []
        for node in nodes:
            scoped_nodes.append(
                {
                    "node_id": self._tenant_node_id(tenant_id, node.node_id),
                    "kind": node.kind,
                    "value": node.value,
                    "full_path": node.full_path,
                    "depth": node.depth,
                    "tenant_id": tenant_id,
                    "parent_node_id": self._tenant_node_id(tenant_id, f"{node.kind}:{node.parent_path}")
                    if node.parent_path is not None
                    else None,
                }
            )
        query = """
        UNWIND $nodes AS node
        MERGE (current:HierarchyNode {node_id: node.node_id})
        SET
          current.kind = node.kind,
          current.value = node.value,
          current.full_path = node.full_path,
          current.depth = node.depth,
          current.tenant_id = node.tenant_id
        FOREACH (_ IN CASE WHEN node.parent_node_id IS NULL THEN [] ELSE [1] END |
          MERGE (parent:HierarchyNode {node_id: node.parent_node_id})
          MERGE (current)-[:CHILD_OF]->(parent)
        )
        """
        self.driver.execute_query(
            query,
            parameters_={"nodes": scoped_nodes},
            database_=self.database,
        )

    def list_tenants(self) -> list[TenantRecord]:
        query = """
        MATCH (tenant:Tenant)
        OPTIONAL MATCH (tenant)-[:OWNS_PROMPT]->(prompt:Prompt)
        RETURN
          tenant.tenant_id AS tenant_id,
          tenant.name AS name,
          tenant.is_builtin AS is_builtin,
          toString(tenant.created_at) AS created_at,
          count(prompt) AS prompt_count
        ORDER BY tenant.is_builtin DESC, tenant.name ASC
        """
        records, _, _ = self.driver.execute_query(query, database_=self.database)
        return [
            TenantRecord(
                tenant_id=record["tenant_id"],
                name=record["name"],
                is_builtin=bool(record.get("is_builtin")),
                created_at=record.get("created_at"),
                prompt_count=int(record.get("prompt_count") or 0),
            )
            for record in records
        ]

    def create_tenant(
        self,
        *,
        tenant_id: str,
        name: str,
        is_builtin: bool = False,
    ) -> TenantRecord:
        query = """
        MERGE (tenant:Tenant {tenant_id: $tenant_id})
        ON CREATE SET
          tenant.name = $name,
          tenant.is_builtin = $is_builtin,
          tenant.created_at = datetime().epochMillis
        ON MATCH SET
          tenant.name = $name,
          tenant.is_builtin = coalesce(tenant.is_builtin, false) OR $is_builtin
        RETURN
          tenant.tenant_id AS tenant_id,
          tenant.name AS name,
          tenant.is_builtin AS is_builtin,
          toString(tenant.created_at) AS created_at
        LIMIT 1
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"tenant_id": tenant_id, "name": name, "is_builtin": is_builtin},
            database_=self.database,
        )
        record = records[0]
        return TenantRecord(
            tenant_id=record["tenant_id"],
            name=record["name"],
            is_builtin=bool(record.get("is_builtin")),
            created_at=record.get("created_at"),
            prompt_count=self.count_prompts_for_tenant(tenant_id),
        )

    def get_tenant(self, tenant_id: str) -> TenantRecord | None:
        query = """
        MATCH (tenant:Tenant {tenant_id: $tenant_id})
        OPTIONAL MATCH (tenant)-[:OWNS_PROMPT]->(prompt:Prompt)
        RETURN
          tenant.tenant_id AS tenant_id,
          tenant.name AS name,
          tenant.is_builtin AS is_builtin,
          toString(tenant.created_at) AS created_at,
          count(prompt) AS prompt_count
        LIMIT 1
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"tenant_id": tenant_id},
            database_=self.database,
        )
        if not records:
            return None
        record = records[0]
        return TenantRecord(
            tenant_id=record["tenant_id"],
            name=record["name"],
            is_builtin=bool(record.get("is_builtin")),
            created_at=record.get("created_at"),
            prompt_count=int(record.get("prompt_count") or 0),
        )

    def tenant_exists(self, tenant_id: str) -> bool:
        return self.get_tenant(tenant_id) is not None

    def count_prompts_for_tenant(self, tenant_id: str) -> int:
        query = """
        MATCH (:Tenant {tenant_id: $tenant_id})-[:OWNS_PROMPT]->(prompt:Prompt)
        RETURN count(prompt) AS prompt_count
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"tenant_id": tenant_id},
            database_=self.database,
        )
        if not records:
            return 0
        return int(records[0].get("prompt_count") or 0)

    def upsert_prompt_graph_for_tenant(self, tenant_id: str, payload: PromptGraphPayload) -> None:
        parameters = {
            "tenant_id": tenant_id,
            "prompt_node_id": f"{tenant_id}:{payload.prompt.prompt_id}",
            "prompt_path_leaf_id": self._tenant_node_id(tenant_id, payload.prompt_path_nodes[-1].node_id),
            "category_leaf_id": self._tenant_node_id(tenant_id, payload.category_nodes[-1].node_id),
            "layer_leaf_id": payload.layer_nodes[-1].node_id,
            "input_variables": list(payload.prompt.input_variables),
            "input_variable_ids": [self._tenant_input_variable_id(tenant_id, name) for name in payload.prompt.input_variables],
            "prompt": {
                **self._prompt_to_dict(payload.prompt),
                "tenant_id": tenant_id,
                "node_id": f"{tenant_id}:{payload.prompt.prompt_id}",
            },
        }
        query = """
        MERGE (tenant:Tenant {tenant_id: $tenant_id})
        MERGE (p:Prompt {node_id: $prompt_node_id})
        SET p += $prompt
        WITH tenant, p
        MERGE (tenant)-[:OWNS_PROMPT]->(p)
        WITH tenant, p
        OPTIONAL MATCH (p)-[r:HAS_PROMPT_PATH|IN_CATEGORY|IN_LAYER_PATH|USES_VARIABLE]->()
        DELETE r
        WITH tenant, p
        MATCH (promptPath:HierarchyNode {node_id: $prompt_path_leaf_id})
        MATCH (category:HierarchyNode {node_id: $category_leaf_id})
        MATCH (layer:HierarchyNode {node_id: $layer_leaf_id})
        MERGE (p)-[:HAS_PROMPT_PATH]->(promptPath)
        MERGE (p)-[:IN_CATEGORY]->(category)
        MERGE (p)-[:IN_LAYER_PATH]->(layer)
        FOREACH (index IN CASE WHEN size($input_variables) = 0 THEN [] ELSE range(0, size($input_variables) - 1) END |
          MERGE (var:InputVariable {node_id: $input_variable_ids[index]})
          SET var.name = $input_variables[index], var.tenant_id = $tenant_id
          MERGE (p)-[:USES_VARIABLE]->(var)
        )
        """
        self.driver.execute_query(query, parameters_=parameters, database_=self.database)

    def get_prompt_for_tenant(self, tenant_id: str, prompt_id: str) -> PromptRecord | None:
        query = """
        MATCH (p:Prompt {tenant_id: $tenant_id, prompt_id: $prompt_id})
        RETURN p AS prompt
        LIMIT 1
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"tenant_id": tenant_id, "prompt_id": prompt_id},
            database_=self.database,
        )
        if not records:
            return None
        return self._prompt_from_record(records[0]["prompt"])

    def list_prompt_ids_for_tenant(
        self,
        tenant_id: str,
        *,
        requires_embedding: bool = False,
        embedding_property: str | None = None,
    ) -> list[str]:
        if requires_embedding and embedding_property:
            query = f"""
            MATCH (p:Prompt {{tenant_id: $tenant_id}})
            WHERE p.{embedding_property} IS NOT NULL
            RETURN p.prompt_id AS prompt_id
            ORDER BY p.prompt_id
            """
            records, _, _ = self.driver.execute_query(
                query,
                parameters_={"tenant_id": tenant_id},
                database_=self.database,
            )
            return [record["prompt_id"] for record in records]
        query = """
        MATCH (p:Prompt {tenant_id: $tenant_id})
        WHERE (NOT $requires_embedding) OR p.embedding IS NOT NULL
        RETURN p.prompt_id AS prompt_id
        ORDER BY p.prompt_id
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"tenant_id": tenant_id, "requires_embedding": requires_embedding},
            database_=self.database,
        )
        return [record["prompt_id"] for record in records]

    def list_prompts_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (p:Prompt {tenant_id: $tenant_id})
        RETURN
          p.prompt_id AS prompt_id,
          p.name AS name,
          p.category AS category,
          p.layer AS layer,
          p.layer_path AS layer_path,
          p.prompt_parent AS prompt_parent,
          coalesce(p.available_embedding_models, []) AS available_embedding_models
        ORDER BY p.layer_path, p.category, p.prompt_id
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"tenant_id": tenant_id},
            database_=self.database,
        )
        return [dict(record) for record in records]

    def get_prompt_embedding_for_tenant(
        self,
        tenant_id: str,
        prompt_id: str,
        *,
        embedding_property: str | None = None,
    ) -> list[float] | None:
        property_name = embedding_property or "embedding"
        query = """
        MATCH (p:Prompt {tenant_id: $tenant_id, prompt_id: $prompt_id})
        RETURN p[$embedding_property] AS embedding
        LIMIT 1
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={
                "tenant_id": tenant_id,
                "prompt_id": prompt_id,
                "embedding_property": property_name,
            },
            database_=self.database,
        )
        if not records:
            return None
        return records[0].get("embedding")

    def upsert_prompt_graph(self, payload: PromptGraphPayload) -> None:
        parameters = {
            "prompt": self._prompt_to_dict(payload.prompt),
            "prompt_path_leaf_id": payload.prompt_path_nodes[-1].node_id,
            "category_leaf_id": payload.category_nodes[-1].node_id,
            "layer_leaf_id": payload.layer_nodes[-1].node_id,
            "input_variables": list(payload.prompt.input_variables),
        }
        query = """
        MERGE (p:Prompt {prompt_id: $prompt.prompt_id})
        SET p += $prompt
        WITH p
        OPTIONAL MATCH (p)-[r:HAS_PROMPT_PATH|IN_CATEGORY|IN_LAYER_PATH|USES_VARIABLE]->()
        DELETE r
        WITH p
        MATCH (promptPath:HierarchyNode {node_id: $prompt_path_leaf_id})
        MATCH (category:HierarchyNode {node_id: $category_leaf_id})
        MATCH (layer:HierarchyNode {node_id: $layer_leaf_id})
        MERGE (p)-[:HAS_PROMPT_PATH]->(promptPath)
        MERGE (p)-[:IN_CATEGORY]->(category)
        MERGE (p)-[:IN_LAYER_PATH]->(layer)
        FOREACH (var_name IN $input_variables |
          MERGE (var:InputVariable {name: var_name})
          MERGE (p)-[:USES_VARIABLE]->(var)
        )
        """
        self.driver.execute_query(query, parameters_=parameters, database_=self.database)

    def get_prompt(self, prompt_id: str) -> PromptRecord | None:
        query = "MATCH (p:Prompt {prompt_id: $prompt_id}) RETURN p AS prompt LIMIT 1"
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"prompt_id": prompt_id},
            database_=self.database,
        )
        if not records:
            return None
        return self._prompt_from_record(records[0]["prompt"])

    def list_prompt_ids(
        self,
        *,
        requires_embedding: bool = False,
        embedding_property: str | None = None,
    ) -> list[str]:
        if requires_embedding and embedding_property:
            query = f"""
        MATCH (p:Prompt)
        WHERE p.{embedding_property} IS NOT NULL
        RETURN p.prompt_id AS prompt_id
        ORDER BY p.prompt_id
        """
            records, _, _ = self.driver.execute_query(query, database_=self.database)
            return [record["prompt_id"] for record in records]

        query = """
        MATCH (p:Prompt)
        WHERE (NOT $requires_embedding) OR p.embedding IS NOT NULL
        RETURN p.prompt_id AS prompt_id
        ORDER BY p.prompt_id
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"requires_embedding": requires_embedding},
            database_=self.database,
        )
        return [record["prompt_id"] for record in records]

    def list_prompts(self) -> list[dict[str, Any]]:
        query = """
        MATCH (p:Prompt)
        RETURN
          p.prompt_id AS prompt_id,
          p.name AS name,
          p.category AS category,
          p.layer AS layer,
          p.layer_path AS layer_path,
          p.prompt_parent AS prompt_parent,
          coalesce(p.available_embedding_models, []) AS available_embedding_models
        ORDER BY p.layer_path, p.category, p.prompt_id
        """
        records, _, _ = self.driver.execute_query(query, database_=self.database)
        return [dict(record) for record in records]

    def get_prompt_embedding(
        self,
        prompt_id: str,
        *,
        embedding_property: str | None = None,
    ) -> list[float] | None:
        property_name = embedding_property or "embedding"
        query = """
        MATCH (p:Prompt {prompt_id: $prompt_id})
        RETURN p[$embedding_property] AS embedding
        LIMIT 1
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"prompt_id": prompt_id, "embedding_property": property_name},
            database_=self.database,
        )
        if not records:
            return None
        return records[0].get("embedding")

    def generate_embeddings(
        self,
        *,
        prompt_ids: list[str] | None,
        embed_batch: Callable[[list[str]], list[list[float]]],
        batch_size: int,
        vector_dimensions: int,
        embedding_property: str = "embedding",
        model_label: str | None = None,
    ) -> int:
        select_query = """
        MATCH (p:Prompt)
        WHERE $prompt_ids IS NULL OR p.prompt_id IN $prompt_ids
        RETURN p.prompt_id AS prompt_id, p.embedding_text AS embedding_text
        ORDER BY p.prompt_id
        """
        records, _, _ = self.driver.execute_query(
            select_query,
            parameters_={"prompt_ids": prompt_ids},
            database_=self.database,
        )
        prompt_rows = [(record["prompt_id"], record["embedding_text"]) for record in records]

        total_updated = 0
        for start in range(0, len(prompt_rows), batch_size):
            batch = prompt_rows[start : start + batch_size]
            embedding_vectors = embed_batch([row[1] for row in batch])
            if len(embedding_vectors) != len(batch):
                raise ValueError("Embedding batch size mismatch")
            update_query = """
            UNWIND range(0, size($prompt_ids) - 1) AS index
            MATCH (p:Prompt {prompt_id: $prompt_ids[index]})
            CALL db.create.setNodeVectorProperty(p, $embedding_property, $embedding_vectors[index])
            SET p.available_embedding_models =
              CASE
                WHEN $model_label IS NULL THEN coalesce(p.available_embedding_models, [])
                WHEN p.available_embedding_models IS NULL THEN [$model_label]
                WHEN $model_label IN p.available_embedding_models THEN p.available_embedding_models
                ELSE p.available_embedding_models + $model_label
              END
            RETURN count(*) AS updated
            """
            batch_records, _, _ = self.driver.execute_query(
                update_query,
                parameters_={
                    "prompt_ids": [row[0] for row in batch],
                    "embedding_vectors": embedding_vectors,
                    "embedding_property": embedding_property,
                    "model_label": model_label,
                },
                database_=self.database,
            )
            if batch_records:
                total_updated += int(batch_records[0].get("updated", 0))
        return total_updated

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
        if not query_text and query_vector is None:
            return []
        retriever = self._get_vector_retriever(
            index_name=index_name or self.vector_index_name,
            node_label=node_label,
            embedding_node_property=embedding_node_property,
            embedding_dimension=embedding_dimension,
        )
        kwargs: dict[str, Any] = {"top_k": limit}
        if query_vector is not None:
            kwargs["query_vector"] = query_vector
        else:
            kwargs["query_text"] = query_text
        if filters:
            kwargs["filters"] = filters
        result = retriever.search(**kwargs)
        return [dict(item.metadata or {}) for item in result.items]

    def fulltext_search(
        self,
        *,
        query_text: str,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        lucene_query = self._to_lucene_query(query_text)
        if not lucene_query:
            return []

        filter_clause, filter_params = self._build_filter_clause(filters or {})
        query = f"""
        CALL db.index.fulltext.queryNodes($fulltext_index_name, $query_text, {{limit: $limit}})
        YIELD node, score
        {filter_clause}
        OPTIONAL MATCH (node)-[:USES_VARIABLE]->(var:InputVariable)
        WITH node, score, collect(DISTINCT var.name) AS variable_names
        RETURN
          node.prompt_id AS prompt_id,
          coalesce(node.content_preview, substring(node.normalized_content, 0, 160)) AS content_preview,
          node.category AS category,
          node.layer_path AS layer_path,
          node.prompt_parent AS prompt_parent,
          node.prompt_path_lineage AS prompt_path_lineage,
          node.layer_lineage AS layer_lineage,
          node.category_lineage AS category_lineage,
          coalesce(node.input_variables, variable_names) AS input_variables,
          score AS fulltext_score
        ORDER BY fulltext_score DESC
        LIMIT $limit
        """
        parameters = {
            "fulltext_index_name": self.fulltext_index_name,
            "query_text": lucene_query,
            "limit": limit,
            **filter_params,
        }
        records, _, _ = self.driver.execute_query(
            query,
            parameters_=parameters,
            database_=self.database,
        )
        return [dict(record) for record in records]

    def generate_embeddings_for_tenant(
        self,
        tenant_id: str,
        *,
        prompt_ids: list[str] | None,
        embed_batch: Callable[[list[str]], list[list[float]]],
        batch_size: int,
        vector_dimensions: int,
        embedding_property: str = "embedding",
        model_label: str | None = None,
    ) -> int:
        select_query = """
        MATCH (p:Prompt {tenant_id: $tenant_id})
        WHERE $prompt_ids IS NULL OR p.prompt_id IN $prompt_ids
        RETURN p.prompt_id AS prompt_id, p.embedding_text AS embedding_text
        ORDER BY p.prompt_id
        """
        records, _, _ = self.driver.execute_query(
            select_query,
            parameters_={"tenant_id": tenant_id, "prompt_ids": prompt_ids},
            database_=self.database,
        )
        prompt_rows = [(record["prompt_id"], record["embedding_text"]) for record in records]
        total_updated = 0
        for start in range(0, len(prompt_rows), batch_size):
            batch = prompt_rows[start : start + batch_size]
            embedding_vectors = embed_batch([row[1] for row in batch])
            if len(embedding_vectors) != len(batch):
                raise ValueError("Embedding batch size mismatch")
            update_query = """
            UNWIND range(0, size($prompt_ids) - 1) AS index
            MATCH (p:Prompt {tenant_id: $tenant_id, prompt_id: $prompt_ids[index]})
            CALL db.create.setNodeVectorProperty(p, $embedding_property, $embedding_vectors[index])
            SET p.available_embedding_models =
              CASE
                WHEN $model_label IS NULL THEN coalesce(p.available_embedding_models, [])
                WHEN p.available_embedding_models IS NULL THEN [$model_label]
                WHEN $model_label IN p.available_embedding_models THEN p.available_embedding_models
                ELSE p.available_embedding_models + $model_label
              END
            RETURN count(*) AS updated
            """
            batch_records, _, _ = self.driver.execute_query(
                update_query,
                parameters_={
                    "tenant_id": tenant_id,
                    "prompt_ids": [row[0] for row in batch],
                    "embedding_vectors": embedding_vectors,
                    "embedding_property": embedding_property,
                    "model_label": model_label,
                },
                database_=self.database,
            )
            if batch_records:
                total_updated += int(batch_records[0].get("updated", 0))
        return total_updated

    def vector_search_for_tenant(
        self,
        tenant_id: str,
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
        scoped_filters = dict(filters or {})
        scoped_filters["tenant_id"] = tenant_id
        return self.vector_search(
            query_text=query_text,
            query_vector=query_vector,
            limit=limit,
            filters=scoped_filters,
            index_name=index_name,
            node_label=node_label,
            embedding_node_property=embedding_node_property,
            embedding_dimension=embedding_dimension,
        )

    def fulltext_search_for_tenant(
        self,
        tenant_id: str,
        *,
        query_text: str,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        scoped_filters = dict(filters or {})
        scoped_filters["tenant_id"] = tenant_id
        return self.fulltext_search(
            query_text=query_text,
            limit=limit,
            filters=scoped_filters,
        )

    def generate_similarity_candidates_for_tenant(self, tenant_id: str, **kwargs: Any) -> list[dict[str, Any]] | None:
        prompt_ids: list[str] | None = kwargs.get("prompt_ids")
        top_k = int(kwargs.get("top_k", 10))
        similarity_cutoff = float(kwargs.get("similarity_cutoff", 0.0))
        embedding_property = str(kwargs.get("embedding_property", "embedding"))

        graph_name = f"prompt_similarity_{re.sub(r'[^A-Za-z0-9_]+', '_', embedding_property)}"
        try:
            self.driver.execute_query(
                "CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName",
                parameters_={"graph_name": graph_name},
                database_=self.database,
            )
            self.driver.execute_query(
                """
                CALL gds.graph.project(
                  $graph_name,
                  'Prompt',
                  '*',
                  { nodeProperties: [$embedding_property] }
                )
                YIELD graphName
                RETURN graphName
                """,
                parameters_={"graph_name": graph_name, "embedding_property": embedding_property},
                database_=self.database,
            )

            candidate_query = """
            MATCH (p:Prompt)
            WHERE p.tenant_id = $tenant_id
              AND ($prompt_ids IS NULL OR p.prompt_id IN $prompt_ids)
              AND p[$embedding_property] IS NOT NULL
            WITH collect(id(p)) AS node_ids
            CALL gds.knn.filtered.stream(
              $graph_name,
              {
                topK: $top_k,
                nodeProperties: $node_properties,
                similarityCutoff: $similarity_cutoff,
                sourceNodeFilter: node_ids,
                targetNodeFilter: node_ids
              }
            )
            YIELD node1, node2, similarity
            WITH gds.util.asNode(node1) AS source, gds.util.asNode(node2) AS target, similarity
            RETURN
              source.prompt_id AS source_prompt_id,
              target.prompt_id AS target_prompt_id,
              similarity AS similarity_score,
              source.category = target.category AS shared_category,
              source.prompt_parent = target.prompt_parent AS shared_prompt_family,
              size([segment IN coalesce(source.layer_lineage, []) WHERE segment IN coalesce(target.layer_lineage, [])]) > 0 AS shared_layer_lineage,
              size([variable IN coalesce(source.input_variables, []) WHERE variable IN coalesce(target.input_variables, [])]) AS shared_variable_count
            ORDER BY source_prompt_id, similarity_score DESC, target_prompt_id
            """
            records, _, _ = self.driver.execute_query(
                candidate_query,
                parameters_={
                    "tenant_id": tenant_id,
                    "graph_name": graph_name,
                    "prompt_ids": prompt_ids,
                    "embedding_property": embedding_property,
                    "top_k": top_k,
                    "similarity_cutoff": similarity_cutoff,
                    "node_properties": {embedding_property: "COSINE"},
                },
                database_=self.database,
            )
            self.driver.execute_query(
                "CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName",
                parameters_={"graph_name": graph_name},
                database_=self.database,
            )
        except ClientError as exc:
            message = str(exc)
            if "gds." in message and ("ProcedureNotFound" in message or "There is no procedure" in message):
                return None
            raise
        rows = [dict(record) for record in records]
        rank_by_source: dict[str, int] = {}
        for row in rows:
            source_prompt_id = row["source_prompt_id"]
            rank = rank_by_source.get(source_prompt_id, 0) + 1
            rank_by_source[source_prompt_id] = rank
            row["rank"] = rank
        return rows

    def generate_similarity_candidates(self, **kwargs: Any) -> list[dict[str, Any]] | None:
        prompt_ids: list[str] | None = kwargs.get("prompt_ids")
        top_k = int(kwargs.get("top_k", 10))
        similarity_cutoff = float(kwargs.get("similarity_cutoff", 0.0))
        embedding_property = str(kwargs.get("embedding_property", "embedding"))

        graph_name = f"prompt_similarity_{re.sub(r'[^A-Za-z0-9_]+', '_', embedding_property)}"
        try:
            self.driver.execute_query(
                "CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName",
                parameters_={"graph_name": graph_name},
                database_=self.database,
            )
            self.driver.execute_query(
                """
                CALL gds.graph.project(
                  $graph_name,
                  'Prompt',
                  '*',
                  { nodeProperties: [$embedding_property] }
                )
                YIELD graphName
                RETURN graphName
                """,
                parameters_={
                    "graph_name": graph_name,
                    "embedding_property": embedding_property,
                },
                database_=self.database,
            )

            candidate_query = """
            MATCH (p:Prompt)
            WHERE ($prompt_ids IS NULL OR p.prompt_id IN $prompt_ids)
              AND p[$embedding_property] IS NOT NULL
            WITH collect(id(p)) AS node_ids
            CALL gds.knn.filtered.stream(
              $graph_name,
              {
                topK: $top_k,
                nodeProperties: $node_properties,
                similarityCutoff: $similarity_cutoff,
                sourceNodeFilter: node_ids,
                targetNodeFilter: node_ids
              }
            )
            YIELD node1, node2, similarity
            WITH gds.util.asNode(node1) AS source, gds.util.asNode(node2) AS target, similarity
            RETURN
              source.prompt_id AS source_prompt_id,
              target.prompt_id AS target_prompt_id,
              similarity AS similarity_score,
              source.category = target.category AS shared_category,
              source.prompt_parent = target.prompt_parent AS shared_prompt_family,
              size([segment IN coalesce(source.layer_lineage, []) WHERE segment IN coalesce(target.layer_lineage, [])]) > 0 AS shared_layer_lineage,
              size([variable IN coalesce(source.input_variables, []) WHERE variable IN coalesce(target.input_variables, [])]) AS shared_variable_count
            ORDER BY source_prompt_id, similarity_score DESC, target_prompt_id
            """
            records, _, _ = self.driver.execute_query(
                candidate_query,
                parameters_={
                    "graph_name": graph_name,
                    "prompt_ids": prompt_ids,
                    "embedding_property": embedding_property,
                    "top_k": top_k,
                    "similarity_cutoff": similarity_cutoff,
                    "node_properties": {embedding_property: "COSINE"},
                },
                database_=self.database,
            )
            self.driver.execute_query(
                "CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName",
                parameters_={"graph_name": graph_name},
                database_=self.database,
            )
        except ClientError as exc:
            message = str(exc)
            if "gds." in message and ("ProcedureNotFound" in message or "There is no procedure" in message):
                return None
            raise
        rows = [dict(record) for record in records]
        rank_by_source: dict[str, int] = {}
        for row in rows:
            source_prompt_id = row["source_prompt_id"]
            rank = rank_by_source.get(source_prompt_id, 0) + 1
            rank_by_source[source_prompt_id] = rank
            row["rank"] = rank
        return rows

    def save_cluster_run_for_tenant(self, tenant_id: str, **kwargs: Any) -> None:
        run = kwargs["run"]
        run_node_id = f"{tenant_id}:{run['run_id']}"
        clusters = []
        for cluster in run.get("clusters", []):
            clusters.append(
                {
                    "props": {
                        "node_id": f"{tenant_id}:{run['run_id']}:{cluster['cluster_id']}",
                        "cluster_id": cluster["cluster_id"],
                        "scope_mode": cluster.get("scope_mode"),
                        "scope_key": cluster.get("scope_key"),
                        "member_count": cluster.get("member_count"),
                        "avg_similarity": cluster.get("avg_similarity"),
                        "canonical_prompt_id": cluster.get("merge_suggestion", {}).get("canonical_prompt_id"),
                        "rationale": cluster.get("merge_suggestion", {}).get("rationale"),
                        "optional_variables": cluster.get("merge_suggestion", {}).get("optional_variables", []),
                        "unified_prompt_template": cluster.get("merge_suggestion", {}).get("unified_prompt_template"),
                        "edges_json": json.dumps(cluster.get("edges", [])),
                    },
                    "prompts": cluster.get("prompts", []),
                }
            )
        query = """
        MERGE (tenant:Tenant {tenant_id: $tenant_id})
        MERGE (run:ClusterRun {run_id: $run.run_id})
        SET run += $run, run.node_id = $run_node_id, run.tenant_id = $tenant_id
        MERGE (tenant)-[:OWNS_RUN]->(run)
        WITH run
        OPTIONAL MATCH (run)-[:CONTAINS]->(existing:Cluster)
        DETACH DELETE existing
        WITH DISTINCT run
        UNWIND $clusters AS cluster
        CREATE (current:Cluster {node_id: cluster.props.node_id})
        SET current += cluster.props, current.tenant_id = $tenant_id
        MERGE (run)-[:CONTAINS]->(current)
        WITH current, cluster
        UNWIND cluster.prompts AS prompt_row
        MATCH (prompt:Prompt {tenant_id: $tenant_id, prompt_id: prompt_row.prompt_id})
        MERGE (current)-[member:HAS_MEMBER]->(prompt)
        SET member.score = prompt_row.similarity_score,
            member.rank = prompt_row.ranking_score
        """
        self.driver.execute_query(
            query,
            parameters_={
                "tenant_id": tenant_id,
                "run_node_id": run_node_id,
                "run": {key: value for key, value in run.items() if key != "clusters"},
                "clusters": clusters,
            },
            database_=self.database,
        )

    def get_cluster_run_for_tenant(self, tenant_id: str, run_id: str) -> dict[str, Any] | None:
        query = """
        MATCH (run:ClusterRun {tenant_id: $tenant_id, run_id: $run_id})
        OPTIONAL MATCH (run)-[:CONTAINS]->(cluster:Cluster)
        OPTIONAL MATCH (cluster)-[member:HAS_MEMBER]->(prompt:Prompt {tenant_id: $tenant_id})
        WITH run, cluster, member, prompt
        ORDER BY cluster.cluster_id, member.score DESC, prompt.prompt_id
        WITH run, cluster, collect(
          CASE
            WHEN prompt IS NULL THEN NULL
            ELSE {
              prompt_id: prompt.prompt_id,
              similarity_score: member.score,
              ranking_score: member.rank,
              fulltext_score: null,
              content_preview: prompt.content_preview,
              category: prompt.category,
              layer_path: prompt.layer_path,
              prompt_parent: prompt.prompt_parent,
              prompt_path_lineage: prompt.prompt_path_lineage,
              layer_lineage: prompt.layer_lineage,
              category_lineage: prompt.category_lineage,
              input_variables: coalesce(prompt.input_variables, []),
              match_sources: []
            }
          END
        ) AS prompts
        WITH run, collect(
          CASE
            WHEN cluster IS NULL THEN NULL
            ELSE {
              cluster_id: cluster.cluster_id,
              scope_mode: cluster.scope_mode,
              scope_key: cluster.scope_key,
              member_count: cluster.member_count,
              avg_similarity: cluster.avg_similarity,
              prompts: [row IN prompts WHERE row IS NOT NULL],
              edges: cluster.edges_json,
              merge_suggestion: {
                canonical_prompt_id: cluster.canonical_prompt_id,
                rationale: cluster.rationale,
                optional_variables: coalesce(cluster.optional_variables, []),
                unified_prompt_template: cluster.unified_prompt_template
              }
            }
          END
        ) AS clusters
        RETURN run, [cluster IN clusters WHERE cluster IS NOT NULL] AS clusters
        LIMIT 1
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"tenant_id": tenant_id, "run_id": run_id},
            database_=self.database,
        )
        if not records:
            return None
        record = records[0]
        run = dict(record["run"])
        clusters = []
        for cluster in record["clusters"]:
            row = dict(cluster)
            row["edges"] = json.loads(row.get("edges") or "[]")
            clusters.append(row)
        run["clusters"] = clusters
        return run

    def list_cluster_runs_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (run:ClusterRun {tenant_id: $tenant_id})
        OPTIONAL MATCH (run)-[:CONTAINS]->(cluster:Cluster)
        WITH run, count(cluster) AS cluster_count
        ORDER BY run.created_at DESC, run.run_id DESC
        RETURN run, cluster_count
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"tenant_id": tenant_id},
            database_=self.database,
        )
        results = []
        for record in records:
            run = dict(record["run"])
            run["cluster_count"] = int(record["cluster_count"])
            results.append(run)
        return results

    def get_prompt_graph_for_tenant(self, tenant_id: str, prompt_id: str) -> dict[str, Any]:
        query = """
        MATCH (p:Prompt {tenant_id: $tenant_id, prompt_id: $prompt_id})
        OPTIONAL MATCH (p)-[:USES_VARIABLE]->(var:InputVariable {tenant_id: $tenant_id})
        RETURN p AS prompt, collect(DISTINCT var.name) AS variables
        LIMIT 1
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"tenant_id": tenant_id, "prompt_id": prompt_id},
            database_=self.database,
        )
        if not records:
            raise KeyError(f"Prompt not found: {prompt_id}")
        record = records[0]
        prompt = self._prompt_from_record(record["prompt"])
        return {
            "prompt_id": prompt.prompt_id,
            "name": prompt.name,
            "category": prompt.category,
            "layer_path": prompt.layer_path,
            "prompt_parent": prompt.prompt_parent,
            "prompt_path_lineage": list(prompt.prompt_path_lineage),
            "layer_lineage": list(prompt.layer_lineage),
            "category_lineage": list(prompt.category_lineage),
            "variables": record.get("variables", []),
            "storage": {
                "bucket": prompt.storage_bucket,
                "key": prompt.storage_key,
                "version_id": prompt.storage_version_id,
                "s3_uri": prompt.storage_uri,
            },
        }

    def get_explorer_graph_for_tenant(
        self,
        tenant_id: str,
        *,
        view: str,
        category: str | None = None,
        hierarchy: str | None = None,
        layer_path: str | None = None,
        prompt_query: str | None = None,
    ) -> dict[str, Any]:
        query = """
        MATCH (p:Prompt {tenant_id: $tenant_id})
        WHERE ($category IS NULL OR p.category = $category)
          AND ($layer_path IS NULL OR p.layer_path = $layer_path)
          AND ($prompt_query IS NULL OR p.prompt_id CONTAINS $prompt_query OR coalesce(p.name, '') CONTAINS $prompt_query)
          AND (
            $hierarchy IS NULL OR
            $hierarchy IN split(p.layer_path, '.') OR
            $hierarchy IN coalesce(p.category_lineage, []) OR
            $hierarchy IN coalesce(p.prompt_path_lineage, [])
          )
        RETURN
          p.prompt_id AS prompt_id,
          p.name AS name,
          p.category AS category,
          p.layer_path AS layer_path,
          p.prompt_parent AS prompt_parent,
          p.prompt_path_lineage AS prompt_path_lineage,
          p.layer_lineage AS layer_lineage,
          p.category_lineage AS category_lineage
        ORDER BY p.layer_path, p.category, p.prompt_id
        LIMIT 300
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={
                "tenant_id": tenant_id,
                "category": category,
                "hierarchy": hierarchy,
                "layer_path": layer_path,
                "prompt_query": prompt_query,
            },
            database_=self.database,
        )
        rows = [dict(record) for record in records]
        return self._build_explorer_graph(
            tenant_id=tenant_id,
            view=view,
            rows=rows,
            category=category,
            hierarchy=hierarchy,
            layer_path=layer_path,
            prompt_query=prompt_query,
        )

    def _build_explorer_graph(
        self,
        *,
        tenant_id: str,
        view: str,
        rows: list[dict[str, Any]],
        category: str | None,
        hierarchy: str | None,
        layer_path: str | None,
        prompt_query: str | None,
    ) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        categories: set[str] = set()
        layers: set[str] = set()

        def ensure_node(node_id: str, *, label: str, kind: str, **extra: Any) -> None:
            if node_id in nodes:
                return
            nodes[node_id] = {
                "id": node_id,
                "label": label,
                "kind": kind,
                **extra,
            }

        def ensure_edge(source: str, target: str, kind: str) -> None:
            edge_id = f"{source}->{target}"
            if edge_id in edges:
                return
            edges[edge_id] = {
                "id": edge_id,
                "source": source,
                "target": target,
                "kind": kind,
            }

        for row in rows:
            prompt_node_id = f"prompt:{row['prompt_id']}"
            ensure_node(
                prompt_node_id,
                label=row["prompt_id"],
                kind="prompt",
                category=row["category"],
                layer_path=row["layer_path"],
                prompt_parent=row["prompt_parent"],
            )

            category_value = row.get("category")
            category_node_id = f"category:{category_value}" if category_value else None
            family_value = row.get("prompt_parent")
            family_node_id = f"family:{family_value}" if family_value else None
            layer_lineage = [segment for segment in row.get("layer_lineage", []) if segment]
            layer_leaf_id: str | None = None

            if category_value:
                categories.add(category_value)

            if view in {"global", "hierarchy", "layer_path"}:
                previous_layer_id: str | None = None
                for layer_segment in layer_lineage:
                    current_layer_id = f"layer:{layer_segment}"
                    ensure_node(
                        current_layer_id,
                        label=layer_segment,
                        kind="layer",
                        layer_path=layer_segment,
                    )
                    layers.add(layer_segment)
                    if previous_layer_id:
                        ensure_edge(previous_layer_id, current_layer_id, "layer_child")
                    previous_layer_id = current_layer_id
                layer_leaf_id = previous_layer_id

                if category_node_id and category_value:
                    ensure_node(category_node_id, label=category_value, kind="category")
                    if layer_leaf_id:
                        ensure_edge(layer_leaf_id, category_node_id, "contains_category")

                if family_node_id and family_value and family_value != category_value:
                    ensure_node(family_node_id, label=family_value, kind="prompt_family")
                    if category_node_id:
                        ensure_edge(category_node_id, family_node_id, "contains_family")
                    elif layer_leaf_id:
                        ensure_edge(layer_leaf_id, family_node_id, "contains_family")
                    ensure_edge(family_node_id, prompt_node_id, "contains_prompt")
                elif category_node_id:
                    ensure_edge(category_node_id, prompt_node_id, "contains_prompt")
                elif layer_leaf_id:
                    ensure_edge(layer_leaf_id, prompt_node_id, "contains_prompt")
                continue

            if view == "category":
                if category_node_id and category_value:
                    ensure_node(category_node_id, label=category_value, kind="category")
                    ensure_edge(category_node_id, prompt_node_id, "contains_prompt")
                continue

            if view == "prompt_family":
                family_label = family_value or row["prompt_id"]
                family_node_id = f"family:{family_label}"
                ensure_node(family_node_id, label=family_label, kind="prompt_family")
                ensure_edge(family_node_id, prompt_node_id, "contains_prompt")
                continue

            if category_node_id and category_value:
                ensure_node(category_node_id, label=category_value, kind="category")
                ensure_edge(category_node_id, prompt_node_id, "contains_prompt")

        return {
            "tenant_id": tenant_id,
            "view": view,
            "filters": {
                "category": category,
                "hierarchy": hierarchy,
                "layer_path": layer_path,
                "prompt_query": prompt_query,
            },
            "nodes": list(nodes.values()),
            "edges": list(edges.values()),
            "summary": {
                "prompt_count": len(rows),
                "category_count": len(categories),
                "layer_count": len(layers),
            },
        }

    def save_cluster_run(self, **kwargs: Any) -> None:
        run = kwargs["run"]
        clusters = []
        for cluster in run.get("clusters", []):
            clusters.append(
                {
                    "props": {
                        "node_id": f"{run['run_id']}:{cluster['cluster_id']}",
                        "cluster_id": cluster["cluster_id"],
                        "scope_mode": cluster.get("scope_mode"),
                        "scope_key": cluster.get("scope_key"),
                        "member_count": cluster.get("member_count"),
                        "avg_similarity": cluster.get("avg_similarity"),
                        "canonical_prompt_id": cluster.get("merge_suggestion", {}).get("canonical_prompt_id"),
                        "rationale": cluster.get("merge_suggestion", {}).get("rationale"),
                        "optional_variables": cluster.get("merge_suggestion", {}).get("optional_variables", []),
                        "unified_prompt_template": cluster.get("merge_suggestion", {}).get("unified_prompt_template"),
                        "edges_json": json.dumps(cluster.get("edges", [])),
                    },
                    "prompts": cluster.get("prompts", []),
                }
            )

        query = """
        MERGE (run:ClusterRun {run_id: $run.run_id})
        SET run += $run
        WITH run
        OPTIONAL MATCH (run)-[:CONTAINS]->(existing:Cluster)
        DETACH DELETE existing
        WITH DISTINCT run
        UNWIND $clusters AS cluster
        CREATE (current:Cluster {node_id: cluster.props.node_id})
        SET current += cluster.props
        MERGE (run)-[:CONTAINS]->(current)
        WITH current, cluster
        UNWIND cluster.prompts AS prompt_row
        MATCH (prompt:Prompt {prompt_id: prompt_row.prompt_id})
        MERGE (current)-[member:HAS_MEMBER]->(prompt)
        SET member.score = prompt_row.similarity_score,
            member.rank = prompt_row.ranking_score
        """
        self.driver.execute_query(
            query,
            parameters_={
                "run": {
                    key: value
                    for key, value in run.items()
                    if key != "clusters"
                },
                "clusters": clusters,
            },
            database_=self.database,
        )

    def get_cluster_run(self, run_id: str) -> dict[str, Any] | None:
        query = """
        MATCH (run:ClusterRun {run_id: $run_id})
        OPTIONAL MATCH (run)-[:CONTAINS]->(cluster:Cluster)
        OPTIONAL MATCH (cluster)-[member:HAS_MEMBER]->(prompt:Prompt)
        WITH run, cluster, member, prompt
        ORDER BY cluster.cluster_id, member.score DESC, prompt.prompt_id
        WITH run, cluster, collect(
          CASE
            WHEN prompt IS NULL THEN NULL
            ELSE {
              prompt_id: prompt.prompt_id,
              similarity_score: member.score,
              ranking_score: member.rank,
              fulltext_score: null,
              content_preview: prompt.content_preview,
              category: prompt.category,
              layer_path: prompt.layer_path,
              prompt_parent: prompt.prompt_parent,
              prompt_path_lineage: prompt.prompt_path_lineage,
              layer_lineage: prompt.layer_lineage,
              category_lineage: prompt.category_lineage,
              input_variables: coalesce(prompt.input_variables, []),
              match_sources: []
            }
          END
        ) AS prompts
        WITH run, collect(
          CASE
            WHEN cluster IS NULL THEN NULL
            ELSE {
              cluster_id: cluster.cluster_id,
              scope_mode: cluster.scope_mode,
              scope_key: cluster.scope_key,
              member_count: cluster.member_count,
              avg_similarity: cluster.avg_similarity,
              prompts: [row IN prompts WHERE row IS NOT NULL],
              edges: cluster.edges_json,
              merge_suggestion: {
                canonical_prompt_id: cluster.canonical_prompt_id,
                rationale: cluster.rationale,
                optional_variables: coalesce(cluster.optional_variables, []),
                unified_prompt_template: cluster.unified_prompt_template
              }
            }
          END
        ) AS clusters
        RETURN run, [cluster IN clusters WHERE cluster IS NOT NULL] AS clusters
        LIMIT 1
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"run_id": run_id},
            database_=self.database,
        )
        if not records:
            return None
        record = records[0]
        run = dict(record["run"])
        clusters = []
        for cluster in record["clusters"]:
            row = dict(cluster)
            row["edges"] = json.loads(row.get("edges") or "[]")
            clusters.append(row)
        run["clusters"] = clusters
        return run

    def list_cluster_runs(self) -> list[dict[str, Any]]:
        query = """
        MATCH (run:ClusterRun)
        OPTIONAL MATCH (run)-[:CONTAINS]->(cluster:Cluster)
        WITH run, count(cluster) AS cluster_count
        ORDER BY run.created_at DESC, run.run_id DESC
        RETURN run, cluster_count
        """
        records, _, _ = self.driver.execute_query(
            query,
            database_=self.database,
        )
        results = []
        for record in records:
            run = dict(record["run"])
            run["cluster_count"] = int(record["cluster_count"])
            results.append(run)
        return results

    def get_prompt_graph(self, prompt_id: str) -> dict[str, Any]:
        query = """
        MATCH (p:Prompt {prompt_id: $prompt_id})
        OPTIONAL MATCH (p)-[:HAS_PROMPT_PATH]->(prompt_path:HierarchyNode)
        OPTIONAL MATCH (p)-[:IN_CATEGORY]->(category:HierarchyNode)
        OPTIONAL MATCH (p)-[:IN_LAYER_PATH]->(layer:HierarchyNode)
        OPTIONAL MATCH (p)-[:USES_VARIABLE]->(var:InputVariable)
        RETURN
          p AS prompt,
          prompt_path AS prompt_path,
          category AS category,
          layer AS layer,
          collect(DISTINCT var.name) AS variables
        LIMIT 1
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"prompt_id": prompt_id},
            database_=self.database,
        )
        if not records:
            raise KeyError(f"Prompt not found: {prompt_id}")
        record = records[0]
        prompt = self._prompt_from_record(record["prompt"])
        return {
            "prompt_id": prompt.prompt_id,
            "name": prompt.name,
            "category": prompt.category,
            "layer_path": prompt.layer_path,
            "prompt_parent": prompt.prompt_parent,
            "prompt_path_lineage": list(prompt.prompt_path_lineage),
            "layer_lineage": list(prompt.layer_lineage),
            "category_lineage": list(prompt.category_lineage),
            "variables": record.get("variables", []),
            "storage": {
                "bucket": prompt.storage_bucket,
                "key": prompt.storage_key,
                "version_id": prompt.storage_version_id,
                "s3_uri": prompt.storage_uri,
            },
        }

    def _get_vector_retriever(
        self,
        *,
        index_name: str,
        node_label: str | None = None,
        embedding_node_property: str | None = None,
        embedding_dimension: int | None = None,
    ) -> VectorCypherRetriever:
        if index_name not in self._vector_retrievers:
            self._vector_retrievers[index_name] = VectorCypherRetriever(
                self.driver,
                index_name=index_name,
                retrieval_query=VECTOR_RETRIEVAL_QUERY,
                embedder=self.embedder,
                result_formatter=self._format_vector_result,
                neo4j_database=self.database,
            )
        retriever = self._vector_retrievers[index_name]
        if node_label is not None:
            setattr(retriever, "_node_label", node_label)
        if embedding_node_property is not None:
            setattr(retriever, "_node_embedding_property", embedding_node_property)
        if embedding_dimension is not None:
            setattr(retriever, "_embedding_dimension", embedding_dimension)
        return retriever

    def _current_vector_dimensions(self, *, index_name: str) -> int | None:
        query = """
        SHOW VECTOR INDEXES
        YIELD name, options
        WHERE name = $index_name
        RETURN options.indexConfig.`vector.dimensions` AS dimensions
        LIMIT 1
        """
        records, _, _ = self.driver.execute_query(
            query,
            parameters_={"index_name": index_name},
            database_=self.database,
        )
        if not records:
            return None
        dimensions = records[0].get("dimensions")
        return int(dimensions) if dimensions is not None else None

    def _format_vector_result(self, record: Any) -> RetrieverResultItem:
        metadata = dict(record)
        return RetrieverResultItem(
            content=metadata.get("content_preview", ""),
            metadata=metadata,
        )

    def _build_filter_clause(self, filters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if not filters:
            return "", {}
        clauses: list[str] = []
        parameters: dict[str, Any] = {}
        for index, (key, value) in enumerate(sorted(filters.items())):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise ValueError(f"Unsupported filter field: {key}")
            param_name = f"filter_{index}"
            clauses.append(f"node.{key} = ${param_name}")
            parameters[param_name] = value
        return f"WHERE {' AND '.join(clauses)}", parameters

    def _to_lucene_query(self, text: str) -> str:
        stripped = (text or "").strip()
        if not stripped:
            return ""
        escaped = re.sub(r'([+\-&|!(){}\\[\\]^"~*?:\\\\/])', r"\\\\\1", stripped)
        tokens = [token for token in re.findall(r"[A-Za-z0-9_]+", stripped) if len(token) > 1]
        fuzzy_terms = " OR ".join(f"{token}~2" for token in tokens[:8])
        phrase = f'"{escaped}"'
        if fuzzy_terms:
            return f"{phrase} OR {fuzzy_terms}"
        return phrase

    def _prompt_to_dict(self, prompt: PromptRecord) -> dict[str, Any]:
        payload = asdict(prompt)
        payload["layer_lineage"] = list(prompt.layer_lineage)
        payload["input_variables"] = list(prompt.input_variables)
        payload["prompt_path_lineage"] = list(prompt.prompt_path_lineage)
        payload["category_lineage"] = list(prompt.category_lineage)
        return payload

    def _prompt_from_record(self, prompt: Any) -> PromptRecord:
        data = dict(prompt)
        return PromptRecord(
            prompt_id=data["prompt_id"],
            category=data["category"],
            layer=data["layer"],
            layer_path=data["layer_path"],
            layer_lineage=tuple(data.get("layer_lineage", [])),
            name=data.get("name"),
            content_preview=data.get("content_preview", ""),
            normalized_content=data.get("normalized_content", ""),
            input_variables=tuple(data.get("input_variables", [])),
            prompt_parent=data.get("prompt_parent", data["prompt_id"]),
            prompt_path_lineage=tuple(data.get("prompt_path_lineage", [])),
            category_lineage=tuple(data.get("category_lineage", [])),
            embedding_text=data.get("embedding_text", ""),
            search_text=data.get("search_text", ""),
            storage_bucket=data.get("storage_bucket"),
            storage_key=data.get("storage_key"),
            storage_version_id=data.get("storage_version_id"),
            storage_uri=data.get("storage_uri"),
            embedding=data.get("embedding"),
        )

    def _tenant_node_id(self, tenant_id: str, node_id: str) -> str:
        return f"{tenant_id}:{node_id}"

    def _tenant_input_variable_id(self, tenant_id: str, variable_name: str) -> str:
        return f"{tenant_id}:input_variable:{variable_name}"
