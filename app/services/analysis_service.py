from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.repositories.prompt_repository import PromptGraphRepository
from app.services.cluster_read_model_builder import ClusterReadModelBuilder
from app.services.duplicate_candidate_service import DuplicateCandidateService
from app.services.duplicate_scope_resolver import DuplicateScopeResolver
from app.services.similarity_service import SimilarityService
from app.services.strict_duplicate_clusterer import StrictDuplicateClusterer


ALGORITHM_VERSION = "strict-v2"


class ClusterAnalysisService:
    def __init__(
        self,
        repo: PromptGraphRepository,
        similarity_service: SimilarityService,
        *,
        scope_resolver: DuplicateScopeResolver | None = None,
        candidate_service: DuplicateCandidateService | None = None,
        read_model_builder: ClusterReadModelBuilder | None = None,
        duplicate_clusterer: StrictDuplicateClusterer | None = None,
    ) -> None:
        self.repo = repo
        self.similarity_service = similarity_service
        self.scope_resolver = scope_resolver or DuplicateScopeResolver(repo)
        self.candidate_service = candidate_service or DuplicateCandidateService(repo, similarity_service)
        self.read_model_builder = read_model_builder or ClusterReadModelBuilder(repo)
        self.duplicate_clusterer = duplicate_clusterer or StrictDuplicateClusterer()

    def analyze_duplicates(
        self,
        *,
        threshold: float = 0.9,
        neighbor_limit: int = 10,
        ranker: str = "rrf",
        alpha: float | None = None,
        rrf_k: int = 60,
        candidate_multiplier: int = 5,
        provider: str = "openai",
        model: str = "text-embedding-3-large",
        category_filter: str | None = None,
        hierarchy_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        allowed_prompt_ids = self.scope_resolver.filter_prompt_ids(
            category_filter=category_filter,
            hierarchy_filter=hierarchy_filter,
            provider=provider,
            model=model,
        )
        return self._compute_duplicate_clusters(
            threshold=threshold,
            neighbor_limit=neighbor_limit,
            ranker=ranker,
            alpha=alpha,
            rrf_k=rrf_k,
            candidate_multiplier=candidate_multiplier,
            allowed_prompt_ids=allowed_prompt_ids,
            provider=provider,
            model=model,
        )

    def analyze_scoped_duplicates(
        self,
        *,
        scope_mode: str,
        threshold: float = 0.9,
        neighbor_limit: int = 10,
        ranker: str = "rrf",
        alpha: float | None = None,
        rrf_k: int = 60,
        candidate_multiplier: int = 5,
        provider: str = "openai",
        model: str = "text-embedding-3-large",
        category_filter: str | None = None,
        hierarchy_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        allowed_prompt_ids = self.scope_resolver.filter_prompt_ids(
            category_filter=category_filter,
            hierarchy_filter=hierarchy_filter,
            provider=provider,
            model=model,
        )
        groups = self.scope_resolver.group_prompt_ids_by_scope(
            scope_mode=scope_mode,
            allowed_prompt_ids=allowed_prompt_ids,
            hierarchy_filter=hierarchy_filter,
        )

        results: list[dict[str, Any]] = []
        for scope_value, prompt_ids in groups:
            clusters = self._compute_duplicate_clusters(
                threshold=threshold,
                neighbor_limit=neighbor_limit,
                ranker=ranker,
                alpha=alpha,
                rrf_k=rrf_k,
                candidate_multiplier=candidate_multiplier,
                allowed_prompt_ids=set(prompt_ids),
                provider=provider,
                model=model,
                scope_mode=scope_mode,
                scope_key=scope_value,
            )
            payload = self.read_model_builder.build_scope_payload(
                scope_type=scope_mode,
                scope_value=scope_value,
                prompt_ids=prompt_ids,
                clusters=clusters,
            )
            if payload["clusters"]:
                results.append(payload)
        return results

    def create_cluster_run(
        self,
        *,
        scope_mode: str,
        scope_key: str | None = None,
        threshold: float = 0.9,
        neighbor_limit: int = 10,
        ranker: str = "rrf",
        alpha: float | None = None,
        rrf_k: int = 60,
        candidate_multiplier: int = 5,
        provider: str = "openai",
        model: str = "text-embedding-3-large",
        category_filter: str | None = None,
        hierarchy_filter: str | None = None,
    ) -> dict[str, Any]:
        allowed_prompt_ids = self.scope_resolver.filter_prompt_ids(
            category_filter=category_filter,
            hierarchy_filter=hierarchy_filter,
            provider=provider,
            model=model,
        )
        clusters = self._compute_run_clusters(
            scope_mode=scope_mode,
            scope_key=scope_key,
            threshold=threshold,
            neighbor_limit=neighbor_limit,
            ranker=ranker,
            alpha=alpha,
            rrf_k=rrf_k,
            candidate_multiplier=candidate_multiplier,
            allowed_prompt_ids=allowed_prompt_ids,
            hierarchy_filter=hierarchy_filter,
            provider=provider,
            model=model,
        )

        run_document = {
            "run_id": uuid4().hex,
            "scope_mode": scope_mode,
            "scope_key": scope_key,
            "provider": provider,
            "model": model,
            "top_k": neighbor_limit,
            "threshold": threshold,
            "algorithm_version": ALGORITHM_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "category_filter": category_filter,
            "hierarchy_filter": hierarchy_filter,
            "cluster_count": len(clusters),
            "clusters": clusters,
        }
        self.repo.save_cluster_run(run=run_document)
        return run_document

    def get_cluster_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.repo.get_cluster_run(run_id)
        if run is None:
            return None
        run.setdefault("cluster_count", len(run.get("clusters", [])))
        return run

    def list_cluster_runs(self) -> list[dict[str, Any]]:
        return self.repo.list_cluster_runs()

    def get_cluster_run_detail(self, *, run_id: str, cluster_id: str) -> dict[str, Any] | None:
        run = self.repo.get_cluster_run(run_id)
        if run is None:
            return None
        return self.read_model_builder.get_cluster_from_run(run=run, cluster_id=cluster_id)

    def build_cluster_run_visualization(self, *, run_id: str) -> dict[str, Any] | None:
        run = self.repo.get_cluster_run(run_id)
        if run is None:
            return None
        return self.read_model_builder.build_run_visualization(run=run)

    def analyze_scope_clusters(
        self,
        *,
        prompt_id: str,
        threshold: float = 0.9,
        neighbor_limit: int = 10,
        ranker: str = "rrf",
        alpha: float | None = None,
        rrf_k: int = 60,
        candidate_multiplier: int = 5,
        provider: str = "openai",
        model: str = "text-embedding-3-large",
    ) -> dict[str, Any]:
        scopes = self.scope_resolver.scope_prompt_ids_for_prompt(
            prompt_id=prompt_id,
            provider=provider,
            model=model,
        )

        return {
            "prompt_id": prompt_id,
            "category": self._build_prompt_scope_slice(
                scope_type="category",
                scope_value=scopes["category"][0],
                prompt_ids=scopes["category"][1],
                threshold=threshold,
                neighbor_limit=neighbor_limit,
                ranker=ranker,
                alpha=alpha,
                rrf_k=rrf_k,
                candidate_multiplier=candidate_multiplier,
                provider=provider,
                model=model,
            ),
            "layer": self._build_prompt_scope_slice(
                scope_type="layer",
                scope_value=scopes["layer"][0],
                prompt_ids=scopes["layer"][1],
                threshold=threshold,
                neighbor_limit=neighbor_limit,
                ranker=ranker,
                alpha=alpha,
                rrf_k=rrf_k,
                candidate_multiplier=candidate_multiplier,
                provider=provider,
                model=model,
            ),
            "prompt_family": self._build_prompt_scope_slice(
                scope_type="prompt_family",
                scope_value=scopes["prompt_family"][0],
                prompt_ids=scopes["prompt_family"][1],
                threshold=threshold,
                neighbor_limit=neighbor_limit,
                ranker=ranker,
                alpha=alpha,
                rrf_k=rrf_k,
                candidate_multiplier=candidate_multiplier,
                provider=provider,
                model=model,
            ),
        }

    def drilldown_for_prompt(
        self,
        *,
        prompt_id: str,
        limit: int = 5,
        ranker: str = "rrf",
        alpha: float | None = None,
        rrf_k: int = 60,
        candidate_multiplier: int = 5,
        provider: str = "openai",
        model: str = "text-embedding-3-large",
    ) -> dict[str, Any]:
        prompt = self.repo.get_prompt(prompt_id)
        if not prompt:
            raise KeyError(f"Prompt not found: {prompt_id}")

        all_matches = self.similarity_service.find_similar_by_prompt_id(
            prompt_id,
            limit=max(limit * max(candidate_multiplier, 1), limit * 3),
            threshold=0.0,
            ranker=ranker,
            alpha=alpha,
            rrf_k=rrf_k,
            candidate_multiplier=candidate_multiplier,
            provider=provider,
            model=model,
        )

        same_layer = [match for match in all_matches if match["layer_path"] == prompt.layer_path][:limit]
        same_category = [match for match in all_matches if match["category"] == prompt.category][:limit]
        same_prompt_family = [match for match in all_matches if match["prompt_parent"] == prompt.prompt_parent][:limit]

        return {
            "prompt_id": prompt_id,
            "global": all_matches[:limit],
            "same_layer": same_layer,
            "same_category": same_category,
            "same_prompt_family": same_prompt_family,
        }

    def _compute_run_clusters(
        self,
        *,
        scope_mode: str,
        scope_key: str | None,
        threshold: float,
        neighbor_limit: int,
        ranker: str,
        alpha: float | None,
        rrf_k: int,
        candidate_multiplier: int,
        allowed_prompt_ids: set[str],
        hierarchy_filter: str | None,
        provider: str,
        model: str,
    ) -> list[dict[str, Any]]:
        if scope_mode == "global":
            return self._compute_duplicate_clusters(
                threshold=threshold,
                neighbor_limit=neighbor_limit,
                ranker=ranker,
                alpha=alpha,
                rrf_k=rrf_k,
                candidate_multiplier=candidate_multiplier,
                allowed_prompt_ids=allowed_prompt_ids,
                provider=provider,
                model=model,
                scope_mode=scope_mode,
                scope_key=scope_key,
            )

        grouped_prompt_ids = self.scope_resolver.group_prompt_ids_by_scope(
            scope_mode=scope_mode,
            allowed_prompt_ids=allowed_prompt_ids,
            hierarchy_filter=hierarchy_filter,
        )
        clusters: list[dict[str, Any]] = []
        for group_scope_key, prompt_ids in grouped_prompt_ids:
            clusters.extend(
                self._compute_duplicate_clusters(
                    threshold=threshold,
                    neighbor_limit=neighbor_limit,
                    ranker=ranker,
                    alpha=alpha,
                    rrf_k=rrf_k,
                    candidate_multiplier=candidate_multiplier,
                    allowed_prompt_ids=set(prompt_ids),
                    provider=provider,
                    model=model,
                    scope_mode=scope_mode,
                    scope_key=group_scope_key,
                )
            )
        return clusters

    def _build_prompt_scope_slice(
        self,
        *,
        scope_type: str,
        scope_value: str,
        prompt_ids: list[str],
        threshold: float,
        neighbor_limit: int,
        ranker: str,
        alpha: float | None,
        rrf_k: int,
        candidate_multiplier: int,
        provider: str,
        model: str,
    ) -> dict[str, Any]:
        clusters = self._compute_duplicate_clusters(
            threshold=threshold,
            neighbor_limit=neighbor_limit,
            ranker=ranker,
            alpha=alpha,
            rrf_k=rrf_k,
            candidate_multiplier=candidate_multiplier,
            allowed_prompt_ids=set(prompt_ids),
            provider=provider,
            model=model,
            scope_mode=scope_type,
            scope_key=scope_value,
        )
        return self.read_model_builder.build_scope_payload(
            scope_type=scope_type,
            scope_value=scope_value,
            prompt_ids=prompt_ids,
            clusters=clusters,
        )

    def _compute_duplicate_clusters(
        self,
        *,
        threshold: float,
        neighbor_limit: int,
        ranker: str,
        alpha: float | None,
        rrf_k: int,
        candidate_multiplier: int,
        allowed_prompt_ids: set[str] | None,
        provider: str,
        model: str,
        scope_mode: str = "global",
        scope_key: str | None = None,
    ) -> list[dict[str, Any]]:
        pairs = self.candidate_service.generate_pairs(
            threshold=threshold,
            neighbor_limit=neighbor_limit,
            ranker=ranker,
            alpha=alpha,
            rrf_k=rrf_k,
            candidate_multiplier=candidate_multiplier,
            allowed_prompt_ids=allowed_prompt_ids,
            provider=provider,
            model=model,
        )
        clustering = self.duplicate_clusterer.build_clusters(pairs=pairs, threshold=threshold)
        return [
            self.read_model_builder.build_cluster_payload(
                cluster_id=self._cluster_identifier(
                    scope_mode=scope_mode,
                    scope_key=scope_key,
                    index=index + 1,
                ),
                prompt_ids=prompt_ids,
                pairs=clustering.admitted_pairs,
                scope_mode=scope_mode,
                scope_key=scope_key,
            )
            for index, prompt_ids in enumerate(clustering.clusters)
        ]

    def _cluster_identifier(
        self,
        *,
        scope_mode: str,
        scope_key: str | None,
        index: int,
    ) -> str:
        if scope_mode == "global" or not scope_key:
            return f"{scope_mode}_cluster_{index}"

        scope_fragment = "".join(character if character.isalnum() else "_" for character in scope_key).strip("_")
        if not scope_fragment:
            scope_fragment = "scope"
        return f"{scope_mode}_{scope_fragment}_cluster_{index}"
