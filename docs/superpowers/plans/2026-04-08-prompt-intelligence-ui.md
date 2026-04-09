# Prompt Intelligence UI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Next.js frontend for the FastAPI prompt intelligence service with a graph-first dashboard, scoped analysis views, a live API lab, and a FastAPI-rendered prompt preview iframe.

**Architecture:** Add a `web/` Next.js App Router application that talks to the existing FastAPI backend over HTTP. Extend the FastAPI backend with a preview endpoint and CORS support, then build a three-pane graph observatory UI using Cytoscape.js, TanStack Query, Motion, and a custom theme layer.

**Tech Stack:** Next.js App Router, TypeScript, Cytoscape.js, TanStack Query, Motion, shadcn/ui primitives, FastAPI, pytest, Playwright or equivalent UI smoke coverage if available.

---

## Chunk 1: Backend Support For The UI

### Task 1: Add preview endpoint tests first

**Files:**
- Modify: `tests/test_api_routes.py`
- Modify: `tests/fakes.py`

- [ ] **Step 1: Write failing tests for a prompt preview endpoint**

Add tests that:
- request `GET /api/prompts/{prompt_id}/preview`
- assert `200`
- assert `text/html` response
- assert prompt content and metadata are rendered
- assert missing prompt returns `404`

- [ ] **Step 2: Run the targeted tests to verify failure**

Run: `pytest tests/test_api_routes.py -k preview -v`
Expected: FAIL because the route does not exist yet.

- [ ] **Step 3: Extend fake repositories/stores as needed**

Add the minimum fake behavior needed to return stored prompt document content for preview rendering.

- [ ] **Step 4: Re-run the targeted tests**

Run: `pytest tests/test_api_routes.py -k preview -v`
Expected: Still FAIL, but only for missing implementation.

### Task 2: Implement prompt preview backend support

**Files:**
- Modify: `app/repositories/prompt_repository.py`
- Modify: `app/repositories/s3_prompt_store.py`
- Modify: `app/api/dependencies.py`
- Modify: `app/api/routes/prompts.py`
- Modify: `app/schemas/prompt.py` if a response helper is needed
- Test: `tests/test_api_routes.py`

- [ ] **Step 1: Add a template-store read method**

Add an interface method for reading a stored prompt document by `prompt_id`.

- [ ] **Step 2: Implement S3 document retrieval**

Fetch the prompt JSON from S3 and decode it into a typed payload or plain dict.

- [ ] **Step 3: Add a FastAPI route that renders HTML**

Return a styled `HTMLResponse` for `GET /api/prompts/{prompt_id}/preview` containing:
- prompt id
- name
- category
- layer
- variables
- formatted content
- storage/version metadata if available

- [ ] **Step 4: Wire the dependency graph**

Ensure the route can access both prompt metadata and stored prompt document content.

- [ ] **Step 5: Run the targeted preview tests**

Run: `pytest tests/test_api_routes.py -k preview -v`
Expected: PASS.

### Task 3: Add CORS for the Next.js frontend

**Files:**
- Modify: `app/main.py`
- Modify: `README.md`

- [ ] **Step 1: Add configurable CORS middleware**

Support at least a local Next.js origin such as `http://localhost:3000`.

- [ ] **Step 2: Document the frontend origin env var**

Update setup docs with the local dev flow.

- [ ] **Step 3: Run backend tests**

Run: `pytest tests/test_api_routes.py tests/test_ingestion.py tests/test_clustering.py -q`
Expected: PASS.

## Chunk 2: Next.js App Scaffold And Data Layer

### Task 4: Scaffold the Next.js app

**Files:**
- Create: `web/package.json`
- Create: `web/next.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/postcss.config.js`
- Create: `web/app/layout.tsx`
- Create: `web/app/page.tsx`
- Create: `web/app/globals.css`
- Create: `web/public/`

- [ ] **Step 1: Create the base Next.js app files**

Set up an App Router project with TypeScript.

- [ ] **Step 2: Add runtime dependencies**

Include the packages needed for:
- React/Next
- Cytoscape.js
- TanStack Query
- Motion
- utility styling/helpers

- [ ] **Step 3: Add npm scripts**

At minimum:
- `dev`
- `build`
- `start`
- `lint` if configured

- [ ] **Step 4: Install dependencies**

Run: `cd web && npm install`
Expected: install succeeds with a lockfile.

### Task 5: Build the frontend API client layer

**Files:**
- Create: `web/lib/api/types.ts`
- Create: `web/lib/api/client.ts`
- Create: `web/lib/api/endpoints.ts`
- Create: `web/lib/query/query-client.ts`
- Create: `web/providers/query-provider.tsx`

- [ ] **Step 1: Define TypeScript types matching the FastAPI payloads**

Include:
- semantic search
- similar prompts
- cluster visualization
- scoped analysis
- prompt graph
- load prompts
- embeddings generate

- [ ] **Step 2: Add a typed fetch client**

Support GET and POST requests against `NEXT_PUBLIC_API_BASE_URL`.

- [ ] **Step 3: Add endpoint helpers**

Create focused helpers rather than embedding URLs in components.

- [ ] **Step 4: Add TanStack Query provider wiring**

Wrap the app in a query provider.

