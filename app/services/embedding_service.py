from __future__ import annotations

import json
import os
from typing import Any

import boto3
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
from openai import OpenAI


class EmbeddingService:
    _DIMENSIONS = {
        ("openai", "text-embedding-3-large"): 3072,
        ("openai", "text-embedding-3-small"): 1536,
        ("openai", "text-embedding-ada-002"): 1536,
        ("bedrock", "amazon.titan-embed-text-v1"): 1536,
        ("bedrock", "amazon.titan-embed-text-v2:0"): 1024,
    }

    def __init__(
        self,
        *,
        provider: str = "openai",
        model: str = "text-embedding-3-large",
        api_key: str | None = None,
        aws_region: str | None = None,
        aws_session: Any | None = None,
        bedrock_client: Any | None = None,
        openai_client: Any | None = None,
    ) -> None:
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.aws_region = aws_region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
        self.aws_session = aws_session or boto3.Session()
        self._bedrock_client = bedrock_client
        self._openai_client = openai_client or (
            OpenAI(api_key=self.api_key) if self.provider == "openai" and self.api_key else None
        )

    @property
    def dimensions(self) -> int:
        return self._DIMENSIONS.get((self.provider, self.model), 3072)

    def model_label(self) -> str:
        return f"{self.provider}:{self.model}"

    def model_key(self) -> str:
        raw = f"{self.provider}_{self.model}".lower()
        return "".join(character if character.isalnum() else "_" for character in raw).strip("_")

    def embedding_property(self) -> str:
        return f"embedding_{self.model_key()}"

    def vector_index_name(self, base_index_name: str) -> str:
        return f"{base_index_name}__{self.model_key()}"

    def provider_name(self) -> str:
        if self.provider == "openai":
            return "OpenAI"
        if self.provider == "bedrock":
            return "Bedrock"
        raise ValueError(f"Unsupported embedding provider: {self.provider}")

    def provider_options(self) -> dict[str, str]:
        if self.provider == "openai":
            if not self.api_key:
                raise RuntimeError("OPENAI_API_KEY is not set")
            return {
                "token": self.api_key,
                "model": self.model,
            }

        if self.provider == "bedrock":
            credentials = self.aws_session.get_credentials()
            if not credentials:
                raise RuntimeError("AWS credentials are not available for Bedrock")
            frozen = credentials.get_frozen_credentials() if hasattr(credentials, "get_frozen_credentials") else credentials
            options = {
                "accessKeyId": frozen.access_key,
                "secretAccessKey": frozen.secret_key,
                "model": self.model,
                "region": self.aws_region,
            }
            if getattr(frozen, "token", None):
                options["sessionToken"] = frozen.token
            return options

        raise ValueError(f"Unsupported embedding provider: {self.provider}")

    def build_graphrag_embedder(self) -> OpenAIEmbeddings | None:
        if self.provider != "openai":
            return None
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return OpenAIEmbeddings(model=self.model, api_key=self.api_key)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if self.provider == "openai":
            if not self._openai_client:
                raise RuntimeError("OPENAI_API_KEY is not set")
            response = self._openai_client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [item.embedding for item in response.data]

        if self.provider == "bedrock":
            vectors: list[list[float]] = []
            client = self._get_bedrock_client()
            for text in texts:
                response = client.invoke_model(
                    modelId=self.model,
                    body=json.dumps({"inputText": text}),
                )
                body = json.loads(response["body"].read())
                vectors.append(body["embedding"])
            return vectors

        raise ValueError(f"Unsupported embedding provider: {self.provider}")

    def _get_bedrock_client(self) -> Any:
        if self._bedrock_client is None:
            self._bedrock_client = self.aws_session.client("bedrock-runtime", region_name=self.aws_region)
        return self._bedrock_client
