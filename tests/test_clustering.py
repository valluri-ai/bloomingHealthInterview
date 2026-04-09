from app.domain.models import PromptRecord
from app.services.analysis_service import ClusterAnalysisService
from app.services.similarity_service import SimilarityService
from tests.fakes import FakePromptRepository


def _layer_path_for(layer: str) -> tuple[str, tuple[str, ...]]:
    if layer == "org":
        return "org", ("org",)
    if layer == "os":
        return "org.os", ("org", "org.os")
    if layer == "team":
        return "org.os.team", ("org", "org.os", "org.os.team")
    if layer == "directive":
        return (
            "org.os.team.engine.directive",
            ("org", "org.os", "org.os.team", "org.os.team.engine", "org.os.team.engine.directive"),
        )
    return "org.os.team.engine", ("org", "org.os", "org.os.team", "org.os.team.engine")


def _prompt(
    prompt_id: str,
    category: str,
    normalized_content: str,
    embedding: list[float],
    *,
    layer: str = "engine",
) -> PromptRecord:
    parts = prompt_id.split(".")
    layer_path, layer_lineage = _layer_path_for(layer)
    return PromptRecord(
        prompt_id=prompt_id,
        category=category,
        layer=layer,
        layer_path=layer_path,
        layer_lineage=layer_lineage,
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
        embedding=embedding,
    )


def _match(prompt_id: str, category: str, similarity_score: float, fulltext_score: float | None = None) -> dict:
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


def test_duplicate_cluster_analysis_groups_close_prompts() -> None:
    repo = FakePromptRepository()
    repo.prompts["verification.dob"] = _prompt(
        "verification.dob",
        category="verification",
        normalized_content="Ask for the caller date of birth.",
        embedding=[1.0, 0.0],
    )
    repo.prompts["verification.identity"] = _prompt(
        "verification.identity",
        category="verification",
        normalized_content="Verify the caller identity using date of birth.",
        embedding=[0.99, 0.01],
    )
    repo.prompts["common.error_recovery"] = _prompt(
        "common.error_recovery",
        category="common",
        normalized_content="If the user is confused, calmly recover and retry.",
        embedding=[0.1, 0.9],
    )

    repo.vector_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.dob", "verification", 1.0, 4.5),
        _match("verification.identity", "verification", 0.99, 4.2),
    ]
    repo.fulltext_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.identity", "verification", 0.99, 7.0),
        _match("verification.dob", "verification", 1.0, 6.5),
    ]
    repo.vector_search_results[("Verify the caller identity using date of birth.", tuple())] = [
        _match("verification.identity", "verification", 1.0, 4.8),
        _match("verification.dob", "verification", 0.99, 4.0),
    ]
    repo.fulltext_search_results[("Verify the caller identity using date of birth.", tuple())] = [
        _match("verification.identity", "verification", 1.0, 7.2),
        _match("verification.dob", "verification", 0.99, 6.7),
    ]
    repo.vector_search_results[("If the user is confused, calmly recover and retry.", tuple())] = [
        _match("common.error_recovery", "common", 1.0, 3.2),
    ]
    repo.fulltext_search_results[("If the user is confused, calmly recover and retry.", tuple())] = [
        _match("common.error_recovery", "common", 1.0, 6.0),
    ]

    similarity = SimilarityService(repo)
    analysis = ClusterAnalysisService(repo, similarity)

    clusters = analysis.analyze_duplicates(threshold=0.95, ranker="rrf")

    assert len(clusters) == 1
    assert {prompt["prompt_id"] for prompt in clusters[0]["prompts"]} == {
        "verification.dob",
        "verification.identity",
    }
    assert all("org.os" in prompt["layer_lineage"] for prompt in clusters[0]["prompts"])
    assert clusters[0]["merge_suggestion"]["canonical_prompt_id"] in {
        "verification.dob",
        "verification.identity",
    }
    assert clusters[0]["edges"][0]["shared_category"] is True


