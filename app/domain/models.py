from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HierarchyNodeRecord:
    node_id: str
    kind: str
    value: str
    full_path: str
    depth: int
    parent_path: str | None = None


@dataclass(frozen=True)
class StoredPromptVersion:
    bucket: str
    key: str
    version_id: str | None
    etag: str | None
    s3_uri: str


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str


@dataclass(frozen=True)
class TenantRecord:
    tenant_id: str
    name: str
    prompt_count: int = 0
    is_builtin: bool = False
    created_at: str | None = None


@dataclass(frozen=True)
class PromptRecord:
    prompt_id: str
    category: str
    layer: str
    layer_path: str
    layer_lineage: tuple[str, ...]
    name: str | None
    content_preview: str
    normalized_content: str
    input_variables: tuple[str, ...]
    prompt_parent: str
    prompt_path_lineage: tuple[str, ...]
    category_lineage: tuple[str, ...]
    embedding_text: str
    search_text: str
    storage_bucket: str | None
    storage_key: str | None
    storage_version_id: str | None
    storage_uri: str | None
    embedding: list[float] | None = None


@dataclass(frozen=True)
class PromptGraphPayload:
    prompt: PromptRecord
    prompt_path_nodes: tuple[HierarchyNodeRecord, ...]
    category_nodes: tuple[HierarchyNodeRecord, ...]
    layer_nodes: tuple[HierarchyNodeRecord, ...]
