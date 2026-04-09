# Prompt Intelligence UI Simplified MVP Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the complex graph-heavy UI with a simple four-tab operator interface for embeddings generation, prompt similarity, semantic search, and duplicate clusters, while adding prompt-list and model-scoped embedding support on the backend.

**Architecture:** Keep the FastAPI + Neo4j backend but extend it with prompt listing and model-scoped vector storage/index selection. Refactor the Next.js frontend into a single clear tabbed workflow, backed by typed API helpers and plain results lists instead of graph visualizations.

**Tech Stack:** FastAPI, Neo4j, S3, Next.js App Router, TypeScript, TanStack Query, pytest.

---

## Chunk 1: Backend Model-Scoped Embedding Support

### Task 1: Add failing backend tests for prompt listing and loopback model-scoped behavior

**Files:**
- Modify: `tests/test_api_routes.py`
- Modify: `tests/fakes.py`
- Modify: `tests/test_embedding_service.py`

- [ ] **Step 1: Write failing tests for `GET /api/prompts`**
- [ ] **Step 2: Write failing tests proving loopback/local prompt listing includes category/layer metadata**
- [ ] **Step 3: Write failing tests for model-scoped embedding naming helpers**
- [ ] **Step 4: Run targeted tests and verify failure**

Run: `pytest tests/test_api_routes.py tests/test_embedding_service.py -k "prompt_list or model_scoped" -v`
Expected: FAIL for missing route/helper behavior.

### Task 2: Implement prompt listing and model-scoped embedding helpers

**Files:**
- Modify: `app/services/embedding_service.py`
- Modify: `app/repositories/prompt_repository.py`
- Modify: `app/repositories/neo4j_prompt_repository.py`
- Modify: `tests/fakes.py`
- Test: `tests/test_api_routes.py`
- Test: `tests/test_embedding_service.py`

- [ ] **Step 1: Add helper methods for model-scoped property/index keys**
- [ ] **Step 2: Add repository support for listing prompt metadata**
- [ ] **Step 3: Add repository support for retrieving prompt embedding vectors for a specific model**
- [ ] **Step 4: Update embedding generation to store vectors in model-scoped properties and indexes**
- [ ] **Step 5: Run targeted tests and verify pass**

Run: `pytest tests/test_api_routes.py tests/test_embedding_service.py -k "prompt_list or model_scoped" -v`
Expected: PASS.

### Task 3: Extend required endpoints to accept optional model selection

**Files:**
- Modify: `app/schemas/prompt.py`
- Modify: `app/api/routes/prompts.py`
- Modify: `app/services/similarity_service.py`
- Modify: `app/services/analysis_service.py`
- Test: `tests/test_api_routes.py`
- Test: `tests/test_clustering.py`

- [ ] **Step 1: Add optional provider/model fields where needed**
- [ ] **Step 2: Thread provider/model through similar search, semantic search, and duplicate analysis**
- [ ] **Step 3: Keep backward compatibility with existing calls**
- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_api_routes.py tests/test_clustering.py -v`
Expected: PASS.

## Chunk 2: Simplified Next.js UI

### Task 4: Replace the graph dashboard with a four-tab workflow

**Files:**
- Modify: `web/app/page.tsx`
- Modify: `web/app/globals.css`
- Replace: `web/components/dashboard.tsx`
- Optionally leave unused graph components in place or remove imports

- [ ] **Step 1: Build the tab shell**
- [ ] **Step 2: Add tabs for embeddings, similar prompts, semantic search, and duplicate clusters**
- [ ] **Step 3: Remove the graph-first layout from the landing page**
- [ ] **Step 4: Run frontend build to catch layout/type issues**

Run: `cd web && npm run build`
Expected: PASS or fail only on missing new tab components.

### Task 5: Build the embeddings tab with prompt tree selection

**Files:**
- Modify: `web/lib/api.ts`
- Modify: `web/lib/types.ts`
- Create or modify: `web/components/dashboard.tsx`

- [ ] **Step 1: Add frontend prompt-list query support**
- [ ] **Step 2: Render a tree grouped by layer, then category, then prompts**
- [ ] **Step 3: Add checkbox selection with select-all/clear**
- [ ] **Step 4: Add provider/model/batch controls**
- [ ] **Step 5: Wire generate embeddings action and render results**
- [ ] **Step 6: Run frontend build**

Run: `cd web && npm run build`
Expected: PASS.

### Task 6: Build the similar prompts and semantic search tabs

**Files:**
- Modify: `web/components/dashboard.tsx`
- Modify: `web/lib/api.ts`
- Modify: `web/lib/types.ts`

- [ ] **Step 1: Add prompt picker for similar prompts**
- [ ] **Step 2: Add limit/threshold controls**
- [ ] **Step 3: Render simple result lists with required fields**
- [ ] **Step 4: Add semantic query form and result list**
- [ ] **Step 5: Run frontend build**

Run: `cd web && npm run build`
Expected: PASS.

### Task 7: Build duplicate cluster tab with simple scope filters

**Files:**
- Modify: `web/components/dashboard.tsx`
- Modify: `web/lib/api.ts`

- [ ] **Step 1: Add threshold and model controls**
- [ ] **Step 2: Render expandable cluster rows**
- [ ] **Step 3: Add category/layer filtering on returned cluster prompts**
- [ ] **Step 4: Run frontend build**

Run: `cd web && npm run build`
Expected: PASS.

## Chunk 3: Verification And Docs

### Task 8: Update docs and verify end to end

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the simplified four-tab UI**
- [ ] **Step 2: Document prompt list and model selection behavior**
- [ ] **Step 3: Run full backend tests**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 4: Run frontend production build**

Run: `cd web && npm run build`
Expected: PASS.

- [ ] **Step 5: Run live local verification**

Verify:
- prompt tree renders
- embeddings selection works
- similar prompts returns rows
- semantic search returns rows
- duplicate clusters render and filter
