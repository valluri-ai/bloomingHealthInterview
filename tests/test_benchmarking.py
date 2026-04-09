from app.utils.benchmarking import (
    benchmark_dataset_from_payload,
    generate_benchmark_dataset,
    summarize_cluster_alignment,
    summarize_durations,
)


def test_generate_benchmark_dataset_builds_taxonomy_driven_profile() -> None:
    dataset = generate_benchmark_dataset(total_prompts=1000, seed=11)

    assert len(dataset.prompts) == 1000
    prompt_ids = [prompt.prompt_id for prompt in dataset.prompts]
    assert len(prompt_ids) == len(set(prompt_ids))
    assert dataset.metadata["profile"] == "taxonomy_balanced_v2"
    assert dataset.metadata["category_count"] == 20
    assert dataset.metadata["subcategories_per_category"] == 4
    assert dataset.metadata["family_count"] == 80

    categories = {prompt.prompt_id.split(".")[0] for prompt in dataset.prompts}
    families = {".".join(prompt.prompt_id.split(".")[:2]) for prompt in dataset.prompts}
    assert len(categories) == 20
    assert len(families) == 80


def test_generate_benchmark_dataset_seeds_250_similarity_prompts() -> None:
    dataset = generate_benchmark_dataset(total_prompts=1000, seed=7)
    duplicate_prompt_ids = {
        prompt_id
        for cluster in dataset.expected_duplicate_clusters
        for prompt_id in cluster.prompt_ids
    }

    assert dataset.metadata["seeded_similarity_prompt_count"] == 250
    assert len(dataset.expected_duplicate_clusters) == 50
    assert len(duplicate_prompt_ids) == 250
    for cluster in dataset.expected_duplicate_clusters:
        assert len(cluster.prompt_ids) == 5
        assert all(prompt_id.startswith(cluster.family_id) for prompt_id in cluster.prompt_ids)


def test_generate_benchmark_dataset_spreads_prompts_across_all_layers() -> None:
    dataset = generate_benchmark_dataset(total_prompts=1000, seed=9)

    assert {prompt.layer for prompt in dataset.prompts} == {"org", "os", "team", "engine", "directive"}


def test_benchmark_dataset_payload_round_trips() -> None:
    dataset = generate_benchmark_dataset(total_prompts=1000, seed=5)
    restored = benchmark_dataset_from_payload(dataset.to_payload())

    assert len(restored.prompts) == 1000
    assert restored.metadata == dataset.metadata
    assert restored.expected_duplicate_clusters == dataset.expected_duplicate_clusters
    assert restored.semantic_queries == dataset.semantic_queries


def test_summarize_cluster_alignment_penalizes_overmerged_clusters() -> None:
    summary = summarize_cluster_alignment(
        actual_clusters=[
            ("billing.refund.similar_1", "billing.refund.similar_2", "support.outage.similar_1"),
            ("support.outage.similar_2",),
        ],
        expected_clusters=[
            ("billing.refund.similar_1", "billing.refund.similar_2"),
            ("support.outage.similar_1", "support.outage.similar_2"),
        ],
    )

    assert summary["expected_cluster_count"] == 2
    assert summary["actual_cluster_count"] == 1
    assert summary["subset_cluster_recall"] == 0.5
    assert summary["exact_cluster_recall"] == 0.0
    assert summary["pairwise_precision"] == 0.333
    assert summary["pairwise_recall"] == 0.5
    assert summary["pairwise_f1"] == 0.4


def test_summarize_durations_reports_percentiles() -> None:
    summary = summarize_durations([10.0, 20.0, 30.0, 40.0, 50.0])

    assert summary["count"] == 5
    assert summary["min_ms"] == 10.0
    assert summary["avg_ms"] == 30.0
    assert summary["p50_ms"] == 30.0
    assert summary["p95_ms"] == 50.0
    assert summary["max_ms"] == 50.0
