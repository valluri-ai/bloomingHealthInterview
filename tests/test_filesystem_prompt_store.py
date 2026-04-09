import json

from app.repositories.filesystem_prompt_store import FilesystemPromptStore
from app.schemas.prompt import PromptInput


def test_store_prompt_writes_prompt_document_to_local_filesystem(tmp_path) -> None:
    store = FilesystemPromptStore(root=str(tmp_path))

    stored = store.store_prompt(
        PromptInput(
            prompt_id="survey.question.base",
            category="survey",
            layer="engine",
            name="Base Question Template",
            content="Ask naturally: {{question_text}}",
        )
    )

    assert stored.bucket == "local"
    assert stored.key == "prompts/survey.question.base.json"
    path = tmp_path / stored.key
    assert path.exists()
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["prompt_id"] == "survey.question.base"
    assert stored.s3_uri.startswith("file://")


def test_store_prompt_for_tenant_writes_tenant_scoped_document_to_local_filesystem(tmp_path) -> None:
    store = FilesystemPromptStore(root=str(tmp_path))

    stored = store.store_prompt_for_tenant(
        tenant_id="sample-prompts",
        prompt=PromptInput(
            prompt_id="verification.identity",
            category="verification",
            layer="engine",
            content="Verify identity using {{date_of_birth}}",
        ),
    )

    assert stored.key == "prompts/tenants/sample-prompts/verification.identity.json"
    document = json.loads((tmp_path / stored.key).read_text(encoding="utf-8"))
    assert document["prompt_id"] == "verification.identity"


def test_get_prompt_by_storage_reads_local_document(tmp_path) -> None:
    store = FilesystemPromptStore(root=str(tmp_path))
    target = tmp_path / "prompts/verification.identity.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "prompt_id": "verification.identity",
                "content": "Verify identity using {{date_of_birth}}",
            }
        ),
        encoding="utf-8",
    )

    document = store.get_prompt_by_storage(key="prompts/verification.identity.json", bucket="local")

    assert document == {
        "prompt_id": "verification.identity",
        "content": "Verify identity using {{date_of_birth}}",
    }