def test_duplicate_cluster_analysis_reclusters_after_category_filter() -> None:
    repo = FakePromptRepository()
    repo.prompts["verification.dob"] = _prompt(
        "verification.dob",
        category="verification",
        normalized_content="Ask for the caller date of birth.",
        embedding=[1.0, 0.0],
    )
    repo.prompts["verification.identity"] = _prompt(
        "verification.identity",
        category="verification",
        normalized_content="Verify the caller identity using date of birth.",
        embedding=[0.99, 0.01],
    )
    repo.prompts["common.error_recovery"] = _prompt(
        "common.error_recovery",
        category="common",
        normalized_content="If the user is confused, calmly recover and retry.",
        embedding=[0.1, 0.9],
    )
    repo.prompts["common.error_handling"] = _prompt(
        "common.error_handling",
        category="common",
        normalized_content="Handle errors calmly and offer a recovery path.",
        embedding=[0.11, 0.89],
    )

    repo.vector_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.dob", "verification", 1.0, 4.5),
        _match("verification.identity", "verification", 0.99, 4.2),
        _match("common.error_handling", "common", 0.97, 4.0),
    ]
    repo.fulltext_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.identity", "verification", 0.99, 7.0),
        _match("common.error_handling", "common", 0.97, 6.8),
        _match("verification.dob", "verification", 1.0, 6.5),
    ]
    repo.vector_search_results[("Verify the caller identity using date of birth.", tuple())] = [
        _match("verification.identity", "verification", 1.0, 4.8),
        _match("verification.dob", "verification", 0.99, 4.0),
        _match("common.error_handling", "common", 0.97, 3.9),
    ]
    repo.fulltext_search_results[("Verify the caller identity using date of birth.", tuple())] = [
        _match("verification.dob", "verification", 0.99, 6.7),
        _match("common.error_handling", "common", 0.97, 6.5),
        _match("verification.identity", "verification", 1.0, 7.2),
    ]
    repo.vector_search_results[("If the user is confused, calmly recover and retry.", tuple())] = [
        _match("common.error_recovery", "common", 1.0, 3.2),
        _match("common.error_handling", "common", 0.99, 3.1),
    ]
    repo.fulltext_search_results[("If the user is confused, calmly recover and retry.", tuple())] = [
        _match("common.error_handling", "common", 0.99, 6.0),
        _match("common.error_recovery", "common", 1.0, 6.2),
    ]
    repo.vector_search_results[("Handle errors calmly and offer a recovery path.", tuple())] = [
        _match("common.error_handling", "common", 1.0, 3.4),
        _match("common.error_recovery", "common", 0.99, 3.3),
        _match("verification.identity", "verification", 0.97, 3.0),
    ]
    repo.fulltext_search_results[("Handle errors calmly and offer a recovery path.", tuple())] = [
        _match("common.error_recovery", "common", 0.99, 6.1),
        _match("verification.identity", "verification", 0.97, 5.9),
        _match("common.error_handling", "common", 1.0, 6.3),
    ]

    similarity = SimilarityService(repo)
    analysis = ClusterAnalysisService(repo, similarity)

    global_clusters = analysis.analyze_duplicates(threshold=0.95, ranker="rrf")
    filtered_clusters = analysis.analyze_duplicates(
        threshold=0.95,
        ranker="rrf",
        category_filter="verification",
    )

    assert len(global_clusters) == 2
    assert {
        frozenset(prompt["prompt_id"] for prompt in cluster["prompts"])
        for cluster in global_clusters
    } == {
        frozenset({"verification.dob", "verification.identity"}),
        frozenset({"common.error_recovery", "common.error_handling"}),
    }
    assert len(filtered_clusters) == 1
    assert {prompt["prompt_id"] for prompt in filtered_clusters[0]["prompts"]} == {
        "verification.dob",
        "verification.identity",
    }


