from __future__ import annotations

import json
import re
from typing import Any, Protocol

from app.repositories.prompt_repository import PromptGraphRepository, PromptTemplateStore

SAFE_MERGE_ANALYSIS_MODEL = "openai:gpt-4o-mini"


class MergeAnalysisRunner(Protocol):
    def analyze_cluster(self, cluster_payload: dict[str, Any], *, model: str) -> dict[str, Any]: ...


class DeepAgentMergeRunner:
    def __init__(self, *, default_model: str) -> None:
        self.default_model = default_model

    def analyze_cluster(self, cluster_payload: dict[str, Any], *, model: str) -> dict[str, Any]:
        from deepagents import create_deep_agent

        prompt_map = {prompt["prompt_id"]: prompt for prompt in cluster_payload["prompts"]}

        def read_prompt(prompt_id: str) -> dict[str, Any]:
            """Read one prompt from the active duplicate cluster by prompt_id."""
            if prompt_id not in prompt_map:
                raise ValueError(f"Prompt {prompt_id} is not in the active cluster")
            return prompt_map[prompt_id]

        def read_cluster_context() -> dict[str, Any]:
            """Read the active cluster context, including scope, edges, and prompt ids."""
            return {
                "cluster_id": cluster_payload["cluster_id"],
                "prompt_ids": cluster_payload["prompt_ids"],
                "scope": cluster_payload["scope"],
                "edges": cluster_payload["edges"],
            }

        system_prompt = """
You are a prompt merge analyst for a layered prompt library.

Your job is to decide whether the prompts in the active duplicate cluster should be merged into one canonical prompt.

Rules:
1. Call read_cluster_context() before you conclude.
2. Call read_prompt(prompt_id) for every prompt in the cluster.
3. Prefer one canonical prompt with parameterization when differences are minor.
4. Do not merge if behavior, policy, or intent materially differs.
5. Use the layer, category, family, variables, and prompt text as evidence.
6. Return ONLY valid JSON. No markdown fences. No prose outside the JSON object.

Return this exact shape:
{
  "can_merge": true,
  "confidence": 0.0,
  "canonical_prompt_id": "prompt.id",
  "merged_prompt_name": "Unified Prompt Name",
  "unified_prompt_template": "merged prompt text",
  "variables_to_parameterize": ["var_a"],
  "differences_to_preserve": ["important behavioral difference"],
  "reasoning": "short explanation",
  "migration_steps": ["step 1", "step 2"]
}
"""

        agent = create_deep_agent(
            model=model or self.default_model,
            tools=[read_prompt, read_cluster_context],
            system_prompt=system_prompt,
            name="prompt-merge-analyst",
        )

        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Analyze whether this duplicate cluster should be unified.\n"
                            f"Cluster id: {cluster_payload['cluster_id']}\n"
                            f"Prompt ids: {', '.join(cluster_payload['prompt_ids'])}\n"
                            f"Scope hierarchy: {cluster_payload['scope'].get('hierarchy') or 'all'}\n"
                            f"Scope category: {cluster_payload['scope'].get('category') or 'all'}\n"
                        ),
                    }
                ]
            }
        )
        content = self._extract_message_text(response)
        return self._parse_json(content)

    def _extract_message_text(self, response: Any) -> str:
        if isinstance(response, dict):
            messages = response.get("messages")
            if isinstance(messages, list) and messages:
                last_message = messages[-1]
                content = getattr(last_message, "content", None)
                if content is None and isinstance(last_message, dict):
                    content = last_message.get("content")
                return self._flatten_content(content)
            if "output" in response:
                return self._flatten_content(response["output"])
        return self._flatten_content(response)

    def _flatten_content(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if isinstance(item.get("text"), str):
                        parts.append(item["text"])
                    elif item.get("type") == "text" and isinstance(item.get("content"), str):
                        parts.append(item["content"])
                else:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part)
        return str(content)

    def _parse_json(self, text: str) -> dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                raise ValueError(f"Deep agent did not return JSON: {text}") from None
            return json.loads(match.group(0))


