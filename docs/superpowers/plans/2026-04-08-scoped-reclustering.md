# Scoped Reclustering Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real scoped reclustering for duplicate analysis, while preserving a global clustering view and the existing category/hierarchy filters.

**Architecture:** Keep global duplicate clustering in the analysis service, but make filters define the allowed prompt set before clustering. Add a second grouped reclustering path that recomputes clusters inside category, hierarchy, and prompt-family scopes. Update the cluster UI to fetch and render both sections: filtered global clusters and scoped reclustered groups.

**Tech Stack:** FastAPI, Python service layer, Next.js, TypeScript, pytest

---

## Chunk 1: Backend reclustering

### Task 1: Add failing tests for filtered global reclustering and grouped scoped reclustering

**Files:**
- Modify: `tests/test_clustering.py`
- Modify: `tests/test_api_routes.py`

- [ ] **Step 1: Write failing clustering tests**
- [ ] **Step 2: Run them to verify they fail for the right reason**
- [ ] **Step 3: Add route-level test coverage for the new scoped endpoint / params**
- [ ] **Step 4: Re-run the targeted tests**

### Task 2: Implement backend scoped reclustering

**Files:**
- Modify: `app/services/analysis_service.py`
- Modify: `app/api/routes/prompts.py`
- Modify: `app/schemas/prompt.py`

- [ ] **Step 1: Add allowed-prompt filtering to global duplicate clustering**
- [ ] **Step 2: Add grouped scoped reclustering for category, hierarchy, and prompt family**
- [ ] **Step 3: Expose the scoped endpoint and query params**
- [ ] **Step 4: Run targeted tests**

## Chunk 2: Cluster UI

### Task 3: Update the clusters tab to show global plus scoped sections

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`
- Modify: `web/components/dashboard.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Add types and API helper for scoped duplicate groups**
- [ ] **Step 2: Replace client-side prompt trimming with backend-driven filtered clustering**
- [ ] **Step 3: Show global clusters and scoped reclustered groups together, with a scope-mode selector**
- [ ] **Step 4: Build/typecheck the frontend**

## Chunk 3: Verification

### Task 4: Verify end to end

**Files:**
- Modify: `README.md` if needed

- [ ] **Step 1: Run full pytest**
- [ ] **Step 2: Run compile/typecheck/build**
- [ ] **Step 3: Smoke the live endpoints if needed**
