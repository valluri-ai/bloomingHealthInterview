from app.domain.models import PromptRecord
from app.services.merge_analysis_service import PromptMergeAnalysisService
from tests.fakes import FakePromptRepository, FakePromptStore


class RecordingRunner:
    def __init__(self) -> None:
        self.models: list[str] = []

    def analyze_cluster(self, cluster_payload, *, model: str):
        self.models.append(model)
        return {
            "can_merge": True,
            "confidence": 0.91,
            "canonical_prompt_id": cluster_payload["prompt_ids"][0],
            "merged_prompt_name": "Merged Prompt",
            "unified_prompt_template": "Unified content",
            "variables_to_parameterize": [],
            "differences_to_preserve": [],
            "reasoning": "Looks safe to merge.",
            "migration_steps": ["Replace references."],
        }


def _prompt(prompt_id: str) -> PromptRecord:
    return PromptRecord(
        prompt_id=prompt_id,
        category="verification",
        layer="engine",
        layer_path="org.os.team.engine",
        layer_lineage=("org", "org.os", "org.os.team", "org.os.team.engine"),
        name="Verification Prompt",
        content_preview="Verify identity with date of birth.",
        normalized_content="Verify identity with [VAR].",
        input_variables=("date_of_birth",),
        prompt_parent="verification",
        prompt_path_lineage=("verification", prompt_id),
        category_lineage=("verification",),
        embedding_text="prompt",
        search_text="prompt",
        storage_bucket="bucket",
        storage_key=f"prompts/{prompt_id}.json",
        storage_version_id="v1",
        storage_uri=f"s3://bucket/prompts/{prompt_id}.json",
        embedding=None,
    )


def test_merge_analysis_service_rejects_embedding_model_and_uses_safe_default() -> None:
    repo = FakePromptRepository()
    store = FakePromptStore()
    runner = RecordingRunner()
    prompt = _prompt("verification.identity")
    repo.prompts[prompt.prompt_id] = prompt
    store.documents[prompt.prompt_id] = {
        "prompt_id": prompt.prompt_id,
        "name": prompt.name,
        "content": "Verify the caller's identity with their date of birth.",
    }
    service = PromptMergeAnalysisService(
        repo=repo,
        prompt_store=store,
        runner=runner,
        default_model="openai:gpt-4o-mini",
    )

    result = service.analyze_clusters(
        clusters=[{"cluster_id": "cluster-1", "prompt_ids": [prompt.prompt_id]}],
        analysis_model="text-embedding-3-large",
    )

    assert result["results"][0]["error"] is None
    assert runner.models == ["openai:gpt-4o-mini"]


def test_merge_analysis_service_rejects_provider_prefixed_embedding_model_and_uses_safe_default() -> None:
    repo = FakePromptRepository()
    store = FakePromptStore()
    runner = RecordingRunner()
    prompt = _prompt("verification.identity")
    repo.prompts[prompt.prompt_id] = prompt
    store.documents[prompt.prompt_id] = {
        "prompt_id": prompt.prompt_id,
        "name": prompt.name,
        "content": "Verify the caller's identity with their date of birth.",
    }
    service = PromptMergeAnalysisService(
        repo=repo,
        prompt_store=store,
        runner=runner,
        default_model="openai:gpt-4o-mini",
    )

    result = service.analyze_clusters(
        clusters=[{"cluster_id": "cluster-1", "prompt_ids": [prompt.prompt_id]}],
        analysis_model="openai:text-embedding-3-large",
    )

    assert result["results"][0]["error"] is None
    assert runner.models == ["openai:gpt-4o-mini"]


def test_merge_analysis_service_uses_requested_chat_model_when_valid() -> None:
    repo = FakePromptRepository()
    store = FakePromptStore()
    runner = RecordingRunner()
    prompt = _prompt("verification.identity")
    repo.prompts[prompt.prompt_id] = prompt
    store.documents[prompt.prompt_id] = {
        "prompt_id": prompt.prompt_id,
        "name": prompt.name,
        "content": "Verify the caller's identity with their date of birth.",
    }
    service = PromptMergeAnalysisService(
        repo=repo,
        prompt_store=store,
        runner=runner,
        default_model="openai:gpt-4o-mini",
    )

    service.analyze_clusters(
        clusters=[{"cluster_id": "cluster-1", "prompt_ids": [prompt.prompt_id]}],
        analysis_model="openai:gpt-5.4-mini",
    )

    assert runner.models == ["openai:gpt-5.4-mini"]


def test_merge_analysis_service_rejects_codex_default_and_uses_safe_chat_default() -> None:
    repo = FakePromptRepository()
    store = FakePromptStore()
    runner = RecordingRunner()
    prompt = _prompt("verification.identity")
    repo.prompts[prompt.prompt_id] = prompt
    store.documents[prompt.prompt_id] = {
        "prompt_id": prompt.prompt_id,
        "name": prompt.name,
        "content": "Verify the caller's identity with their date of birth.",
    }
    service = PromptMergeAnalysisService(
        repo=repo,
        prompt_store=store,
        runner=runner,
        default_model="openai:gpt-5.3-codex",
    )

    result = service.analyze_clusters(
        clusters=[{"cluster_id": "cluster-1", "prompt_ids": [prompt.prompt_id]}],
    )

    assert result["results"][0]["error"] is None
    assert runner.models == ["openai:gpt-4o-mini"]