def test_duplicate_cluster_analysis_rejects_transitive_chaining() -> None:
    repo = FakePromptRepository()
    repo.prompts["claims.appeal.base"] = _prompt(
        "claims.appeal.base",
        category="claims",
        normalized_content="Handle claim appeal intake with appeal reason and claim number.",
        embedding=[1.0, 0.0],
    )
    repo.prompts["claims.status.base"] = _prompt(
        "claims.status.base",
        category="claims",
        normalized_content="Handle claim status intake with claim number and current claim status.",
        embedding=[0.96, 0.04],
    )
    repo.prompts["claims.documents.base"] = _prompt(
        "claims.documents.base",
        category="claims",
        normalized_content="Handle claim document collection with document type and claim number.",
        embedding=[0.92, 0.08],
    )

    repo.vector_search_results[("Handle claim appeal intake with appeal reason and claim number.", tuple())] = [
        _match("claims.appeal.base", "claims", 1.0, 5.0),
        _match("claims.status.base", "claims", 0.97, 4.7),
        _match("claims.documents.base", "claims", 0.91, 3.9),
    ]
    repo.fulltext_search_results[("Handle claim appeal intake with appeal reason and claim number.", tuple())] = [
        _match("claims.status.base", "claims", 0.97, 7.0),
        _match("claims.appeal.base", "claims", 1.0, 6.8),
        _match("claims.documents.base", "claims", 0.91, 5.3),
    ]
    repo.vector_search_results[("Handle claim status intake with claim number and current claim status.", tuple())] = [
        _match("claims.status.base", "claims", 1.0, 5.1),
        _match("claims.appeal.base", "claims", 0.97, 4.8),
        _match("claims.documents.base", "claims", 0.97, 4.8),
    ]
    repo.fulltext_search_results[("Handle claim status intake with claim number and current claim status.", tuple())] = [
        _match("claims.appeal.base", "claims", 0.97, 7.1),
        _match("claims.documents.base", "claims", 0.97, 7.0),
        _match("claims.status.base", "claims", 1.0, 6.9),
    ]
    repo.vector_search_results[("Handle claim document collection with document type and claim number.", tuple())] = [
        _match("claims.documents.base", "claims", 1.0, 5.0),
        _match("claims.status.base", "claims", 0.97, 4.7),
        _match("claims.appeal.base", "claims", 0.91, 3.8),
    ]
    repo.fulltext_search_results[("Handle claim document collection with document type and claim number.", tuple())] = [
        _match("claims.status.base", "claims", 0.97, 7.0),
        _match("claims.documents.base", "claims", 1.0, 6.8),
        _match("claims.appeal.base", "claims", 0.91, 5.2),
    ]

    similarity = SimilarityService(repo)
    analysis = ClusterAnalysisService(repo, similarity)

    clusters = analysis.analyze_duplicates(threshold=0.95, ranker="rrf")

    cluster_members = [sorted(prompt["prompt_id"] for prompt in cluster["prompts"]) for cluster in clusters]
    assert ["claims.appeal.base", "claims.documents.base", "claims.status.base"] not in cluster_members
    assert all(len(cluster) <= 2 for cluster in cluster_members)
    assert any(
        cluster == ["claims.appeal.base", "claims.status.base"]
        or cluster == ["claims.documents.base", "claims.status.base"]
        for cluster in cluster_members
    )


