from app.domain.models import PromptRecord
from app.schemas.prompt import PromptInput
from app.services.merge_analysis_service import PromptMergeAnalysisService
from tests.fakes import FakePromptRepository, FakePromptStore


def _prompt(prompt_id: str, category: str, normalized_content: str) -> PromptRecord:
    parts = prompt_id.split(".")
    return PromptRecord(
        prompt_id=prompt_id,
        category=category,
        layer="engine",
        layer_path="org.os.team.engine",
        layer_lineage=("org", "org.os", "org.os.team", "org.os.team.engine"),
        name=prompt_id,
        content_preview=normalized_content[:160],
        normalized_content=normalized_content,
        input_variables=(),
        prompt_parent=".".join(parts[:-1]) or prompt_id,
        prompt_path_lineage=tuple(".".join(parts[: index + 1]) for index in range(len(parts))),
        category_lineage=(category,),
        embedding_text=f"prompt_id: {prompt_id}\ncontent: {normalized_content}",
        search_text=f"prompt_id: {prompt_id}\ncontent: {normalized_content}",
        storage_bucket="core-prompts-057286249135",
        storage_key=f"prompts/{prompt_id}.json",
        storage_version_id="v1",
        storage_uri=f"s3://core-prompts-057286249135/prompts/{prompt_id}.json",
        embedding=[0.1, 0.2, 0.3],
    )


class FakeMergeRunner:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def analyze_cluster(self, cluster_payload: dict, *, model: str) -> dict:
        self.calls.append(cluster_payload)
        return {
            "can_merge": True,
            "confidence": 0.94,
            "canonical_prompt_id": "verification.identity",
            "merged_prompt_name": "Unified Verification Prompt",
            "unified_prompt_template": "Verify identity using DOB with consistent confirmation.",
            "variables_to_parameterize": [],
            "differences_to_preserve": ["Keep flexible DOB parsing."],
            "reasoning": "Both prompts collect DOB for the same verification purpose.",
            "migration_steps": ["Route both IDs to the unified prompt."],
        }


def test_merge_analysis_enriches_clusters_with_prompt_documents_and_scope() -> None:
    repo = FakePromptRepository()
    store = FakePromptStore()
    runner = FakeMergeRunner()

    repo.prompts["verification.dob"] = _prompt(
        "verification.dob",
        category="verification",
        normalized_content="Ask for the caller date of birth.",
    )
    repo.prompts["verification.identity"] = _prompt(
        "verification.identity",
        category="verification",
        normalized_content="Verify the caller identity using date of birth.",
    )

    store.store_prompt(
        PromptInput(
            prompt_id="verification.dob",
            category="verification",
            layer="engine",
            name="DOB Verification",
            content="Ask for the caller's date of birth and confirm it.",
        )
    )
    store.store_prompt(
        PromptInput(
            prompt_id="verification.identity",
            category="verification",
            layer="engine",
            name="Identity Verification",
            content="Verify identity by collecting date of birth with flexible parsing.",
        )
    )

    service = PromptMergeAnalysisService(repo=repo, prompt_store=store, runner=runner)

    result = service.analyze_clusters(
        clusters=[{"cluster_id": "cluster_2", "prompt_ids": ["verification.dob", "verification.identity"]}],
        scope_hierarchy="engine",
        scope_category="verification",
    )

    assert result["scope"]["hierarchy"] == "engine"
    assert result["scope"]["category"] == "verification"
    assert result["results"][0]["cluster_id"] == "cluster_2"
    assert result["results"][0]["analysis"]["canonical_prompt_id"] == "verification.identity"
    assert runner.calls[0]["scope"]["hierarchy"] == "engine"
    assert runner.calls[0]["prompts"][0]["document"]["content"].startswith("Ask for the caller")
