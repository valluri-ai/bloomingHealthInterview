from __future__ import annotations

import os

from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings


class OpenAIEmbeddingService:
    _MODEL_DIMENSIONS = {
        "text-embedding-3-large": 3072,
        "text-embedding-3-small": 1536,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, api_key: str | None = None, model: str = "text-embedding-3-large") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

    @property
    def dimensions(self) -> int:
        return self._MODEL_DIMENSIONS.get(self.model, 3072)

    def provider_name(self) -> str:
        return "OpenAI"

    def provider_options(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return {
            "token": self.api_key,
            "model": self.model,
        }

    def build_graphrag_embedder(self) -> OpenAIEmbeddings:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return OpenAIEmbeddings(model=self.model, api_key=self.api_key)
