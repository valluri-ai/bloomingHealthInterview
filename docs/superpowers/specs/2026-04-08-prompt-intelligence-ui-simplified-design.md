# Prompt Intelligence UI Simplified MVP Design

**Date:** 2026-04-08

## Goal

Replace the graph-heavy UI with a simple operator interface focused on the four required endpoints:

- `POST /api/embeddings/generate`
- `GET /api/prompts/{prompt_id}/similar`
- `POST /api/search/semantic`
- `GET /api/analysis/duplicates`

The UI should make those flows obvious, testable, and easy to understand.

## Product Direction

This MVP is not a visual analytics environment. It is a straightforward working console for running the required prompt similarity workflows.

The interface should answer four practical questions:

1. Which prompts should I embed, and with which model?
2. What prompts are similar to this selected prompt?
3. What prompts match this semantic query?
4. What duplicate clusters exist, and how do I filter them by scope?

## UI Shape

Use a simple four-tab interface:

1. **Generate Embeddings**
2. **Similar Prompts**
3. **Semantic Search**
4. **Duplicate Clusters**

No graph canvas. No API lab on the landing view. No large side panels. No dense hierarchy overlays.

## Tab 1: Generate Embeddings

### Purpose

Allow the user to choose prompts, inspect grouping, and generate embeddings with a chosen provider/model.

### UI

- prompt tree with checkboxes
- grouped by:
  - layer
  - category
  - prompt
- actions:
  - select all
  - clear
  - generate embeddings
- controls:
  - provider
  - model
  - batch size

### Output

Show:

- generated count
- prompt ids processed
- active provider/model used for the run

## Model-Scoped Embeddings

Embeddings must not be stored as one generic `embedding` only.

If the user changes the model, the backend should store the vector under a model-scoped property and index, so embeddings remain associated with the model that produced them.

The UI should surface the active model clearly on every endpoint interaction.

## Tab 2: Similar Prompts

### Purpose

Let the user select a prompt and retrieve similar prompts.

### UI

- prompt picker
- limit input
- threshold input
- model display/selection

### Output

Render a clean result list with:

- `prompt_id`
- `similarity_score`
- `content_preview`

## Tab 3: Semantic Search

### Purpose

Let the user run a text query and inspect matches.

### UI

- query input
- limit input
- model display/selection

### Output

Render a result list with:

- `prompt_id`
- similarity or ranking score
- `content_preview`
- `category`
- `layer`

## Tab 4: Duplicate Clusters

### Purpose

List duplicate clusters simply and allow basic filtering by scope.

### UI

- threshold input
- model display/selection
- filters:
  - category
  - layer or layer path

### Output

Show:

- `cluster_id`
- prompts in cluster
- prompt count

Each cluster row should expand to show the prompts inside it.

## Scope And Hierarchy Simplification

Instead of a visual hierarchy graph, the simplified MVP uses filters and grouping:

- prompt tree for embeddings selection
- category/layer metadata in search results
- category/layer filters in duplicate clusters

This preserves hierarchy-aware workflows without making the UI harder to read.

## Backend Support Needed

### Prompt Listing

The UI needs a prompt list endpoint so the frontend can render:

- the embeddings tree
- the prompt picker for similarity

### Model-Scoped Retrieval

Similarity, semantic search, and duplicate analysis must all operate against a selected embedding model, or a clear default model.

The API can keep backward compatibility while accepting optional model selection parameters.

## Visual Direction

Keep the styling sharp and intentional, but restrained:

- simple tabbed layout
- strong type hierarchy
- muted dark background
- high-contrast results lists
- minimal motion

The UI should feel clear first, stylish second.
