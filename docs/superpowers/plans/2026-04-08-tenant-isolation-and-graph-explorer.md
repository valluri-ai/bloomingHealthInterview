# Tenant Isolation And Graph Explorer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tenant-scoped prompt storage, search, clustering, and graph exploration with one active tenant selected in the UI.

**Architecture:** Keep tenant enforcement in the data-access layer by introducing tenant-scoped repository and prompt-store wrappers over the shared Neo4j and S3 backends. Shared layer hierarchy stays global, while prompt-owned nodes and reads/writes become tenant-local; the UI sends `X-Tenant-Id` on every prompt-scoped request and reloads data when the active tenant changes.

**Tech Stack:** FastAPI, Neo4j, S3, React, Next.js, TanStack Query, Cytoscape

---

## Chunk 1: Tenant-Scoped Backend Contracts

### Task 1: Add failing tests for tenant requirements

**Files:**
- Modify: `tests/test_api_routes.py`
- Modify: `tests/test_ingestion.py`
- Modify: `tests/test_s3_prompt_store.py`
- Modify: `tests/test_neo4j_repository.py`

- [ ] Add route tests for missing `X-Tenant-Id`, tenant list/create endpoints, and graph explorer contract
- [ ] Add storage test for tenant-scoped S3 keys
- [ ] Add ingestion/repository tests for tenant-scoped prompt persistence
- [ ] Run the focused tests and confirm they fail for the expected missing-tenant behavior

### Task 2: Add tenant domain and wrapper boundaries

**Files:**
- Modify: `app/domain/models.py`
- Modify: `app/repositories/prompt_repository.py`
- Create: `app/repositories/tenant_scoped_prompt_repository.py`
- Create: `app/repositories/tenant_scoped_prompt_store.py`

- [ ] Add tenant records/context models
- [ ] Add tenant admin protocol methods and graph explorer response protocol method
- [ ] Add tenant-scoped wrapper implementations that preserve the existing prompt-scoped interface
- [ ] Keep service-layer call sites tenant-agnostic

### Task 3: Implement tenant-aware Neo4j and S3 access

**Files:**
- Modify: `app/repositories/neo4j_prompt_repository.py`
- Modify: `app/repositories/s3_prompt_store.py`

- [ ] Add tenant nodes, constraints, and tenant-aware read/write/query methods
- [ ] Keep layer hierarchy global while categories, prompt paths, input variables, prompts, and cluster runs are tenant-local
- [ ] Add tenant-scoped graph explorer query support
- [ ] Add tenant-scoped S3 document paths under `tenants/{tenant_id}/prompts/...`

## Chunk 2: FastAPI Tenant Wiring And Seeding

### Task 4: Add tenant dependencies and services

**Files:**
- Modify: `app/api/dependencies.py`
- Create: `app/services/tenant_service.py`
- Create: `app/data/sample_prompts.py`
- Modify: `app/core/config.py`
- Modify: `app/main.py`

- [ ] Resolve active tenant from `X-Tenant-Id`
- [ ] Return tenant-scoped repo/store/service instances from dependencies
- [ ] Add tenant bootstrap service for built-in sample and benchmark tenants
- [ ] Add config for benchmark dataset path and seed loading

### Task 5: Add tenant and graph explorer routes

**Files:**
- Modify: `app/api/routes/prompts.py`
- Modify: `app/schemas/prompt.py`

- [ ] Add `GET /api/tenants`
- [ ] Add `POST /api/tenants`
- [ ] Add `GET /api/graph/explorer`
- [ ] Require tenant context for prompt/search/cluster routes and keep tenant admin routes unscoped

## Chunk 3: Frontend Active Tenant And Explorer

### Task 6: Add active tenant client state and header propagation

**Files:**
- Modify: `web/lib/api.ts`
- Modify: `web/lib/types.ts`
- Create: `web/lib/tenant-storage.ts`
- Create: `web/components/tenant-switcher.tsx`

- [ ] Add tenant list/create API helpers
- [ ] Add active-tenant storage helpers
- [ ] Send `X-Tenant-Id` on prompt-scoped requests
- [ ] Add a tenant switch/create control in the dashboard chrome

### Task 7: Add tenant-scoped graph explorer UI

**Files:**
- Modify: `web/components/dashboard.tsx`
- Modify: `web/lib/graph.ts`

- [ ] Add a `Graph Explorer` tab
- [ ] Fetch explorer data for the active tenant
- [ ] Add category, hierarchy, layer-path, and prompt-id filters
- [ ] Render the tenant graph with the existing Cytoscape canvas

## Chunk 4: Verification And Docs

### Task 8: Update docs and run full verification

**Files:**
- Modify: `README.md`
- Modify: `.env.example`

- [ ] Document tenant behavior, built-in tenants, and graph explorer usage
- [ ] Run `pytest -q`
- [ ] Run `python3 -m compileall app scripts tests`
- [ ] Run `cd web && npm run build`