def test_duplicate_cluster_analysis_clusters_same_family_pairs_without_lexical_gates() -> None:
    repo = FakePromptRepository()
    repo.prompts["receptionist.workflow.alpha"] = _prompt(
        "receptionist.workflow.alpha",
        category="receptionist",
        normalized_content="Route the caller to billing and explain the transfer clearly.",
        embedding=[1.0, 0.0],
    )
    repo.prompts["receptionist.workflow.beta"] = _prompt(
        "receptionist.workflow.beta",
        category="receptionist",
        normalized_content="Collect a voicemail summary and callback number before ending the call.",
        embedding=[0.99, 0.01],
    )
    repo.prompts["verification.dob"] = _prompt(
        "verification.dob",
        category="verification",
        normalized_content="Ask for the caller date of birth.",
        embedding=[0.1, 0.9],
    )
    repo.prompts["verification.identity"] = _prompt(
        "verification.identity",
        category="verification",
        normalized_content="Verify the caller identity using date of birth.",
        embedding=[0.11, 0.89],
    )
    repo.generated_candidates = [
        {
            "source_prompt_id": "receptionist.workflow.alpha",
            "target_prompt_id": "receptionist.workflow.beta",
            "similarity_score": 0.96,
            "rank": 1,
            "shared_category": True,
            "shared_prompt_family": True,
            "shared_layer_lineage": True,
            "shared_variable_count": 0,
        },
        {
            "source_prompt_id": "receptionist.workflow.beta",
            "target_prompt_id": "receptionist.workflow.alpha",
            "similarity_score": 0.96,
            "rank": 1,
            "shared_category": True,
            "shared_prompt_family": True,
            "shared_layer_lineage": True,
            "shared_variable_count": 0,
        },
        {
            "source_prompt_id": "verification.dob",
            "target_prompt_id": "verification.identity",
            "similarity_score": 0.97,
            "rank": 1,
            "shared_category": True,
            "shared_prompt_family": True,
            "shared_layer_lineage": True,
            "shared_variable_count": 0,
        },
        {
            "source_prompt_id": "verification.identity",
            "target_prompt_id": "verification.dob",
            "similarity_score": 0.97,
            "rank": 1,
            "shared_category": True,
            "shared_prompt_family": True,
            "shared_layer_lineage": True,
            "shared_variable_count": 0,
        },
    ]

    similarity = SimilarityService(repo)
    analysis = ClusterAnalysisService(repo, similarity)

    clusters = analysis.analyze_duplicates(threshold=0.9, ranker="rrf")

    cluster_members = {frozenset(prompt["prompt_id"] for prompt in cluster["prompts"]) for cluster in clusters}
    assert frozenset({"verification.dob", "verification.identity"}) in cluster_members
    assert frozenset({"receptionist.workflow.alpha", "receptionist.workflow.beta"}) in cluster_members


def test_duplicate_cluster_analysis_clusters_same_family_pairs_at_threshold_floor() -> None:
    repo = FakePromptRepository()
    repo.prompts["common.error_recovery"] = _prompt(
        "common.error_recovery",
        category="common",
        normalized_content="If something goes wrong or the user seems confused, acknowledge the issue calmly.",
        embedding=[1.0, 0.0],
    )
    repo.prompts["common.error_handling"] = _prompt(
        "common.error_handling",
        category="common",
        normalized_content="When errors occur or confusion arises, remain calm and helpful.",
        embedding=[0.99, 0.01],
    )

    repo.generated_candidates = [
        {
            "source_prompt_id": "common.error_recovery",
            "target_prompt_id": "common.error_handling",
            "similarity_score": 0.9069,
            "rank": 1,
            "shared_category": True,
            "shared_prompt_family": True,
            "shared_layer_lineage": True,
            "shared_variable_count": 0,
        },
        {
            "source_prompt_id": "common.error_handling",
            "target_prompt_id": "common.error_recovery",
            "similarity_score": 0.9069,
            "rank": 1,
            "shared_category": True,
            "shared_prompt_family": True,
            "shared_layer_lineage": True,
            "shared_variable_count": 0,
        },
    ]

    similarity = SimilarityService(repo)
    analysis = ClusterAnalysisService(repo, similarity)

    clusters = analysis.analyze_duplicates(threshold=0.9, ranker="rrf")

    assert {
        frozenset(prompt["prompt_id"] for prompt in cluster["prompts"])
        for cluster in clusters
    } == {frozenset({"common.error_recovery", "common.error_handling"})}


