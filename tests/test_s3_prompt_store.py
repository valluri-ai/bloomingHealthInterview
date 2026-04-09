import json

from app.repositories.s3_prompt_store import S3PromptStore
from app.schemas.prompt import PromptInput


class StubS3Client:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.documents: dict[str, dict] = {}
        self.exceptions = type("Exceptions", (), {"NoSuchKey": KeyError})

    def put_object(self, **kwargs):
        self.calls.append(kwargs)
        return {"VersionId": "3LgQx.aws", "ETag": '"etag-value"'}

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        key = kwargs["Key"]
        if key not in self.documents:
            raise self.exceptions.NoSuchKey(key)
        return {
            "Body": type(
                "Body",
                (),
                {"read": staticmethod(lambda: json.dumps(self.documents[key]).encode("utf-8"))},
            )()
        }


def test_store_prompt_writes_versioned_prompt_document_to_s3() -> None:
    client = StubS3Client()
    store = S3PromptStore(bucket="core-prompts-057286249135", client=client)

    stored = store.store_prompt(
        PromptInput(
            prompt_id="survey.question.base",
            category="survey",
            layer="engine",
            name="Base Question Template",
            content="Ask naturally: {{question_text}}",
        )
    )

    assert stored.version_id == "3LgQx.aws"
    assert client.calls[0]["Bucket"] == "core-prompts-057286249135"
    assert client.calls[0]["Key"] == "prompts/survey.question.base.json"
    body = json.loads(client.calls[0]["Body"].decode("utf-8"))
    assert body["prompt_id"] == "survey.question.base"
    assert body["content"] == "Ask naturally: {{question_text}}"


def test_store_prompt_for_tenant_writes_tenant_scoped_document_to_s3() -> None:
    client = StubS3Client()
    store = S3PromptStore(bucket="core-prompts-057286249135", client=client)

    stored = store.store_prompt_for_tenant(
        tenant_id="sample-prompts",
        prompt=PromptInput(
            prompt_id="survey.question.base",
            category="survey",
            layer="engine",
            name="Base Question Template",
            content="Ask naturally: {{question_text}}",
        ),
    )

    assert stored.version_id == "3LgQx.aws"
    assert client.calls[0]["Key"] == "prompts/tenants/sample-prompts/survey.question.base.json"


def test_get_prompt_by_storage_reads_known_s3_key() -> None:
    client = StubS3Client()
    client.documents["prompts/verification.identity.json"] = {
        "prompt_id": "verification.identity",
        "content": "Verify identity using {{date_of_birth}}",
    }
    store = S3PromptStore(bucket="core-prompts-057286249135", client=client)

    document = store.get_prompt_by_storage(
        key="prompts/verification.identity.json",
        bucket="core-prompts-057286249135",
        version_id="v123",
    )

    assert document["prompt_id"] == "verification.identity"
    assert client.calls[0]["Key"] == "prompts/verification.identity.json"


def test_get_prompt_for_tenant_reads_tenant_scoped_prompt_document() -> None:
    client = StubS3Client()
    client.documents["prompts/tenants/benchmark-1k/verification.identity.json"] = {
        "prompt_id": "verification.identity",
        "content": "Verify identity using {{date_of_birth}}",
    }
    store = S3PromptStore(bucket="core-prompts-057286249135", client=client)

    document = store.get_prompt_for_tenant("benchmark-1k", "verification.identity")

    assert document["prompt_id"] == "verification.identity"
    assert client.calls[0]["Key"] == "prompts/tenants/benchmark-1k/verification.identity.json"
