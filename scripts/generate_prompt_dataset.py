#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.prompt import PromptInput
from app.utils.benchmarking import BenchmarkDataset, generate_benchmark_dataset


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

    remapped_prompts: list[PromptInput] = []
    id_map: dict[str, str] = {}
    for prompt in dataset.prompts:
        new_prompt_id = inject_prefix(prompt.prompt_id, prefix)
        id_map[prompt.prompt_id] = new_prompt_id
        remapped_prompts.append(
            PromptInput(
                prompt_id=new_prompt_id,
                category=prompt.category,
                layer=prompt.layer,
                name=prompt.name,
                content=prompt.content,
            )
        )

    return BenchmarkDataset(
        prompts=remapped_prompts,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic prompt benchmark dataset.")
    parser.add_argument("--count", type=int, required=True, help="Number of prompts to generate.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for repeatable dataset generation.")
    parser.add_argument("--categories", type=int, default=20, help="Top-level category count.")
    parser.add_argument("--subcategories", type=int, default=4, help="Subcategories per category.")
    parser.add_argument("--similar-prompts", type=int, default=250, help="Number of seeded similar prompts.")
    parser.add_argument("--prefix", default="", help="Optional prompt_id prefix to avoid collisions.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to write the JSON payload. Prints to stdout when omitted.",
    )
    args = parser.parse_args()

    dataset = apply_prefix(
        generate_benchmark_dataset(
            total_prompts=args.count,
            seed=args.seed,
            category_count=args.categories,
            subcategories_per_category=args.subcategories,
            seeded_similarity_prompt_count=args.similar_prompts,
        ),
        args.prefix,
    )
    payload = dataset.to_payload()
    serialized = json.dumps(payload, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized + "\n", encoding="utf-8")
        print(f"Wrote dataset with {len(dataset.prompts)} prompts to {output_path}")
        return

    print(serialized)


if __name__ == "__main__":
    main()
