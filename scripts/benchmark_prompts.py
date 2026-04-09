#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.prompt import PromptInput
from app.utils.benchmarking import (
    BenchmarkDataset,
    benchmark_dataset_from_payload,
    generate_benchmark_dataset,
    summarize_cluster_alignment,
    summarize_durations,
)


def inject_prefix(prompt_id: str, prefix: str) -> str:
    if not prefix:
        return prompt_id

    prefix_slug = prefix.replace(".", "_")
    parts = prompt_id.split(".")
    if len(parts) >= 2:
        return ".".join([parts[0], parts[1], prefix_slug, *parts[2:]])
    return f"{prefix_slug}.{prompt_id}"


def apply_prefix(dataset: BenchmarkDataset, prefix: str) -> BenchmarkDataset:
    if not prefix:
        return dataset

    id_map: dict[str, str] = {}
    prompts: list[PromptInput] = []
    for prompt in dataset.prompts:
        prompt_id = inject_prefix(prompt.prompt_id, prefix)
        id_map[prompt.prompt_id] = prompt_id
        prompts.append(
            PromptInput(
                prompt_id=prompt_id,
                category=prompt.category,
                layer=prompt.layer,
                name=prompt.name,
                content=prompt.content,
            )
        )

    return BenchmarkDataset(
        prompts=prompts,
        expected_duplicate_clusters=[
            cluster.__class__(
                family_id=inject_prefix(cluster.family_id, prefix),
                prompt_ids=tuple(id_map[prompt_id] for prompt_id in cluster.prompt_ids),
            )
            for cluster in dataset.expected_duplicate_clusters
        ],
        semantic_queries=[
            query.__class__(
                query=query.query,
                expected_prompt_ids=tuple(id_map[prompt_id] for prompt_id in query.expected_prompt_ids),
            )
            for query in dataset.semantic_queries
        ],
        metadata={**dataset.metadata, "prefix": prefix},
    )