def test_drilldown_groups_neighbors_by_layer_and_category() -> None:
    repo = FakePromptRepository()
    repo.prompts["verification.dob"] = _prompt(
        "verification.dob",
        category="verification",
        normalized_content="Ask for the caller date of birth.",
        embedding=[1.0, 0.0],
    )
    repo.prompts["verification.identity"] = _prompt(
        "verification.identity",
        category="verification",
        normalized_content="Verify the caller identity using date of birth.",
        embedding=[0.99, 0.01],
    )
    repo.prompts["common.error_recovery"] = _prompt(
        "common.error_recovery",
        category="common",
        normalized_content="If the user is confused, calmly recover and retry.",
        embedding=[0.1, 0.9],
    )

    repo.vector_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.dob", "verification", 1.0),
        _match("verification.identity", "verification", 0.98),
        _match("common.error_recovery", "common", 0.55),
    ]
    repo.fulltext_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.identity", "verification", 0.98, 6.0),
        _match("common.error_recovery", "common", 0.55, 2.0),
    ]

    similarity = SimilarityService(repo)
    analysis = ClusterAnalysisService(repo, similarity)

    result = analysis.drilldown_for_prompt(prompt_id="verification.dob", limit=5, ranker="rrf")

    assert result["same_layer"][0]["prompt_id"] == "verification.identity"
    assert result["same_category"][0]["prompt_id"] == "verification.identity"
    assert result["same_prompt_family"][0]["prompt_id"] == "verification.identity"


def test_scope_cluster_analysis_groups_by_category_layer_and_family() -> None:
    repo = FakePromptRepository()
    repo.prompts["verification.dob"] = _prompt(
        "verification.dob",
        category="verification",
        normalized_content="Ask for the caller date of birth.",
        embedding=[1.0, 0.0],
    )
    repo.prompts["verification.identity"] = _prompt(
        "verification.identity",
        category="verification",
        normalized_content="Verify the caller identity using date of birth.",
        embedding=[0.99, 0.01],
    )
    repo.prompts["common.error_recovery"] = _prompt(
        "common.error_recovery",
        category="common",
        normalized_content="If the user is confused, calmly recover and retry.",
        embedding=[0.1, 0.9],
    )

    repo.vector_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.dob", "verification", 1.0),
        _match("verification.identity", "verification", 0.98),
        _match("common.error_recovery", "common", 0.40),
    ]
    repo.fulltext_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.identity", "verification", 0.98, 6.0),
        _match("common.error_recovery", "common", 0.40, 1.0),
    ]
    repo.vector_search_results[("Verify the caller identity using date of birth.", tuple())] = [
        _match("verification.identity", "verification", 1.0),
        _match("verification.dob", "verification", 0.98),
        _match("common.error_recovery", "common", 0.35),
    ]
    repo.fulltext_search_results[("Verify the caller identity using date of birth.", tuple())] = [
        _match("verification.dob", "verification", 0.98, 6.1),
        _match("common.error_recovery", "common", 0.35, 0.9),
    ]
    repo.vector_search_results[("If the user is confused, calmly recover and retry.", tuple())] = [
        _match("common.error_recovery", "common", 1.0),
        _match("verification.identity", "verification", 0.35),
    ]
    repo.fulltext_search_results[("If the user is confused, calmly recover and retry.", tuple())] = [
        _match("verification.identity", "verification", 0.35, 0.7),
    ]

    similarity = SimilarityService(repo)
    analysis = ClusterAnalysisService(repo, similarity)

    result = analysis.analyze_scope_clusters(prompt_id="verification.dob", threshold=0.95, ranker="rrf")

    assert result["prompt_id"] == "verification.dob"
    assert result["category"]["scope_value"] == "verification"
    assert len(result["category"]["clusters"]) == 1
    assert {prompt["prompt_id"] for prompt in result["category"]["clusters"][0]["prompts"]} == {
        "verification.dob",
        "verification.identity",
    }
    assert len(result["prompt_family"]["clusters"]) == 1
    assert result["prompt_family"]["clusters"][0]["prompts"][0]["prompt_id"] in {
        "verification.dob",
        "verification.identity",
    }


