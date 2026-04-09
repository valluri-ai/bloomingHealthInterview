from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SimilarityPair:
    prompt_a: str
    prompt_b: str
    forward_score: float | None
    reverse_score: float | None
    forward_rank: int | None
    reverse_rank: int | None
    shared_category: bool
    shared_prompt_family: bool
    shared_layer_lineage: bool
    shared_variable_count: int

    @property
    def reciprocal(self) -> bool:
        return self.forward_score is not None and self.reverse_score is not None

    @property
    def best_score(self) -> float:
        return max(score for score in (self.forward_score, self.reverse_score) if score is not None)

    @property
    def average_score(self) -> float:
        scores = [score for score in (self.forward_score, self.reverse_score) if score is not None]
        return sum(scores) / len(scores)

    def as_payload(self) -> dict[str, Any]:
        return {
            "source": self.prompt_a,
            "target": self.prompt_b,
            "similarity_score": self.best_score,
            "ranking_score": self.average_score,
            "shared_category": self.shared_category,
            "shared_layer_path": self.shared_layer_lineage,
            "shared_prompt_path_parent": self.shared_prompt_family,
            "reciprocal": self.reciprocal,
            "shared_variable_count": self.shared_variable_count,
        }


@dataclass(frozen=True)
class ClusteringResult:
    clusters: list[list[str]]
    admitted_pairs: dict[frozenset[str], SimilarityPair]


class StrictDuplicateClusterer:
    def admit_pairs(
        self,
        *,
        pairs: dict[frozenset[str], SimilarityPair],
        threshold: float,
    ) -> dict[frozenset[str], SimilarityPair]:
        admitted: dict[frozenset[str], SimilarityPair] = {}
        average_floor = min(0.995, threshold + 0.02)
        same_category_floor = min(0.98, threshold + 0.01)
        cross_scope_floor = min(0.995, threshold + 0.05)

        for key, pair in pairs.items():
            if pair.best_score < threshold:
                continue

            if not pair.reciprocal:
                continue

            if pair.shared_prompt_family:
                admitted[key] = pair
                continue

            if pair.average_score < average_floor:
                continue

            minimum_score = same_category_floor if pair.shared_category else cross_scope_floor
            if pair.average_score < minimum_score:
                continue

            admitted[key] = pair
        return admitted

    def build_clusters(
        self,
        *,
        pairs: dict[frozenset[str], SimilarityPair],
        threshold: float,
    ) -> ClusteringResult:
        admitted_pairs = self.admit_pairs(pairs=pairs, threshold=threshold)
        sorted_pairs = sorted(
            admitted_pairs.values(),
            key=lambda pair: (-pair.average_score, -pair.best_score, pair.prompt_a, pair.prompt_b),
        )
        clusters: list[set[str]] = []

        for pair in sorted_pairs:
            left_index = self._find_cluster_index(clusters, pair.prompt_a)
            right_index = self._find_cluster_index(clusters, pair.prompt_b)

            if left_index is None and right_index is None:
                clusters.append({pair.prompt_a, pair.prompt_b})
                continue

            if left_index is not None and right_index is None:
                if self._can_join_cluster(clusters[left_index], pair.prompt_b, admitted_pairs):
                    clusters[left_index].add(pair.prompt_b)
                continue

            if left_index is None and right_index is not None:
                if self._can_join_cluster(clusters[right_index], pair.prompt_a, admitted_pairs):
                    clusters[right_index].add(pair.prompt_a)
                continue

            if left_index is None or right_index is None or left_index == right_index:
                continue

            left_cluster = clusters[left_index]
            right_cluster = clusters[right_index]
            if self._can_merge_clusters(left_cluster, right_cluster, admitted_pairs):
                merged = left_cluster | right_cluster
                for index in sorted((left_index, right_index), reverse=True):
                    clusters.pop(index)
                clusters.append(merged)

        normalized_clusters = sorted(
            [sorted(cluster) for cluster in clusters if len(cluster) > 1],
            key=lambda cluster: (-len(cluster), cluster),
        )
        return ClusteringResult(clusters=normalized_clusters, admitted_pairs=admitted_pairs)

    def _find_cluster_index(self, clusters: list[set[str]], prompt_id: str) -> int | None:
        for index, cluster in enumerate(clusters):
            if prompt_id in cluster:
                return index
        return None

    def _can_join_cluster(
        self,
        cluster: set[str],
        prompt_id: str,
        admitted_pairs: dict[frozenset[str], SimilarityPair],
    ) -> bool:
        return all(frozenset((member, prompt_id)) in admitted_pairs for member in cluster)

    def _can_merge_clusters(
        self,
        left: set[str],
        right: set[str],
        admitted_pairs: dict[frozenset[str], SimilarityPair],
    ) -> bool:
        return all(frozenset((left_member, right_member)) in admitted_pairs for left_member in left for right_member in right)