def request_json(
    *,
    api_base_url: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{api_base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"{method} {path} failed: {error.reason}") from error


def timed_request(**kwargs: Any) -> tuple[Any, float]:
    started_at = time.perf_counter()
    response = request_json(**kwargs)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    return response, elapsed_ms


def count_search_hits(result_sets: list[list[dict[str, Any]]], expected_ids: list[tuple[str, ...]], *, top_k: int) -> float:
    if not result_sets:
        return 0.0
    hits = 0
    for results, expected in zip(result_sets, expected_ids, strict=False):
        returned_ids = [row.get("prompt_id") for row in results[:top_k]]
        if any(prompt_id in returned_ids for prompt_id in expected):
            hits += 1
    return hits / len(result_sets)


def extract_cluster_prompt_ids(clusters: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    return [
        tuple(prompt["prompt_id"] for prompt in cluster.get("prompts", []))
        for cluster in clusters
        if len(cluster.get("prompts", [])) > 1
    ]


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    if args.dataset_file:
        dataset_path = Path(args.dataset_file)
        dataset = benchmark_dataset_from_payload(json.loads(dataset_path.read_text(encoding="utf-8")))
        run_prefix = dataset.metadata.get("prefix", dataset_path.stem)
    else:
        run_prefix = args.prefix or f"benchmark.{args.count}.{int(time.time())}"
        dataset = apply_prefix(
            generate_benchmark_dataset(
                total_prompts=args.count,
                seed=args.seed,
                category_count=args.categories,
                subcategories_per_category=args.subcategories,
                seeded_similarity_prompt_count=args.similar_prompts,
            ),
            run_prefix,
        )
    prompt_count = len(dataset.prompts)

    prompts_before = request_json(api_base_url=args.api_base_url, path="/api/prompts")
    ingestion_response, ingestion_ms = timed_request(
        api_base_url=args.api_base_url,
        path="/api/prompts/load",
        method="POST",
        payload={"prompts": [prompt.model_dump() for prompt in dataset.prompts]},
    )
    embeddings_response, embeddings_ms = timed_request(
        api_base_url=args.api_base_url,
        path="/api/embeddings/generate",
        method="POST",
        payload={
            "prompt_ids": [prompt.prompt_id for prompt in dataset.prompts],
            "batch_size": args.batch_size,
            "provider": args.provider,
            "model": args.model,
        },
    )

    similar_latencies: list[float] = []
    similar_results: list[list[dict[str, Any]]] = []
    similar_expected: list[tuple[str, ...]] = []
    for cluster in dataset.expected_duplicate_clusters[: args.search_runs]:
        anchor_id = cluster.prompt_ids[0]
        expected_ids = tuple(prompt_id for prompt_id in cluster.prompt_ids[1:])
        query_string = urlencode(
            {
                "limit": args.similar_limit,
                "threshold": args.similar_threshold,
                "provider": args.provider,
                "model": args.model,
            }
        )
        result, elapsed_ms = timed_request(
            api_base_url=args.api_base_url,
            path=f"/api/prompts/{quote(anchor_id, safe='')}/similar?{query_string}",
        )
        similar_latencies.append(elapsed_ms)
        similar_results.append(result)
        similar_expected.append(expected_ids)

    semantic_latencies: list[float] = []
    semantic_results: list[list[dict[str, Any]]] = []
    semantic_expected: list[tuple[str, ...]] = []
    for query in dataset.semantic_queries[: args.search_runs]:
        result, elapsed_ms = timed_request(
            api_base_url=args.api_base_url,
            path="/api/search/semantic",
            method="POST",
            payload={
                "query": query.query,
                "limit": args.semantic_limit,
                "provider": args.provider,
                "model": args.model,
            },
        )
        semantic_latencies.append(elapsed_ms)
        semantic_results.append(result)
        semantic_expected.append(query.expected_prompt_ids)

    duplicate_query = urlencode(
        {
            "threshold": args.duplicate_threshold,
            "provider": args.provider,
            "model": args.model,
        }
    )
    duplicates_response, duplicates_ms = timed_request(
        api_base_url=args.api_base_url,
        path=f"/api/analysis/duplicates?{duplicate_query}",
    )
    prompts_after = request_json(api_base_url=args.api_base_url, path="/api/prompts")
    duplicate_alignment = summarize_cluster_alignment(
        actual_clusters=extract_cluster_prompt_ids(duplicates_response),
        expected_clusters=[cluster.prompt_ids for cluster in dataset.expected_duplicate_clusters],
    )

    return {
        "api_base_url": args.api_base_url,
        "provider": args.provider,
        "model": args.model,
        "batch_size": args.batch_size,
        "dataset": {
            "requested_prompt_count": args.count,
            "actual_prompt_count": prompt_count,
            "seed": args.seed,
            "prefix": run_prefix,
            "profile": dataset.metadata.get("profile"),
            "library_size_before": len(prompts_before),
            "library_size_after": len(prompts_after),
            "expected_duplicate_cluster_count": len(dataset.expected_duplicate_clusters),
            "semantic_query_count": len(dataset.semantic_queries[: args.search_runs]),
        },
        "ingestion": {
            "elapsed_ms": round(ingestion_ms, 2),
            "prompts_per_second": round(prompt_count / max(ingestion_ms / 1000, 0.001), 2),
            "loaded_count": ingestion_response["loaded_count"],
        },
        "embeddings": {
            "elapsed_ms": round(embeddings_ms, 2),
            "prompts_per_second": round(prompt_count / max(embeddings_ms / 1000, 0.001), 2),
            "generated_count": embeddings_response["generated_count"],
        },
        "similar_search": {
            "runs": len(similar_latencies),
            "latency_ms": summarize_durations(similar_latencies),
            "top1_hit_rate": round(count_search_hits(similar_results, similar_expected, top_k=1), 3),
            "top3_hit_rate": round(count_search_hits(similar_results, similar_expected, top_k=3), 3),
        },
        "semantic_search": {
            "runs": len(semantic_latencies),
            "latency_ms": summarize_durations(semantic_latencies),
            "top3_hit_rate": round(count_search_hits(semantic_results, semantic_expected, top_k=3), 3),
        },
        "duplicate_analysis": {
            "elapsed_ms": round(duplicates_ms, 2),
            "cluster_count": len(duplicates_response),
            "threshold": args.duplicate_threshold,
            **duplicate_alignment,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark prompt ingestion, embeddings, search, and clustering.")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001", help="FastAPI base URL.")
    parser.add_argument("--count", type=int, default=1000, help="Synthetic prompt count to benchmark.")
    parser.add_argument("--seed", type=int, default=7, help="Dataset seed.")
    parser.add_argument("--categories", type=int, default=20, help="Top-level category count.")
    parser.add_argument("--subcategories", type=int, default=4, help="Subcategories per category.")
    parser.add_argument("--similar-prompts", type=int, default=250, help="Seeded similar prompt count.")
    parser.add_argument("--prefix", default="", help="Optional prompt_id prefix. Generated automatically when omitted.")
    parser.add_argument("--dataset-file", default="", help="Optional generated dataset JSON file to benchmark directly.")
    parser.add_argument("--provider", default="openai", help="Embedding provider to benchmark.")
    parser.add_argument("--model", default="text-embedding-3-large", help="Embedding model to benchmark.")
    parser.add_argument("--batch-size", type=int, default=32, help="Embedding batch size.")
    parser.add_argument("--search-runs", type=int, default=8, help="How many similar/semantic searches to time.")
    parser.add_argument("--similar-limit", type=int, default=5, help="Limit for prompt similarity queries.")
    parser.add_argument("--similar-threshold", type=float, default=0.0, help="Threshold for prompt similarity queries.")
    parser.add_argument("--semantic-limit", type=int, default=5, help="Limit for semantic search queries.")
    parser.add_argument("--duplicate-threshold", type=float, default=0.9, help="Threshold for duplicate analysis.")
    parser.add_argument("--output", default="", help="Optional JSON report path.")
    args = parser.parse_args()

    report = run_benchmark(args)
    serialized = json.dumps(report, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized + "\n", encoding="utf-8")
        print(f"Wrote benchmark report to {output_path}")
        return

    print(serialized)


if __name__ == "__main__":
    main()
