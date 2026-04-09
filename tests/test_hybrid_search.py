from app.domain.models import PromptRecord
from app.services.similarity_service import SimilarityService
from tests.fakes import FakePromptRepository


def _prompt(
    prompt_id: str,
    *,
    category: str,
    normalized_content: str,
    embedding: list[float],
    prompt_parent: str,
) -> PromptRecord:
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
        prompt_parent=prompt_parent,
        prompt_path_lineage=tuple(".".join(parts[: index + 1]) for index in range(len(parts))),
        category_lineage=(category,),
        embedding_text=f"prompt_id: {prompt_id}\ncontent: {normalized_content}",
        search_text=f"prompt_id: {prompt_id}\ncontent: {normalized_content}",
        storage_bucket="core-prompts-057286249135",
        storage_key=f"prompts/{prompt_id}.json",
        storage_version_id="v1",
        storage_uri=f"s3://core-prompts-057286249135/prompts/{prompt_id}.json",
        embedding=embedding,
    )


def _match(
    prompt_id: str,
    *,
    category: str,
    similarity_score: float | None = None,
    fulltext_score: float | None = None,
) -> dict:
    return {
        "prompt_id": prompt_id,
        "content_preview": f"preview for {prompt_id}",
        "category": category,
        "layer_path": "org.os.team.engine",
        "prompt_parent": prompt_id.rsplit(".", 1)[0],
        "prompt_path_lineage": prompt_id.split("."),
        "layer_lineage": ["org", "org.os", "org.os.team", "org.os.team.engine"],
        "category_lineage": [category],
        "input_variables": [],
        "similarity_score": similarity_score,
        "fulltext_score": fulltext_score,
    }


def test_semantic_search_uses_rrf_and_respects_similarity_threshold() -> None:
    repo = FakePromptRepository()
    repo.prompts["common.error_recovery"] = _prompt(
        "common.error_recovery",
        category="common",
        normalized_content="If the user is confused, calmly recover and retry.",
        embedding=[1.0, 0.0],
        prompt_parent="common",
    )
    repo.prompts["common.error_handling"] = _prompt(
        "common.error_handling",
        category="common",
        normalized_content="Handle an error calmly and offer alternatives.",
        embedding=[0.9, 0.1],
        prompt_parent="common",
    )
    repo.prompts["receptionist.handoff"] = _prompt(
        "receptionist.handoff",
        category="receptionist",
        normalized_content="Explain the next step before handing the caller off.",
        embedding=[0.6, 0.4],
        prompt_parent="receptionist",
    )

    repo.vector_search_results[("how to handle user interruptions", tuple())] = [
        _match("common.error_recovery", category="common", similarity_score=0.94),
        _match("common.error_handling", category="common", similarity_score=0.90),
        _match("receptionist.handoff", category="receptionist", similarity_score=0.72),
    ]
    repo.fulltext_search_results[("how to handle user interruptions", tuple())] = [
        _match("common.error_recovery", category="common", fulltext_score=12.0),
        _match("receptionist.handoff", category="receptionist", fulltext_score=11.0),
    ]

    service = SimilarityService(repo)
    results = service.search_semantic(
        query="how to handle user interruptions",
        limit=2,
        threshold=0.8,
        ranker="rrf",
        rrf_k=20,
    )

    assert [row["prompt_id"] for row in results] == [
        "common.error_recovery",
        "common.error_handling",
    ]
    assert results[0]["ranking_score"] > results[1]["ranking_score"]
    assert results[0]["match_sources"] == ["fulltext", "vector"]
    assert repo.vector_search_calls[0]["node_label"] == "Prompt"
    assert repo.vector_search_calls[0]["embedding_node_property"] == "embedding_openai_text_embedding_3_large"
    assert repo.vector_search_calls[0]["embedding_dimension"] == 3072


def test_find_similar_by_prompt_id_excludes_self_and_reuses_prompt_embedding() -> None:
    repo = FakePromptRepository()
    repo.prompts["verification.dob"] = _prompt(
        "verification.dob",
        category="verification",
        normalized_content="Ask for the caller date of birth.",
        embedding=[1.0, 0.0],
        prompt_parent="verification",
    )

    repo.vector_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.dob", category="verification", similarity_score=1.0),
        _match("verification.identity", category="verification", similarity_score=0.98),
    ]
    repo.fulltext_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.identity", category="verification", fulltext_score=5.0),
        _match("verification.dob", category="verification", fulltext_score=4.5),
    ]

    service = SimilarityService(repo)
    results = service.find_similar_by_prompt_id(
        "verification.dob",
        limit=5,
        threshold=0.9,
        ranker="rrf",
    )

    assert [row["prompt_id"] for row in results] == ["verification.identity"]
    assert repo.vector_search_calls[0]["query_vector"] == [1.0, 0.0]
    assert repo.vector_search_calls[0]["node_label"] == "Prompt"
    assert repo.vector_search_calls[0]["embedding_node_property"] == "embedding_openai_text_embedding_3_large"
    assert repo.vector_search_calls[0]["embedding_dimension"] == 3072
