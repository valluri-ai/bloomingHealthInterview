# Product Hardening And AWS Deploy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add semantic-search threshold controls, make duplicate cluster runs browsable and reusable per tenant, strengthen the README, and deploy the stack to AWS with cost-conscious ECS infrastructure.

**Architecture:** Keep the similarity and clustering logic in the existing backend services, but add missing persistence/read APIs for cluster runs and expose them in the dashboard. Add deployment as explicit infrastructure artifacts rather than ad hoc shell commands so the app can be recreated, documented, and operated cleanly.

**Tech Stack:** FastAPI, Neo4j, Next.js, React Query, Cytoscape, pytest, AWS ECS/Fargate, ALB, ECR, CloudFormation/CDK or equivalent AWS IaC.

---

## Chunk 1: Semantic Search Threshold

### Task 1: Expose semantic threshold in the dashboard

**Files:**
- Modify: `web/components/dashboard.tsx`
- Test: existing UI/API smoke verification

- [ ] Add `semanticThreshold` state beside `semanticQuery` and `semanticLimit`
- [ ] Add a threshold input control in the Semantic Search form
- [ ] Pass `threshold: semanticThreshold` into `semanticSearch(...)`
- [ ] Verify the search still runs and filters results correctly

### Task 2: Keep request payload/docs aligned

**Files:**
- Modify: `README.md`

- [ ] Update the semantic search example to show threshold support

## Chunk 2: Tenant-Persisted Cluster Runs

### Task 3: Add cluster-run listing in the repository layer

**Files:**
- Modify: `app/repositories/prompt_repository.py`
- Modify: `app/repositories/neo4j_prompt_repository.py`
- Modify: `app/repositories/tenant_scoped_prompt_repository.py`
- Test: `tests/test_neo4j_repository.py`, `tests/test_tenant_scoping.py`

- [ ] Add protocol method for listing cluster runs by tenant
- [ ] Implement tenant-scoped run listing in Neo4j with newest-first ordering
- [ ] Return enough metadata for selection/filtering without forcing a full run payload

### Task 4: Add API/schema support for run history

**Files:**
- Modify: `app/schemas/prompt.py`
- Modify: `app/services/analysis_service.py`
- Modify: `app/api/routes/prompts.py`
- Test: `tests/test_api_routes.py`

- [ ] Add a summary schema for cluster runs
- [ ] Add a service method to list cluster runs
- [ ] Add `GET /api/analysis/runs` scoped by tenant

### Task 5: Add run selection and filtering in the dashboard

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`
- Modify: `web/components/dashboard.tsx`

- [ ] Fetch persisted run summaries for the active tenant
- [ ] Show selectable runs in the Duplicate Clusters tab
- [ ] When a run is selected, load its full detail and use its saved filters/scope metadata
- [ ] Keep newly created runs in the list immediately after clustering

## Chunk 3: README Upgrade

### Task 6: Rewrite the README around the actual architecture

**Files:**
- Modify: `README.md`

- [ ] Explain tenant isolation and shared-vs-tenant-local graph structures
- [ ] Explain prompt hierarchy, category, prompt-family, and layer lineage
- [ ] Explain why the explorer supports different scopes and how drilldown works
- [ ] Document semantic search threshold and persisted cluster runs
- [ ] Add AWS deployment steps and operational notes once infra is complete

## Chunk 4: AWS Deployment

### Task 7: Add container artifacts

**Files:**
- Create/Modify: backend Dockerfile and frontend Dockerfile as needed
- Modify: `.dockerignore` files if needed

- [ ] Add reproducible container builds for backend and frontend
- [ ] Verify containers can run with env-driven config

### Task 8: Add AWS infrastructure definitions

**Files:**
- Create: infrastructure files under a dedicated path such as `infra/`

- [ ] Define low-cost ECS deployment for backend and frontend
- [ ] Use ALB for public routing
- [ ] Use ECR for images
- [ ] Configure env vars/secrets wiring

### Task 9: Deploy and verify

**Files:**
- Modify: `README.md`

- [ ] Build and push images
- [ ] Deploy the stack
- [ ] Verify public endpoints
- [ ] Record the final URL and deployment commands in the README
