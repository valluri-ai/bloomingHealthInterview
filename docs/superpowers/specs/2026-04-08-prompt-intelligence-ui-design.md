# Prompt Intelligence UI Design

**Date:** 2026-04-08

## Goal

Build a visually distinctive Next.js frontend for the Prompt Similarity & Deduplication Service that makes the graph-aware analysis usable: hybrid semantic search, duplicate clusters, hierarchy/lineage inspection, scoped cluster analysis, and prompt document preview from S3 through a FastAPI-rendered HTML iframe.

## Product Direction

This UI is not a CRUD admin console. It is a graph observatory for prompt intelligence.

The center of the product is the prompt relationship graph, not a table. Users should be able to:

- search prompts semantically
- inspect similar prompts from a selected node
- view duplicate clusters
- switch between scoped analysis modes
- understand lineage across category, layer, and prompt family
- open the underlying prompt document in a document-style preview panel

## Visual Direction

The interface should feel like an editorial control room rather than a default SaaS dashboard.

- Background: dark, textured, slightly archival
- Accent system: oxidized brass, signal cyan, restrained coral alerts
- Typography: high-contrast serif display paired with precise technical sans/mono UI text
- Composition: asymmetric three-pane layout with a large graph stage
- Motion: deliberate, high-impact transitions for graph focus, panel transitions, and preview loading

The most memorable moment should be the "document theater": selecting a prompt highlights its graph neighborhood while loading the S3-backed prompt document in a large iframe on the right.

## Recommended Technical Approach

### Frontend

- Next.js App Router with TypeScript
- Cytoscape.js for the main graph canvas
- TanStack Query for API data orchestration
- Motion for animated transitions and panel choreography
- shadcn/ui primitives as a base layer only, restyled heavily

### Backend Additions

- Add CORS configuration for the Next.js origin
- Add `GET /api/prompts/{prompt_id}/preview` to render a prompt document as HTML for iframe embedding
- Optionally add a raw document endpoint later if needed for developer tooling

## Why Cytoscape.js

The product needs graph analysis and arbitrary network visualization more than it needs a node-editor workflow canvas.

Cytoscape.js is the best primary fit because the UI needs:

- cluster visualization
- semantic neighbor highlighting
- category/layer/family overlays
- graph-style layout, filtering, and styling

React Flow remains a strong secondary option for workflow-style node editing, and Sigma.js remains a scale-up option if the graph grows into a much denser 1000+ node view. For the current product shape, Cytoscape.js is the right primary renderer.

## Information Architecture

### Left Rail

Purpose: control the system and issue API actions.

Contains:

- semantic search
- ranker and threshold controls
- embeddings generation controls
- prompt loading controls
- endpoint launcher cards
- active dataset and model metadata

### Center Graph Stage

Purpose: visualize relationships and support exploration.

Contains:

- main graph canvas
- mode switcher
- cluster highlighting
- node selection
- edge confidence styling
- lineage emphasis for selected prompt

Graph modes:

- duplicates
- global similarity
- same category
- same layer
- same prompt family

### Right Document Theater

Purpose: show selected prompt detail and the prompt document itself.

Contains:

- prompt metadata
- variable chips
- scope summary
- similar prompt summary
- iframe preview of `GET /api/prompts/{prompt_id}/preview`

### Bottom API Lab

Purpose: make every endpoint usable, inspectable, and debuggable from the UI.

Contains:

- endpoint forms
- query/body controls
- last response JSON
- loading/error states
- replay button

## Endpoint-to-UI Mapping

- `POST /api/prompts/load`
  - dataset loader in the left rail and API Lab
- `POST /api/embeddings/generate`
  - embeddings controls in the left rail and API Lab
- `GET /api/prompts/{prompt_id}/similar`
  - similar prompts drawer and selected-node summary
- `GET /api/prompts/{prompt_id}/similar/drilldown`
  - selected-node analysis tabs
- `GET /api/prompts/{prompt_id}/graph`
  - lineage inspector and detail card
- `POST /api/search/semantic`
  - command search surface
- `GET /api/analysis/duplicates`
  - duplicate scan list and cluster mode
- `GET /api/analysis/prompts/{prompt_id}/scopes`
  - scoped cluster analysis cards
- `GET /api/analysis/clusters/visualization`
  - primary graph data source
- `GET /api/analysis/clusters/{cluster_id}`
  - cluster detail modal or drawer
- `POST /api/hierarchy/upsert`
  - advanced admin action in API Lab
- `GET /api/prompts/{prompt_id}/preview`
  - iframe document preview

## URL State

The UI should be deep-linkable using search params for at least:

- `promptId`
- `clusterId`
- `mode`
- `threshold`
- `ranker`
- `query`

This makes the UI shareable and improves debugging.

## Data Flow

1. Load cluster visualization data for the default graph mode.
2. When the user searches, run semantic search and optionally re-center the graph around top matches.
3. When the user selects a prompt node:
   - load prompt graph data
   - load similar prompts
   - load scoped analysis
   - set the iframe preview URL
4. When the user changes threshold or ranker:
   - refetch graph and analysis data
   - preserve the current selected prompt if possible

## Error Handling

- Empty graph state when no embeddings exist yet
- Inline warnings when duplicate analysis returns no clusters
- Clear error banner when the FastAPI backend is unreachable
- Dedicated preview fallback when S3/preview rendering fails
- Persistent request diagnostics in API Lab

## Testing Strategy

### Backend

- add tests for the preview endpoint
- add tests for preview rendering fallback/error cases
- add tests for any new CORS or document-fetch logic if introduced

### Frontend

- component tests for stateful panels where useful
- end-to-end smoke tests for:
  - loading the dashboard
  - running semantic search
  - switching graph modes
  - selecting a prompt node
  - loading the iframe preview
  - using the API Lab for at least one POST and one GET endpoint

## File Layout

- `web/` for the Next.js application
- `web/app/` for routes and layout
- `web/components/` for graph, panels, controls, and API lab
- `web/lib/` for API clients, data mappers, and view-model helpers
- `web/styles/` or `web/app/globals.css` for theme tokens and bespoke visual language

## Constraints

- The frontend must work with the existing FastAPI backend and Neo4j-backed APIs.
- The preview must come from FastAPI-rendered HTML, not a raw S3 JSON iframe.
- The graph should remain understandable on both desktop and mobile, even if the mobile experience collapses panels into drawers.
- The UI must avoid default dashboard aesthetics and feel intentionally designed.

## Source Notes

These choices were informed by official docs for:

- Next.js App Router: https://nextjs.org/docs/app
- Cytoscape.js: https://js.cytoscape.org/
- TanStack Query: https://tanstack.com/query/latest/docs/framework/react/overview
- Motion for React: https://motion.dev/docs/react
- shadcn/ui: https://ui.shadcn.com/docs
- React Flow alternative: https://reactflow.dev/learn
