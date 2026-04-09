# GDS Strict Cluster Runs Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace permissive duplicate clustering with a GDS-backed candidate pipeline, strict duplicate clustering semantics, and persisted cluster runs that the UI can inspect and filter without recomputing.

**Architecture:** Keep Neo4j vector search for interactive similarity endpoints, but move bulk duplicate candidate generation to Neo4j GDS KNN / Filtered KNN. Persist each cluster analysis run in Neo4j, then build strict duplicate clusters in Python from admitted candidate edges so duplicate mode is resistant to chaining while related mode can remain graph-oriented.

**Tech Stack:** FastAPI, Neo4j, Neo4j Graph Data Science, Neo4j vector indexes, Python service/repository layer, pytest, Next.js

---

## Chunk 1: Persisted Run Contract

### Task 1: Add failing tests for run persistence and strict duplicate semantics

**Files:**
- Modify: `tests/test_clustering.py`
- Modify: `tests/test_api_routes.py`
- Modify: `tests/fakes.py`

- [ ] **Step 1: Write a failing clustering test for the chaining case**
  - Create a fixture where `A-B` and `B-C` are admitted candidates but `A-C` is not.
  - Assert duplicate clustering returns two prompts per cluster at most instead of one transitive three-node cluster.
- [ ] **Step 2: Write failing tests for persisted cluster runs**
  - Add assertions that `POST /api/analysis/clusters/run` returns a saved run identifier and member clusters.
  - Add assertions that `GET /api/analysis/runs/{run_id}` returns the saved run without recomputing.
- [ ] **Step 3: Extend the fake repository to support candidate edges and stored runs**
  - Add in-memory hooks for candidate generation inputs, saved run payloads, and run lookups.
- [ ] **Step 4: Run targeted tests and verify they fail for the missing behavior**
  - Run: `pytest tests/test_clustering.py tests/test_api_routes.py -q`

### Task 2: Extend domain models, schemas, and repository interfaces for runs

**Files:**
- Modify: `app/domain/models.py`
- Modify: `app/schemas/prompt.py`
- Modify: `app/repositories/prompt_repository.py`

- [ ] **Step 1: Add domain records for candidate edges, cluster members, clusters, and cluster runs**
- [ ] **Step 2: Add API schemas for run creation, run lookup, and cluster mode selection**
- [ ] **Step 3: Extend repository protocols with methods for GDS candidate generation and run persistence**
- [ ] **Step 4: Re-run the targeted tests and confirm the failures moved to missing implementations**

## Chunk 2: GDS Candidate Generation and Strict Duplicate Clustering

### Task 3: Implement repository support for GDS candidate generation and stored runs

**Files:**
- Modify: `app/repositories/neo4j_prompt_repository.py`
- Modify: `tests/fakes.py`
- Test: `tests/test_neo4j_repository.py`

- [ ] **Step 1: Add a repository method to stream GDS KNN candidate edges**
  - Support:
    - global candidate generation
    - filtered candidate generation by category, hierarchy, or prompt family
  - Include structural metadata in returned rows.
- [ ] **Step 2: Add repository methods to persist and fetch cluster runs**
  - Save `ClusterRun`, `Cluster`, and `HAS_MEMBER` relationships.
  - Optionally save admitted candidate edge facts for debugging.
- [ ] **Step 3: Add repository tests for the Cypher contract and saved run lookups**
- [ ] **Step 4: Run repository-focused tests**
  - Run: `pytest tests/test_neo4j_repository.py -q`

### Task 4: Implement strict duplicate clustering and related cluster mode

**Files:**
- Create: `app/services/candidate_edge_generation_service.py`
- Create: `app/services/strict_duplicate_clusterer.py`
- Create: `app/services/cluster_run_service.py`
- Modify: `app/services/analysis_service.py`
- Modify: `app/api/dependencies.py`
- Test: `tests/test_clustering.py`

- [ ] **Step 1: Implement candidate edge generation service**
  - Resolve model-specific embedding property.
  - Request GDS candidates from the repository for the selected scope.
- [ ] **Step 2: Implement edge admission policy**
  - Enforce thresholding, reciprocal checks, and structural compatibility.
- [ ] **Step 3: Implement strict duplicate clustering**
  - Process admitted edges strongest-first.
  - Allow prompt-to-cluster or cluster-to-cluster merges only when all cross-pairs remain compatible.
- [ ] **Step 4: Keep a separate related-cluster path**
  - Preserve a looser graph-oriented mode for exploratory families.
- [ ] **Step 5: Integrate run persistence into the analysis service**
  - `GET /api/analysis/duplicates` can still return computed results.
  - `POST /api/analysis/clusters/run` saves a run.
  - `GET /api/analysis/runs/{run_id}` returns the saved run.
- [ ] **Step 6: Run clustering tests until green**
  - Run: `pytest tests/test_clustering.py tests/test_api_routes.py -q`

## Chunk 3: API and UI Integration

### Task 5: Expose run APIs and prompt-preview selection behavior

**Files:**
- Modify: `app/api/routes/prompts.py`
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`
- Modify: `web/components/dashboard.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Add cluster run endpoints**
  - `POST /api/analysis/clusters/run`
  - `GET /api/analysis/runs/{run_id}`
- [ ] **Step 2: Update the clusters UI to create and browse saved runs**
  - Show the active run header, run type, scope, model, and filters.
  - Render global duplicate vs related sections from the saved run payload.
- [ ] **Step 3: Add prompt click preview support everywhere prompts are listed**
  - Selecting a prompt in clusters or similarity results updates the preview iframe on the side.
- [ ] **Step 4: Keep existing filters as view filters over a saved run when possible**
- [ ] **Step 5: Build and typecheck the frontend**
  - Run: `cd web && npm run typecheck`
  - Run: `cd web && npm run build`

## Chunk 4: Benchmark and Verification

### Task 6: Re-run benchmark and verify clustering quality does not over-merge

**Files:**
- Modify: `scripts/benchmark_prompts.py` if needed
- Modify: `README.md`

- [ ] **Step 1: Run the targeted benchmark against the saved-run implementation**
  - Run: `python scripts/benchmark_prompts.py --api-base-url http://127.0.0.1:8001 --count 1000 --provider openai --model text-embedding-3-large --output tmp/benchmark-report-1000-strict.json`
- [ ] **Step 2: Compare new cluster counts and latency with the previous report**
- [ ] **Step 3: Document the algorithm split**
  - vector retrieval
  - GDS candidate generation
  - strict duplicate clustering
  - related clustering
  - saved run persistence
- [ ] **Step 4: Run full verification**
  - Run: `pytest -q`
  - Run: `python3 -m compileall app tests scripts`
  - Run: `cd web && npm run build`
