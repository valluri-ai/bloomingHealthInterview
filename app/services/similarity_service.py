from __future__ import annotations

from typing import Any

from app.repositories.prompt_repository import PromptGraphRepository
from app.services.embedding_service import EmbeddingService


class SimilarityService:
    def __init__(self, repo: PromptGraphRepository) -> None:
        self.repo = repo

    def find_similar_by_prompt_id(
        self,
        prompt_id: str,
        *,
        limit: int = 5,
        threshold: float = 0.0,
        ranker: str = "rrf",
        alpha: float | None = None,
        rrf_k: int = 60,
        candidate_multiplier: int = 5,
        filters: dict[str, Any] | None = None,
        provider: str = "openai",
        model: str = "text-embedding-3-large",
    ) -> list[dict[str, Any]]:
        prompt = self.repo.get_prompt(prompt_id)
        embedding_service = EmbeddingService(provider=provider, model=model)
        embedding_vector = self.repo.get_prompt_embedding(
            prompt_id,
            embedding_property=embedding_service.embedding_property(),
        )
        if embedding_vector is None and prompt is not None:
            embedding_vector = prompt.embedding
        if not prompt or not embedding_vector:
            return []
        results = self._hybrid_search(
            query_text=prompt.normalized_content,
            query_vector=embedding_vector,
            limit=limit,
            threshold=threshold,
            ranker=ranker,
            alpha=alpha,
            rrf_k=rrf_k,
            candidate_multiplier=candidate_multiplier,
            filters=filters,
            provider=provider,
            model=model,
        )
        return [row for row in results if row["prompt_id"] != prompt_id][:limit]

    def search_semantic(
        self,
        *,
        query: str,
        query_vector: list[float] | None = None,
        limit: int = 10,
        threshold: float = 0.0,
        ranker: str = "rrf",
        alpha: float | None = None,
        rrf_k: int = 60,
        candidate_multiplier: int = 5,
        filters: dict[str, Any] | None = None,
        provider: str = "openai",
        model: str = "text-embedding-3-large",
    ) -> list[dict[str, Any]]:
        return self._hybrid_search(
            query_text=query,
            query_vector=query_vector,
            limit=limit,
            threshold=threshold,
            ranker=ranker,
            alpha=alpha,
            rrf_k=rrf_k,
            candidate_multiplier=candidate_multiplier,
            filters=filters,
            provider=provider,
            model=model,
        )

    def _hybrid_search(
        self,
        *,
        query_text: str,
        query_vector: list[float] | None,
        limit: int,
        threshold: float,
        ranker: str,
        alpha: float | None,
        rrf_k: int,
        candidate_multiplier: int,
        filters: dict[str, Any] | None,
        provider: str,
        model: str,
    ) -> list[dict[str, Any]]:
        embedding_service = EmbeddingService(provider=provider, model=model)
        base_index_name = getattr(self.repo, "vector_index_name", "prompt_embedding_index")
        candidate_limit = max(limit * max(candidate_multiplier, 1), limit)
        vector_results = self.repo.vector_search(
            query_text=query_text,
            query_vector=query_vector,
            limit=candidate_limit,
            filters=filters,
            index_name=embedding_service.vector_index_name(base_index_name),
            node_label="Prompt",
            embedding_node_property=embedding_service.embedding_property(),
            embedding_dimension=embedding_service.dimensions,
        )
        fulltext_results = self.repo.fulltext_search(
            query_text=query_text,
            limit=candidate_limit,
            filters=filters,
        )
        fused = self._fuse_results(
            vector_results=vector_results,
            fulltext_results=fulltext_results,
            ranker=ranker,
            alpha=alpha,
            rrf_k=rrf_k,
        )
        filtered: list[dict[str, Any]] = []
        for row in fused:
            similarity_score = row.get("similarity_score")
            if similarity_score is None and threshold > 0:
                continue
            if similarity_score is not None and float(similarity_score) < threshold:
                continue
            filtered.append(row)
        return filtered[:limit]

    def _fuse_results(
        self,
        *,
        vector_results: list[dict[str, Any]],
        fulltext_results: list[dict[str, Any]],
        ranker: str,
        alpha: float | None,
        rrf_k: int,
    ) -> list[dict[str, Any]]:
        ranker = ranker.lower()
        if ranker not in {"rrf", "naive", "linear"}:
            raise ValueError(f"Unsupported ranker: {ranker}")

        fused: dict[str, dict[str, Any]] = {}
        vector_max = max((float(row.get("similarity_score") or 0.0) for row in vector_results), default=0.0)
        fulltext_max = max((float(row.get("fulltext_score") or 0.0) for row in fulltext_results), default=0.0)
        alpha = 0.7 if alpha is None else alpha

        for rank, row in enumerate(vector_results, start=1):
            prompt_id = row["prompt_id"]
            entry = fused.setdefault(prompt_id, self._base_entry(row))
            entry["similarity_score"] = float(row.get("similarity_score") or 0.0)
            entry["vector_rank"] = rank
            entry["match_sources"].add("vector")
            entry["_vector_rank_score"] = 1.0 / (rrf_k + rank)
            entry["_vector_normalized"] = (
                float(row.get("similarity_score") or 0.0) / vector_max if vector_max else 0.0
            )

        for rank, row in enumerate(fulltext_results, start=1):
            prompt_id = row["prompt_id"]
            entry = fused.setdefault(prompt_id, self._base_entry(row))
            entry["fulltext_score"] = float(row.get("fulltext_score") or 0.0)
            entry["fulltext_rank"] = rank
            entry["match_sources"].add("fulltext")
            entry["_fulltext_rank_score"] = 1.0 / (rrf_k + rank)
            entry["_fulltext_normalized"] = (
                float(row.get("fulltext_score") or 0.0) / fulltext_max if fulltext_max else 0.0
            )

        results: list[dict[str, Any]] = []
        for entry in fused.values():
            vector_norm = entry.pop("_vector_normalized", 0.0)
            fulltext_norm = entry.pop("_fulltext_normalized", 0.0)
            vector_rank_score = entry.pop("_vector_rank_score", 0.0)
            fulltext_rank_score = entry.pop("_fulltext_rank_score", 0.0)

            if ranker == "rrf":
                entry["ranking_score"] = vector_rank_score + fulltext_rank_score
            elif ranker == "naive":
                entry["ranking_score"] = max(vector_norm, fulltext_norm)
            else:
                entry["ranking_score"] = (alpha * vector_norm) + ((1 - alpha) * fulltext_norm)

            entry["match_sources"] = [source for source in ("fulltext", "vector") if source in entry["match_sources"]]
            results.append(entry)

        return sorted(
            results,
            key=lambda row: (
                -float(row["ranking_score"]),
                -float(row.get("similarity_score") or 0.0),
                row["prompt_id"],
            ),
        )

    def _base_entry(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "prompt_id": row["prompt_id"],
            "content_preview": row.get("content_preview", ""),
            "category": row.get("category"),
            "layer_path": row.get("layer_path"),
            "prompt_parent": row.get("prompt_parent"),
            "prompt_path_lineage": row.get("prompt_path_lineage", []),
            "layer_lineage": row.get("layer_lineage", []),
            "category_lineage": row.get("category_lineage", []),
            "input_variables": row.get("input_variables", []),
            "similarity_score": row.get("similarity_score"),
            "fulltext_score": row.get("fulltext_score"),
            "ranking_score": 0.0,
            "match_sources": set(),
        }
