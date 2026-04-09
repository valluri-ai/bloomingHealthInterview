from __future__ import annotations

from app.domain.models import PromptGraphPayload, PromptRecord
from app.repositories.prompt_repository import PromptGraphRepository, PromptTemplateStore
from app.schemas.prompt import PromptInput
from app.services.hierarchy_service import HierarchyService
from app.utils.prompt_processing import (
    build_content_preview,
    build_embedding_text,
    build_search_text,
    extract_input_variables,
    normalize_prompt_content,
)


class PromptIngestionService:
    def __init__(self, repo: PromptGraphRepository, prompt_store: PromptTemplateStore) -> None:
        self.repo = repo
        self.prompt_store = prompt_store
        self.hierarchy = HierarchyService()

    def ingest_prompts(self, prompts: list[PromptInput]) -> dict:
        self.repo.ensure_schema()
        layer_taxonomy = self.hierarchy.seed_layer_taxonomy()
        self.repo.upsert_hierarchy_nodes(layer_taxonomy)

        prompt_ids: list[str] = []
        stored_prompts: list[dict[str, str | None]] = []
        for prompt in prompts:
            stored_version = self.prompt_store.store_prompt(prompt)
            normalized_content = normalize_prompt_content(prompt.content)
            input_variables = tuple(extract_input_variables(prompt.content))
            layer_path = self.hierarchy.resolve_layer_value(prompt.layer)
            prompt_path_nodes = tuple(self.hierarchy.build_path("prompt_path", prompt.prompt_id))
            category_nodes = tuple(self.hierarchy.build_path("category", prompt.category))
            layer_nodes = tuple(self.hierarchy.build_path("layer_path", layer_path))

            self.repo.upsert_hierarchy_nodes(list(prompt_path_nodes))
            self.repo.upsert_hierarchy_nodes(list(category_nodes))
            self.repo.upsert_hierarchy_nodes(list(layer_nodes))

            record = PromptRecord(
                prompt_id=prompt.prompt_id,
                category=prompt.category,
                layer=prompt.layer,
                layer_path=layer_path,
                layer_lineage=tuple(node.full_path for node in layer_nodes),
                name=prompt.name,
                content_preview=build_content_preview(normalized_content),
                normalized_content=normalized_content,
                input_variables=input_variables,
                prompt_parent=self.hierarchy.prompt_parent(prompt.prompt_id),
                prompt_path_lineage=tuple(node.full_path for node in prompt_path_nodes),
                category_lineage=tuple(node.full_path for node in category_nodes),
                embedding_text=build_embedding_text(
                    prompt_id=prompt.prompt_id,
                    name=prompt.name,
                    category=prompt.category,
                    layer_path=layer_path,
                    input_variables=list(input_variables),
                    normalized_content=normalized_content,
                ),
                search_text=build_search_text(
                    prompt_id=prompt.prompt_id,
                    name=prompt.name,
                    category=prompt.category,
                    layer_path=layer_path,
                    normalized_content=normalized_content,
                ),
                storage_bucket=stored_version.bucket,
                storage_key=stored_version.key,
                storage_version_id=stored_version.version_id,
                storage_uri=stored_version.s3_uri,
                embedding=None,
            )

            self.repo.upsert_prompt_graph(
                PromptGraphPayload(
                    prompt=record,
                    prompt_path_nodes=prompt_path_nodes,
                    category_nodes=category_nodes,
                    layer_nodes=layer_nodes,
                )
            )

            prompt_ids.append(prompt.prompt_id)
            stored_prompts.append(
                {
                    "prompt_id": prompt.prompt_id,
                    "bucket": stored_version.bucket,
                    "key": stored_version.key,
                    "version_id": stored_version.version_id,
                    "s3_uri": stored_version.s3_uri,
                }
            )

        return {
            "loaded_count": len(prompt_ids),
            "prompt_ids": prompt_ids,
            "stored_prompts": stored_prompts,
        }
