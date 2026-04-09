# Load Prompts UI And Benchmark Harness Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paste-based prompt ingestion workflow to the simplified Next.js dashboard and add repeatable benchmark scripts for 100/500/1000+ prompt datasets.

**Architecture:** Keep the existing FastAPI ingestion endpoint as the backend contract. Add a lightweight frontend parser that accepts either a raw JSON array or an object with a `prompts` array, then submit the normalized payload to `POST /api/prompts/load`. Add Python benchmark utilities that generate synthetic prompt datasets with seeded duplicate families and run ingestion, embedding, search, and duplicate-analysis timing against the live API.

**Tech Stack:** Next.js, TypeScript, FastAPI, pytest, Python stdlib scripts

---

## Chunk 1: Prompt ingestion UI

### Task 1: Add failing tests for benchmark dataset generation helpers

**Files:**
- Create: `tests/test_benchmarking.py`
- Create: `app/utils/benchmarking.py`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run the tests to verify they fail**
- [ ] **Step 3: Implement the minimal generation and summary helpers**
- [ ] **Step 4: Run the tests to verify they pass**

### Task 2: Add paste-friendly ingestion parsing and UI tab

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`
- Modify: `web/components/dashboard.tsx`
- Modify: `web/app/globals.css`
- Use: `web/lib/sample-prompts.ts`

- [ ] **Step 1: Add UI state and payload parsing helper with a failing type/build check if needed**
- [ ] **Step 2: Implement a new `Load Prompts` tab with textarea, sample-fill, validate, ingest, and results**
- [ ] **Step 3: Refresh prompt metadata after ingest so the embeddings tree updates immediately**
- [ ] **Step 4: Build/typecheck the frontend**

## Chunk 2: Benchmark harness

### Task 3: Add benchmark scripts using the tested helpers

**Files:**
- Create: `scripts/generate_prompt_dataset.py`
- Create: `scripts/benchmark_prompts.py`
- Modify: `README.md`

- [ ] **Step 1: Implement dataset generation CLI for exact counts and duplicate-family variants**
- [ ] **Step 2: Implement benchmark CLI for ingest, embeddings, similar search, semantic search, and duplicate analysis timing**
- [ ] **Step 3: Document how to run 100/500/1000+ benchmarks and what metrics mean**
- [ ] **Step 4: Run pytest, compile, and Next.js build**
