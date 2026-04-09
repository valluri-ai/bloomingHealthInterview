# Prompt Intelligence Service Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the in-memory prompt similarity scaffold with a Neo4j + S3 prompt intelligence service that supports versioned prompt storage, OpenAI-backed embedding generation through Neo4j GenAI batching, hybrid semantic retrieval, lineage-aware analysis, and duplicate clustering.

**Architecture:** Prompt content is stored as versioned objects in S3 and prompt metadata is modeled in Neo4j as `Prompt`, `HierarchyNode`, and `InputVariable` nodes. FastAPI routes call services that normalize templates, persist graph structure, request embeddings in batches, run hybrid retrieval across Neo4j vector/full-text indexes, and compute duplicate clusters plus merge suggestions in the application layer.

**Tech Stack:** FastAPI, Neo4j, neo4j-graphrag, OpenAI embeddings, boto3, pytest

---

## Chunk 1: Test Coverage and Contracts

### Task 1: Replace in-memory test assumptions

**Files:**
- Modify: `tests/test_ingestion.py`
- Modify: `tests/test_clustering.py`
- Create: `tests/test_hybrid_search.py`
- Create: `tests/fakes.py`

- [ ] **Step 1: Write failing tests for normalized prompt ingestion and S3 version metadata**

```python
def test_ingestion_persists_prompt_metadata_and_s3_version():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingestion.py -v`
Expected: FAIL because the current repository/service interfaces are still in-memory only.

- [ ] **Step 3: Write failing tests for hybrid retrieval and duplicate clustering**

```python
def test_semantic_search_uses_hybrid_rrf_results():
    ...
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_hybrid_search.py tests/test_clustering.py -v`
Expected: FAIL because the current similarity layer does not support Neo4j hybrid retrieval or S3-backed prompts.

## Chunk 2: Repository and Service Rewrite

### Task 2: Add infrastructure adapters and service contracts

**Files:**
- Create: `app/core/config.py`
- Create: `app/domain/models.py`
- Create: `app/repositories/prompt_repository.py`
- Create: `app/repositories/s3_prompt_store.py`
- Modify: `app/repositories/neo4j_prompt_repository.py`
- Modify: `app/services/hierarchy_service.py`
- Modify: `app/services/prompt_ingestion_service.py`
- Modify: `app/services/openai_embedding_service.py`
- Modify: `app/services/similarity_service.py`
- Modify: `app/services/analysis_service.py`

- [ ] **Step 1: Implement repository contracts and prompt graph models**

```python
@dataclass
class PromptRecord:
    prompt_id: str
    ...
```

- [ ] **Step 2: Run focused tests**

Run: `pytest tests/test_ingestion.py tests/test_hybrid_search.py -v`
Expected: PASS for rewritten unit tests covering the new contracts.

- [ ] **Step 3: Implement S3 versioned prompt storage and Neo4j graph upserts**

```python
class S3PromptStore:
    def put_prompt(...): ...
```

- [ ] **Step 4: Implement hybrid retrieval with reciprocal-rank fusion and lineage enrichment**

```python
class SimilarityService:
    def semantic_search(...): ...
```

- [ ] **Step 5: Run focused tests again**

Run: `pytest tests/test_ingestion.py tests/test_hybrid_search.py tests/test_clustering.py -v`
Expected: PASS

## Chunk 3: API Wiring and Documentation

### Task 3: Rewire FastAPI to the new backend

**Files:**
- Modify: `app/api/routes/prompts.py`
- Create: `app/api/dependencies.py`
- Modify: `app/main.py`
- Modify: `app/schemas/prompt.py`
- Modify: `README.md`
- Modify: `requirements.txt`

- [ ] **Step 1: Write/update failing API-level tests if needed**

```python
def test_route_dependency_uses_neo4j_stack():
    ...
```

- [ ] **Step 2: Implement dependency injection for Neo4j, S3, and embedders**

```python
def get_prompt_services():
    ...
```

- [ ] **Step 3: Document setup for `.env`, AWS profile, Neo4j indexes, and hybrid ranking modes**

```markdown
PROMPT_S3_BUCKET=...
NEO4J_URI=...
```

- [ ] **Step 4: Run the full verification suite**

Run: `pytest -q`
Expected: PASS
