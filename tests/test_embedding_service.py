from __future__ import annotations

from dataclasses import dataclass

from app.services.embedding_service import EmbeddingService
from app.services.similarity_service import SimilarityService
from tests.fakes import FakePromptRepository


@dataclass
class FakeCredentials:
    access_key: str = "AKIATEST"
    secret_key: str = "secret"
    token: str | None = None


class FakeAwsSession:
    def get_credentials(self) -> FakeCredentials:
        return FakeCredentials()


class FakeBedrockBody:
    def read(self) -> bytes:
        return b'{"embedding":[0.1,0.2,0.3]}'


class FakeBedrockClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def invoke_model(self, **kwargs):
        self.calls.append(kwargs)
        return {"body": FakeBedrockBody()}


class FakeOpenAIEmbeddingsApi:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        inputs = kwargs["input"]
        if isinstance(inputs, str):
            vectors = [[0.1, 0.2, 0.3]]
        else:
            vectors = [[0.1, 0.2, 0.3] for _ in inputs]
        return type(
            "Response",
            (),
            {"data": [type("Datum", (), {"embedding": vector})() for vector in vectors]},
        )()


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.embeddings = FakeOpenAIEmbeddingsApi()


def test_bedrock_provider_options_use_aws_credentials() -> None:
    service = EmbeddingService(
        provider="bedrock",
        model="amazon.titan-embed-text-v1",
        aws_region="us-east-1",
        aws_session=FakeAwsSession(),
        bedrock_client=FakeBedrockClient(),
    )

    assert service.provider_name() == "Bedrock"
    assert service.dimensions == 1536
    assert service.provider_options() == {
        "accessKeyId": "AKIATEST",
        "secretAccessKey": "secret",
        "model": "amazon.titan-embed-text-v1",
        "region": "us-east-1",
    }


def test_bedrock_embed_query_uses_runtime_client() -> None:
    client = FakeBedrockClient()
    service = EmbeddingService(
        provider="bedrock",
        model="amazon.titan-embed-text-v1",
        aws_region="us-east-1",
        aws_session=FakeAwsSession(),
        bedrock_client=client,
    )

    vector = service.embed_query("handle user interruptions")

    assert vector == [0.1, 0.2, 0.3]
    assert client.calls[0]["modelId"] == "amazon.titan-embed-text-v1"


def test_openai_embed_texts_uses_single_batch_request() -> None:
    client = FakeOpenAIClient()
    service = EmbeddingService(
        provider="openai",
        model="text-embedding-3-large",
        api_key="test-key",
        openai_client=client,
    )

    vectors = service.embed_texts(["first prompt", "second prompt"])

    assert vectors == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert client.embeddings.calls == [
        {
            "model": "text-embedding-3-large",
            "input": ["first prompt", "second prompt"],
        }
    ]


def test_search_semantic_uses_supplied_query_vector() -> None:
    repo = FakePromptRepository()
    repo.vector_search_results[("how to handle user interruptions", tuple())] = []
    repo.fulltext_search_results[("how to handle user interruptions", tuple())] = []

    service = SimilarityService(repo)
    service.search_semantic(
        query="how to handle user interruptions",
        query_vector=[0.1, 0.2, 0.3],
        limit=5,
    )

    assert repo.vector_search_calls[0]["query_vector"] == [0.1, 0.2, 0.3]


def test_embedding_service_builds_model_scoped_keys() -> None:
    service = EmbeddingService(provider="openai", model="text-embedding-3-large")

    assert service.model_key() == "openai_text_embedding_3_large"
    assert service.embedding_property() == "embedding_openai_text_embedding_3_large"
    assert service.vector_index_name("prompt_embedding_index") == "prompt_embedding_index__openai_text_embedding_3_large"