def test_scoped_duplicate_reclustering_returns_independent_scope_groups() -> None:
    repo = FakePromptRepository()
    repo.prompts["verification.dob"] = _prompt(
        "verification.dob",
        category="verification",
        normalized_content="Ask for the caller date of birth.",
        embedding=[1.0, 0.0],
    )
    repo.prompts["verification.identity"] = _prompt(
        "verification.identity",
        category="verification",
        normalized_content="Verify the caller identity using date of birth.",
        embedding=[0.99, 0.01],
    )
    repo.prompts["common.error_recovery"] = _prompt(
        "common.error_recovery",
        category="common",
        normalized_content="If the user is confused, calmly recover and retry.",
        embedding=[0.1, 0.9],
    )
    repo.prompts["common.error_handling"] = _prompt(
        "common.error_handling",
        category="common",
        normalized_content="Handle errors calmly and offer a recovery path.",
        embedding=[0.11, 0.89],
    )
    repo.prompts["os.style.warm"] = _prompt(
        "os.style.warm",
        category="os",
        normalized_content="Maintain a warm and empathetic tone.",
        embedding=[0.5, 0.5],
        layer="os",
    )
    repo.prompts["os.style.empathetic"] = _prompt(
        "os.style.empathetic",
        category="os",
        normalized_content="Maintain an empathetic and supportive tone.",
        embedding=[0.49, 0.51],
        layer="os",
    )

    repo.vector_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.dob", "verification", 1.0),
        _match("verification.identity", "verification", 0.98),
    ]
    repo.fulltext_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.identity", "verification", 0.98, 6.0),
    ]
    repo.vector_search_results[("Verify the caller identity using date of birth.", tuple())] = [
        _match("verification.identity", "verification", 1.0),
        _match("verification.dob", "verification", 0.98),
    ]
    repo.fulltext_search_results[("Verify the caller identity using date of birth.", tuple())] = [
        _match("verification.dob", "verification", 0.98, 6.1),
    ]
    repo.vector_search_results[("If the user is confused, calmly recover and retry.", tuple())] = [
        _match("common.error_recovery", "common", 1.0),
        _match("common.error_handling", "common", 0.98),
    ]
    repo.fulltext_search_results[("If the user is confused, calmly recover and retry.", tuple())] = [
        _match("common.error_handling", "common", 0.98, 6.2),
    ]
    repo.vector_search_results[("Handle errors calmly and offer a recovery path.", tuple())] = [
        _match("common.error_handling", "common", 1.0),
        _match("common.error_recovery", "common", 0.98),
    ]
    repo.fulltext_search_results[("Handle errors calmly and offer a recovery path.", tuple())] = [
        _match("common.error_recovery", "common", 0.98, 6.3),
    ]
    repo.vector_search_results[("Maintain a warm and empathetic tone.", tuple())] = [
        _match("os.style.warm", "os", 1.0),
        _match("os.style.empathetic", "os", 0.98),
    ]
    repo.fulltext_search_results[("Maintain a warm and empathetic tone.", tuple())] = [
        _match("os.style.empathetic", "os", 0.98, 5.8),
    ]
    repo.vector_search_results[("Maintain an empathetic and supportive tone.", tuple())] = [
        _match("os.style.empathetic", "os", 1.0),
        _match("os.style.warm", "os", 0.98),
    ]
    repo.fulltext_search_results[("Maintain an empathetic and supportive tone.", tuple())] = [
        _match("os.style.warm", "os", 0.98, 5.7),
    ]

    similarity = SimilarityService(repo)
    analysis = ClusterAnalysisService(repo, similarity)

    category_groups = analysis.analyze_scoped_duplicates(
        scope_mode="category",
        threshold=0.95,
        ranker="rrf",
    )
    family_groups = analysis.analyze_scoped_duplicates(
        scope_mode="prompt_family",
        threshold=0.95,
        ranker="rrf",
    )
    hierarchy_groups = analysis.analyze_scoped_duplicates(
        scope_mode="hierarchy",
        threshold=0.95,
        ranker="rrf",
    )

    assert {group["scope_value"] for group in category_groups} == {"common", "os", "verification"}
    verification_group = next(group for group in category_groups if group["scope_value"] == "verification")
    assert {prompt["prompt_id"] for prompt in verification_group["clusters"][0]["prompts"]} == {
        "verification.dob",
        "verification.identity",
    }

    assert {group["scope_value"] for group in family_groups} == {"common", "os.style", "verification"}
    os_group = next(group for group in family_groups if group["scope_value"] == "os.style")
    assert {prompt["prompt_id"] for prompt in os_group["clusters"][0]["prompts"]} == {
        "os.style.warm",
        "os.style.empathetic",
    }

    assert {"engine", "os"}.issubset({group["scope_value"] for group in hierarchy_groups})
    engine_group = next(group for group in hierarchy_groups if group["scope_value"] == "engine")
    assert engine_group["prompt_count"] == 4
    assert len(engine_group["clusters"]) == 2