class PromptMergeAnalysisService:
    def __init__(
        self,
        *,
        repo: PromptGraphRepository,
        prompt_store: PromptTemplateStore,
        runner: MergeAnalysisRunner | None = None,
        default_model: str = SAFE_MERGE_ANALYSIS_MODEL,
    ) -> None:
        self.repo = repo
        self.prompt_store = prompt_store
        self.default_model = default_model
        self.runner = runner or DeepAgentMergeRunner(default_model=default_model)

    def analyze_clusters(
        self,
        *,
        clusters: list[dict[str, Any]],
        scope_hierarchy: str | None = None,
        scope_category: str | None = None,
        analysis_model: str | None = None,
    ) -> dict[str, Any]:
        scope = {
            "hierarchy": scope_hierarchy,
            "category": scope_category,
        }
        results = []

        for cluster in clusters:
            cluster_payload = self._build_cluster_payload(cluster=cluster, scope=scope)
            try:
                resolved_model = self._resolve_analysis_model(analysis_model)
                analysis = self.runner.analyze_cluster(
                    cluster_payload,
                    model=resolved_model,
                )
                results.append(
                    {
                        "cluster_id": cluster_payload["cluster_id"],
                        "prompt_ids": cluster_payload["prompt_ids"],
                        "analysis": analysis,
                        "error": None,
                    }
                )
            except Exception as exc:  # pragma: no cover - exercised in live runs
                results.append(
                    {
                        "cluster_id": cluster_payload["cluster_id"],
                        "prompt_ids": cluster_payload["prompt_ids"],
                        "analysis": None,
                        "error": str(exc),
                    }
                )

        return {
            "scope": scope,
            "results": results,
        }

    def _resolve_analysis_model(self, requested_model: str | None) -> str:
        safe_default = (self.default_model or SAFE_MERGE_ANALYSIS_MODEL).strip()
        if self._requires_non_chat_endpoint(safe_default):
            safe_default = SAFE_MERGE_ANALYSIS_MODEL
        candidate = (requested_model or safe_default).strip()
        if self._requires_non_chat_endpoint(candidate):
            return safe_default
        return candidate

    def _requires_non_chat_endpoint(self, model_name: str) -> bool:
        normalized = model_name.split(":", 1)[-1].lower()
        return "embedding" in normalized or "codex" in normalized

    def _build_cluster_payload(
        self,
        *,
        cluster: dict[str, Any],
        scope: dict[str, str | None],
    ) -> dict[str, Any]:
        prompt_ids = cluster["prompt_ids"]
        prompts = [self._build_prompt_payload(prompt_id) for prompt_id in prompt_ids]
        edges = self._build_edges(prompts)
        return {
            "cluster_id": cluster["cluster_id"],
            "prompt_ids": prompt_ids,
            "scope": scope,
            "prompts": prompts,
            "edges": edges,
        }

    def _build_prompt_payload(self, prompt_id: str) -> dict[str, Any]:
        prompt = self.repo.get_prompt(prompt_id)
        if prompt is None:
            raise KeyError(f"Prompt not found: {prompt_id}")
        document = self.prompt_store.get_prompt(prompt_id)
        if document is None:
            raise KeyError(f"Prompt document not found: {prompt_id}")
        return {
            "prompt_id": prompt.prompt_id,
            "name": prompt.name,
            "category": prompt.category,
            "layer": prompt.layer,
            "layer_path": prompt.layer_path,
            "layer_lineage": list(prompt.layer_lineage),
            "prompt_parent": prompt.prompt_parent,
            "prompt_path_lineage": list(prompt.prompt_path_lineage),
            "category_lineage": list(prompt.category_lineage),
            "normalized_content": prompt.normalized_content,
            "content_preview": prompt.content_preview,
            "input_variables": list(prompt.input_variables),
            "document": document,
        }

    def _build_edges(self, prompts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        for index, prompt in enumerate(prompts):
            for other in prompts[index + 1 :]:
                shared_layer_path = prompt["layer_path"] == other["layer_path"]
                shared_category = prompt["category"] == other["category"]
                shared_prompt_path_parent = prompt["prompt_parent"] == other["prompt_parent"]
                shared_variables = sorted(
                    set(prompt["input_variables"]).intersection(other["input_variables"])
                )
                edges.append(
                    {
                        "source": prompt["prompt_id"],
                        "target": other["prompt_id"],
                        "shared_layer_path": shared_layer_path,
                        "shared_category": shared_category,
                        "shared_prompt_path_parent": shared_prompt_path_parent,
                        "shared_variables": shared_variables,
                    }
                )
        return edges