- [ ] **Step 5: Smoke-test the frontend build**

Run: `cd web && npm run build`
Expected: build may fail on missing UI components, but the core config should compile once the shell exists.

## Chunk 3: Graph Observatory UI

### Task 6: Create the visual system and app shell

**Files:**
- Modify: `web/app/layout.tsx`
- Modify: `web/app/page.tsx`
- Modify: `web/app/globals.css`
- Create: `web/components/layout/app-shell.tsx`
- Create: `web/components/layout/topbar.tsx`
- Create: `web/components/layout/left-rail.tsx`
- Create: `web/components/layout/right-panel.tsx`
- Create: `web/components/layout/bottom-lab.tsx`

- [ ] **Step 1: Build the three-pane shell**

Left rail, graph stage, right panel, bottom lab.

- [ ] **Step 2: Implement the theme tokens**

Add CSS variables for color, borders, shadows, spacing, type, grain, and overlays.

- [ ] **Step 3: Add page-load and panel transitions**

Use Motion for the high-impact moments only.

- [ ] **Step 4: Build the shell and verify compile**

Run: `cd web && npm run build`
Expected: shell compiles even if data features are stubbed.

### Task 7: Implement the graph canvas and selection model

**Files:**
- Create: `web/components/graph/prompt-graph.tsx`
- Create: `web/components/graph/graph-controls.tsx`
- Create: `web/components/graph/graph-legend.tsx`
- Create: `web/lib/graph/map-visualization.ts`
- Modify: `web/app/page.tsx`

- [ ] **Step 1: Map visualization API data into graph nodes/edges**

Convert cluster payloads into Cytoscape elements with style metadata.

- [ ] **Step 2: Render the graph**

Support:
- duplicate cluster view
- node hover
- node selection
- edge highlighting

- [ ] **Step 3: Add mode switching**

Wire the graph mode controls for:
- duplicates
- category
- layer
- prompt family

- [ ] **Step 4: Keep selection in URL state**

Persist `promptId`, `clusterId`, `mode`, `threshold`, and `ranker`.

- [ ] **Step 5: Verify the graph build**

Run: `cd web && npm run build`
Expected: PASS.

### Task 8: Implement prompt detail, scoped analysis, and iframe preview

**Files:**
- Create: `web/components/prompt/prompt-detail-panel.tsx`
- Create: `web/components/prompt/prompt-metadata.tsx`
- Create: `web/components/prompt/scoped-analysis.tsx`
- Create: `web/components/prompt/similar-prompts.tsx`
- Create: `web/components/prompt/prompt-preview-frame.tsx`
- Modify: `web/lib/api/endpoints.ts`

- [ ] **Step 1: Load prompt graph, similar prompts, and scope analysis for the selected prompt**

Drive the right panel off the selected node.

- [ ] **Step 2: Add the iframe preview**

Point it at `GET /api/prompts/{prompt_id}/preview`.

- [ ] **Step 3: Add loading, empty, and error states**

Avoid blank panels.

- [ ] **Step 4: Verify compile**

Run: `cd web && npm run build`
Expected: PASS.

### Task 9: Implement the API Lab and admin controls

**Files:**
- Create: `web/components/lab/api-lab.tsx`
- Create: `web/components/lab/request-card.tsx`
- Create: `web/components/lab/json-response.tsx`
- Create: `web/components/lab/forms/load-prompts-form.tsx`
- Create: `web/components/lab/forms/generate-embeddings-form.tsx`
- Create: `web/components/lab/forms/semantic-search-form.tsx`
- Create: `web/components/lab/forms/hierarchy-upsert-form.tsx`

- [ ] **Step 1: Implement endpoint forms**

Support at least the required assignment endpoints and hierarchy upsert.

- [ ] **Step 2: Show live JSON responses**

Each request card should display status, timing if easy, and body.

- [ ] **Step 3: Wire actions back into the main UI**

For example:
- after loading prompts, refresh the dashboard
- after embeddings generation, refetch graph data
- after semantic search, highlight top matches

- [ ] **Step 4: Verify compile**

Run: `cd web && npm run build`
Expected: PASS.

## Chunk 4: Verification And Documentation

### Task 10: Add frontend and integration tests

**Files:**
- Create: `web/tests/` or equivalent if a test runner is added
- Modify: `tests/test_api_routes.py`
- Modify: `README.md`

- [ ] **Step 1: Add a small frontend smoke path**

If Playwright or a lightweight alternative is feasible, cover:
- dashboard loads
- prompt selection updates the right panel
- iframe preview URL changes

- [ ] **Step 2: Add backend regression coverage for preview route**

Keep the preview endpoint protected by tests.

- [ ] **Step 3: Run the full backend suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 4: Run the frontend production build**

Run: `cd web && npm run build`
Expected: PASS.

### Task 11: Document how to run the full stack

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document backend + frontend startup**

Include:
- backend env vars
- frontend env vars
- local ports
- preview endpoint behavior

- [ ] **Step 2: Document the new UI workflows**

Explain:
- graph modes
- scoped analysis
- API lab
- prompt preview

- [ ] **Step 3: Note git limitation if still absent**

If the directory is not a git repo, note that commit steps were skipped.