def test_scoped_cluster_run_uses_unique_cluster_ids_per_scope() -> None:
    repo = FakePromptRepository()
    repo.prompts["verification.dob"] = _prompt(
        "verification.dob",
        category="verification",
        normalized_content="Ask for the caller date of birth.",
        embedding=[1.0, 0.0],
    )
    repo.prompts["verification.identity"] = _prompt(
        "verification.identity",
        category="verification",
        normalized_content="Verify the caller identity using date of birth.",
        embedding=[0.99, 0.01],
    )
    repo.prompts["common.error_recovery"] = _prompt(
        "common.error_recovery",
        category="common",
        normalized_content="If the user is confused, calmly recover and retry.",
        embedding=[0.1, 0.9],
    )
    repo.prompts["common.error_handling"] = _prompt(
        "common.error_handling",
        category="common",
        normalized_content="Handle errors calmly and offer a recovery path.",
        embedding=[0.11, 0.89],
    )

    repo.vector_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.dob", "verification", 1.0),
        _match("verification.identity", "verification", 0.98),
    ]
    repo.fulltext_search_results[("Ask for the caller date of birth.", tuple())] = [
        _match("verification.identity", "verification", 0.98, 6.0),
    ]
    repo.vector_search_results[("Verify the caller identity using date of birth.", tuple())] = [
        _match("verification.identity", "verification", 1.0),
        _match("verification.dob", "verification", 0.98),
    ]
    repo.fulltext_search_results[("Verify the caller identity using date of birth.", tuple())] = [
        _match("verification.dob", "verification", 0.98, 6.1),
    ]
    repo.vector_search_results[("If the user is confused, calmly recover and retry.", tuple())] = [
        _match("common.error_recovery", "common", 1.0),
        _match("common.error_handling", "common", 0.98),
    ]
    repo.fulltext_search_results[("If the user is confused, calmly recover and retry.", tuple())] = [
        _match("common.error_handling", "common", 0.98, 6.2),
    ]
    repo.vector_search_results[("Handle errors calmly and offer a recovery path.", tuple())] = [
        _match("common.error_handling", "common", 1.0),
        _match("common.error_recovery", "common", 0.98),
    ]
    repo.fulltext_search_results[("Handle errors calmly and offer a recovery path.", tuple())] = [
        _match("common.error_recovery", "common", 0.98, 6.3),
    ]

    similarity = SimilarityService(repo)
    analysis = ClusterAnalysisService(repo, similarity)

    run = analysis.create_cluster_run(
        scope_mode="category",
        threshold=0.95,
        ranker="rrf",
    )

    cluster_ids = [cluster["cluster_id"] for cluster in run["clusters"]]
    assert len(cluster_ids) == len(set(cluster_ids))
    assert "category_common_cluster_1" in cluster_ids
    assert "category_verification_cluster_1" in cluster_ids
