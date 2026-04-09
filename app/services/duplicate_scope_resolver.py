from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.repositories.prompt_repository import PromptGraphRepository
from app.services.embedding_service import EmbeddingService


class DuplicateScopeResolver:
    def __init__(self, repo: PromptGraphRepository) -> None:
        self.repo = repo

    def filter_prompt_ids(
        self,
        *,
        category_filter: str | None,
        hierarchy_filter: str | None,
        provider: str,
        model: str,
    ) -> set[str]:
        embedding_service = EmbeddingService(provider=provider, model=model)
        allowed_prompt_ids: set[str] = set()
        for prompt_id in self.repo.list_prompt_ids(
            requires_embedding=True,
            embedding_property=embedding_service.embedding_property(),
        ):
            prompt = self.repo.get_prompt(prompt_id)
            if not prompt:
                continue
            if category_filter and prompt.category != category_filter:
                continue
            if hierarchy_filter and not self.prompt_matches_hierarchy_filter(prompt, hierarchy_filter):
                continue
            allowed_prompt_ids.add(prompt_id)
        return allowed_prompt_ids

    def group_prompt_ids_by_scope(
        self,
        *,
        scope_mode: str,
        allowed_prompt_ids: set[str],
        hierarchy_filter: str | None,
    ) -> list[tuple[str, list[str]]]:
        if scope_mode not in {"category", "hierarchy", "prompt_family"}:
            raise ValueError(f"Unsupported scope mode: {scope_mode}")

        groups: dict[str, list[str]] = defaultdict(list)
        for prompt_id in sorted(allowed_prompt_ids):
            prompt = self.repo.get_prompt(prompt_id)
            if not prompt:
                continue

            if scope_mode == "category":
                groups[prompt.category].append(prompt_id)
                continue

            if scope_mode == "prompt_family":
                groups[prompt.prompt_parent].append(prompt_id)
                continue

            hierarchy_segments = self.prompt_hierarchy_segments(prompt)
            if hierarchy_filter:
                if hierarchy_filter in hierarchy_segments:
                    groups[hierarchy_filter].append(prompt_id)
            else:
                for segment in hierarchy_segments:
                    groups[segment].append(prompt_id)

        if scope_mode == "hierarchy":
            return [
                (scope_value, sorted(prompt_ids))
                for scope_value, prompt_ids in sorted(groups.items(), key=lambda item: self.hierarchy_sort_key(item[0]))
            ]

        return [(scope_value, sorted(prompt_ids)) for scope_value, prompt_ids in sorted(groups.items())]

    def scope_prompt_ids_for_prompt(
        self,
        *,
        prompt_id: str,
        provider: str,
        model: str,
    ) -> dict[str, tuple[str, list[str]]]:
        prompt = self.repo.get_prompt(prompt_id)
        if not prompt:
            raise KeyError(f"Prompt not found: {prompt_id}")

        embedding_service = EmbeddingService(provider=provider, model=model)
        all_prompt_ids = self.repo.list_prompt_ids(
            requires_embedding=True,
            embedding_property=embedding_service.embedding_property(),
        )
        category_prompt_ids = [
            other_id
            for other_id in all_prompt_ids
            if (other := self.repo.get_prompt(other_id)) and other.category == prompt.category
        ]
        layer_prompt_ids = [
            other_id
            for other_id in all_prompt_ids
            if (other := self.repo.get_prompt(other_id)) and other.layer_path == prompt.layer_path
        ]
        family_prompt_ids = [
            other_id
            for other_id in all_prompt_ids
            if (other := self.repo.get_prompt(other_id)) and other.prompt_parent == prompt.prompt_parent
        ]
        return {
            "category": (prompt.category, category_prompt_ids),
            "layer": (prompt.layer_path, layer_prompt_ids),
            "prompt_family": (prompt.prompt_parent, family_prompt_ids),
        }

    def prompt_hierarchy_segments(self, prompt: Any) -> list[str]:
        segments: list[str] = []
        for lineage in prompt.layer_lineage:
            segment = lineage.split(".")[-1]
            if segment and segment not in segments:
                segments.append(segment)
        return segments

    def prompt_matches_hierarchy_filter(self, prompt: Any, hierarchy_filter: str) -> bool:
        return hierarchy_filter in self.prompt_hierarchy_segments(prompt)

    def hierarchy_sort_key(self, value: str) -> tuple[int, str]:
        order = ["org", "os", "team", "engine", "directive"]
        try:
            return (order.index(value), value)
        except ValueError:
            return (len(order), value)
