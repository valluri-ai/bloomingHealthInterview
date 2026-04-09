from app.schemas.prompt import PromptInput
from app.services.prompt_ingestion_service import PromptIngestionService
from tests.fakes import FakePromptRepository, FakePromptStore


def test_ingestion_persists_prompt_metadata_and_s3_version() -> None:
    repo = FakePromptRepository()
    store = FakePromptStore(version_id="3LgQx.example")
    service = PromptIngestionService(repo=repo, prompt_store=store)

    result = service.ingest_prompts(
        [
            PromptInput(
                prompt_id="survey.question.base",
                category="survey",
                layer="engine",
                name="Base Question Template",
                content="Ask naturally: {{question_text}}",
            )
        ]
    )

    assert result["loaded_count"] == 1
    assert result["stored_prompts"][0]["version_id"] == "3LgQx.example"

    saved = repo.get_prompt("survey.question.base")
    assert saved is not None
    assert saved.normalized_content == "Ask naturally: [VAR]"
    assert saved.input_variables == ("question_text",)
    assert saved.layer_path == "org.os.team.engine"
    assert saved.prompt_parent == "survey.question"
    assert saved.prompt_path_lineage == ("survey", "survey.question", "survey.question.base")
    assert saved.storage_bucket == "core-prompts-057286249135"
    assert saved.storage_key == "prompts/survey.question.base.json"
    assert saved.storage_version_id == "3LgQx.example"
    assert saved.storage_uri == "s3://core-prompts-057286249135/prompts/survey.question.base.json"
    assert saved.search_text.startswith("prompt_id: survey.question.base")


def test_ingestion_seeds_canonical_layer_taxonomy() -> None:
    repo = FakePromptRepository()
    store = FakePromptStore()
    service = PromptIngestionService(repo=repo, prompt_store=store)

    service.ingest_prompts(
        [
            PromptInput(
                prompt_id="verification.identity",
                category="verification",
                layer="engine",
                content="Verify identity with {{field_name}}",
            )
        ]
    )

    assert any(node.full_path == "org.os.team.engine.directive" for node in repo.saved_hierarchy_nodes)
    assert any(payload.prompt.prompt_id == "verification.identity" for payload in repo.saved_payloads)
