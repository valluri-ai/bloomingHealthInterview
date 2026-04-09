from __future__ import annotations

import re
from typing import List

_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\.\-]+)\s*\}\}")


def extract_input_variables(text: str) -> List[str]:
    return list(dict.fromkeys(_VAR_PATTERN.findall(text or "")))


def normalize_prompt_content(text: str) -> str:
    return _VAR_PATTERN.sub("[VAR]", text or "").strip()


def build_embedding_text(*, prompt_id: str, name: str | None, category: str, layer_path: str, input_variables: list[str], normalized_content: str) -> str:
    parts = [
        f"prompt_id: {prompt_id}",
        f"name: {name or ''}".strip(),
        f"category: {category}",
        f"layer_path: {layer_path}",
        f"input_variables: {', '.join(input_variables)}" if input_variables else "input_variables: none",
        f"content: {normalized_content}",
    ]
    return "\n".join(parts)


def build_search_text(*, prompt_id: str, name: str | None, category: str, layer_path: str, normalized_content: str) -> str:
    parts = [
        f"prompt_id: {prompt_id}",
        f"name: {name or ''}".strip(),
        f"category: {category}",
        f"layer_path: {layer_path}",
        f"content: {normalized_content}",
    ]
    return "\n".join(part for part in parts if part)


def build_content_preview(text: str, limit: int = 160) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."
