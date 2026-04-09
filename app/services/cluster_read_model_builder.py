from __future__ import annotations

from typing import Any

from app.repositories.prompt_repository import PromptGraphRepository
from app.services.strict_duplicate_clusterer import SimilarityPair


class ClusterReadModelBuilder:
    def __init__(self, repo: PromptGraphRepository) -> None:
        self.repo = repo

    def build_cluster_payload(
        self,
        *,
        cluster_id: str,
        prompt_ids: list[str],
        pairs: dict[frozenset[str], SimilarityPair],
        scope_mode: str,
        scope_key: str | None,
    ) -> dict[str, Any]:
        relevant_pairs = [
            pair
            for pair in pairs.values()
            if pair.prompt_a in prompt_ids and pair.prompt_b in prompt_ids
        ]
        prompt_rows = []
        for prompt_id in prompt_ids:
            prompt = self.repo.get_prompt(prompt_id)
            if not prompt:
                continue
            neighbor_scores = [
                pair.best_score
                for pair in relevant_pairs
                if prompt_id in {pair.prompt_a, pair.prompt_b}
            ]
            prompt_rows.append(
                {
                    "prompt_id": prompt_id,
                    "similarity_score": max(neighbor_scores) if neighbor_scores else 1.0,
                    "ranking_score": max(neighbor_scores) if neighbor_scores else 1.0,
                    "fulltext_score": None,
                    "content_preview": prompt.content_preview,
                    "category": prompt.category,
                    "layer_path": prompt.layer_path,
                    "prompt_parent": prompt.prompt_parent,
                    "prompt_path_lineage": list(prompt.prompt_path_lineage),
                    "layer_lineage": list(prompt.layer_lineage),
                    "category_lineage": list(prompt.category_lineage),
                    "input_variables": list(prompt.input_variables),
                    "match_sources": [],
                }
            )

        merge_suggestion = self._suggest_merge(prompt_ids, relevant_pairs)
        avg_similarity = (
            sum(pair.average_score for pair in relevant_pairs) / len(relevant_pairs)
            if relevant_pairs
            else 1.0
        )
        return {
            "cluster_id": cluster_id,
            "scope_mode": scope_mode,
            "scope_key": scope_key,
            "member_count": len(prompt_rows),
            "avg_similarity": avg_similarity,
            "prompts": sorted(prompt_rows, key=lambda row: (-row["similarity_score"], row["prompt_id"])),
            "edges": [
                pair.as_payload()
                for pair in sorted(
                    relevant_pairs,
                    key=lambda pair: (-pair.best_score, pair.prompt_a, pair.prompt_b),
                )
            ],
            "merge_suggestion": merge_suggestion,
        }

    def build_scope_payload(
        self,
        *,
        scope_type: str,
        scope_value: str,
        prompt_ids: list[str],
        clusters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "scope_type": scope_type,
            "scope_value": scope_value,
            "prompt_count": len(prompt_ids),
            "clusters": clusters,
        }

    def get_cluster_from_run(
        self,
        *,
        run: dict[str, Any],
        cluster_id: str,
    ) -> dict[str, Any] | None:
        for cluster in run.get("clusters", []):
            if cluster.get("cluster_id") == cluster_id:
                return cluster
        return None

    def build_run_visualization(self, *, run: dict[str, Any]) -> dict[str, Any]:
        node_ids: set[str] = set()
        edges_out: list[dict[str, Any]] = []
        clusters = run.get("clusters", [])
        for cluster in clusters:
            for prompt in cluster.get("prompts", []):
                node_ids.add(prompt["prompt_id"])
            edges_out.extend(cluster.get("edges", []))

        return {
            "nodes": [self._build_visual_node(prompt_id) for prompt_id in sorted(node_ids)],
            "edges": edges_out,
            "clusters": clusters,
        }

    def _suggest_merge(self, prompt_ids: list[str], pairs: list[SimilarityPair]) -> dict[str, Any]:
        canonical_prompt_id = self._choose_canonical_prompt_id(prompt_ids)
        canonical_prompt = self.repo.get_prompt(canonical_prompt_id)
        all_variables: list[str] = []
        for prompt_id in prompt_ids:
            prompt = self.repo.get_prompt(prompt_id)
            if not prompt:
                continue
            for variable in prompt.input_variables:
                if variable not in all_variables:
                    all_variables.append(variable)

        average_similarity = (
            sum(pair.average_score for pair in pairs) / len(pairs)
            if pairs
            else 1.0
        )
        rationale_parts = [
            f"Average semantic similarity is {average_similarity:.3f}.",
        ]
        if pairs and all(pair.shared_category for pair in pairs):
            rationale_parts.append("All prompts share the same category.")
        if pairs and all(pair.shared_layer_lineage for pair in pairs):
            rationale_parts.append("All prompts share a layer lineage.")
        if pairs and any(pair.shared_prompt_family for pair in pairs):
            rationale_parts.append("At least one pair shares the same prompt family.")

        unified_prompt_template = canonical_prompt.normalized_content if canonical_prompt else ""
        if all_variables:
            unified_prompt_template = (
                f"{unified_prompt_template}\n\nOptional variables: {', '.join(all_variables)}"
            ).strip()

        return {
            "canonical_prompt_id": canonical_prompt_id,
            "rationale": " ".join(rationale_parts),
            "optional_variables": all_variables,
            "unified_prompt_template": unified_prompt_template,
        }

    def _choose_canonical_prompt_id(self, prompt_ids: list[str]) -> str:
        def key(prompt_id: str) -> tuple[int, str]:
            prompt = self.repo.get_prompt(prompt_id)
            normalized_content = prompt.normalized_content if prompt else ""
            return (-len(normalized_content), prompt_id)

        return sorted(prompt_ids, key=key)[0]

    def _build_visual_node(self, prompt_id: str) -> dict[str, Any]:
        prompt = self.repo.get_prompt(prompt_id)
        if not prompt:
            return {"id": prompt_id, "label": prompt_id}
        return {
            "id": prompt_id,
            "label": prompt_id,
            "category": prompt.category,
            "layer_path": prompt.layer_path,
            "prompt_parent": prompt.prompt_parent,
            "input_variables": list(prompt.input_variables),
        }
