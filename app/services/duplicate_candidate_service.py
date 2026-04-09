from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.repositories.prompt_repository import PromptGraphRepository
from app.services.embedding_service import EmbeddingService
from app.services.similarity_service import SimilarityService
from app.services.strict_duplicate_clusterer import SimilarityPair


class DuplicateCandidateService:
    def __init__(self, repo: PromptGraphRepository, similarity_service: SimilarityService) -> None:
        self.repo = repo
        self.similarity_service = similarity_service

    def generate_pairs(
        self,
        *,
        threshold: float,
        neighbor_limit: int,
        ranker: str,
        alpha: float | None,
        rrf_k: int,
        candidate_multiplier: int,
        allowed_prompt_ids: set[str] | None = None,
        provider: str = "openai",
        model: str = "text-embedding-3-large",
    ) -> dict[frozenset[str], SimilarityPair]:
        embedding_service = EmbeddingService(provider=provider, model=model)
        raw_candidates = self.repo.generate_similarity_candidates(
            prompt_ids=sorted(allowed_prompt_ids) if allowed_prompt_ids else None,
            top_k=neighbor_limit,
            similarity_cutoff=max(0.0, threshold * 0.75),
            embedding_property=embedding_service.embedding_property(),
        )
        if raw_candidates is None:
            raw_candidates = self._fallback_candidates(
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
        return self._pair_candidates(raw_candidates)

    def _fallback_candidates(
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
    ) -> list[dict[str, Any]]:
        embedding_service = EmbeddingService(provider=provider, model=model)
        candidates: list[dict[str, Any]] = []
        for prompt_id in self.repo.list_prompt_ids(
            requires_embedding=True,
            embedding_property=embedding_service.embedding_property(),
        ):
            if allowed_prompt_ids is not None and prompt_id not in allowed_prompt_ids:
                continue
            prompt = self.repo.get_prompt(prompt_id)
            if not prompt:
                continue
            matches = self.similarity_service.find_similar_by_prompt_id(
                prompt_id,
                limit=neighbor_limit,
                threshold=max(0.0, threshold * 0.75),
                ranker=ranker,
                alpha=alpha,
                rrf_k=rrf_k,
                candidate_multiplier=candidate_multiplier,
                provider=provider,
                model=model,
            )
            for rank, match in enumerate(matches, start=1):
                other_id = match["prompt_id"]
                if allowed_prompt_ids is not None and other_id not in allowed_prompt_ids:
                    continue
                candidates.append(
                    {
                        "source_prompt_id": prompt_id,
                        "target_prompt_id": other_id,
                        "similarity_score": float(match.get("similarity_score") or 0.0),
                        "rank": rank,
                    }
                )
        return candidates

    def _pair_candidates(self, raw_candidates: list[dict[str, Any]]) -> dict[frozenset[str], SimilarityPair]:
        directional: dict[tuple[str, str], dict[str, Any]] = {}
        for row in raw_candidates:
            source_prompt_id = row["source_prompt_id"]
            target_prompt_id = row["target_prompt_id"]
            if source_prompt_id == target_prompt_id:
                continue
            key = (source_prompt_id, target_prompt_id)
            score = float(row.get("similarity_score") or 0.0)
            current = directional.get(key)
            if current is None or score > float(current.get("similarity_score") or 0.0):
                directional[key] = row

        pairs: dict[frozenset[str], SimilarityPair] = {}
        for source_prompt_id, target_prompt_id in directional:
            pair_key = frozenset((source_prompt_id, target_prompt_id))
            if pair_key in pairs:
                continue

            prompt_a, prompt_b = sorted(pair_key)
            left = self.repo.get_prompt(prompt_a)
            right = self.repo.get_prompt(prompt_b)
            if not left or not right:
                continue

            forward = directional.get((prompt_a, prompt_b))
            reverse = directional.get((prompt_b, prompt_a))
            pairs[pair_key] = SimilarityPair(
                prompt_a=prompt_a,
                prompt_b=prompt_b,
                forward_score=float(forward["similarity_score"]) if forward else None,
                reverse_score=float(reverse["similarity_score"]) if reverse else None,
                forward_rank=int(forward["rank"]) if forward and forward.get("rank") is not None else None,
                reverse_rank=int(reverse["rank"]) if reverse and reverse.get("rank") is not None else None,
                shared_category=left.category == right.category,
                shared_prompt_family=left.prompt_parent == right.prompt_parent,
                shared_layer_lineage=bool(set(left.layer_lineage) & set(right.layer_lineage)),
                shared_variable_count=len(set(left.input_variables) & set(right.input_variables)),
                content_similarity=self._content_similarity(left.normalized_content, right.normalized_content),
                token_overlap=self._token_overlap(left.normalized_content, right.normalized_content),
            )
        return pairs

    def _content_similarity(self, left: str, right: str) -> float:
        if left == right:
            return 1.0
        return SequenceMatcher(a=left.lower(), b=right.lower()).ratio()

    def _token_overlap(self, left: str, right: str) -> float:
        left_tokens = set(re.findall(r"[a-z0-9]+", left.lower()))
        right_tokens = set(re.findall(r"[a-z0-9]+", right.lower()))
        if not left_tokens and not right_tokens:
            return 1.0
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
