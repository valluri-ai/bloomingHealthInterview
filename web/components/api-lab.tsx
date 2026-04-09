"use client";

import { Braces, Play, Wand2 } from "lucide-react";
import type { ReactNode } from "react";

import type {
  ApiLabResult,
  EmbeddingProviderName,
  HierarchyKind,
  RankerName,
} from "@/lib/types";

interface ApiLabProps {
  loadJson: string;
  onLoadJsonChange: (value: string) => void;
  onLoadSample: () => void;
  embeddingProvider: EmbeddingProviderName;
  onEmbeddingProviderChange: (value: EmbeddingProviderName) => void;
  embeddingModel: string;
  onEmbeddingModelChange: (value: string) => void;
  batchSize: number;
  onBatchSizeChange: (value: number) => void;
  queryInput: string;
  onQueryInputChange: (value: string) => void;
  searchThreshold: number;
  onSearchThresholdChange: (value: number) => void;
  ranker: RankerName;
  threshold: number;
  neighborLimit: number;
  selectedPromptId: string;
  selectedClusterId: string;
  selectedRunId?: string;
  hierarchyKind: HierarchyKind;
  onHierarchyKindChange: (value: HierarchyKind) => void;
  hierarchyPath: string;
  onHierarchyPathChange: (value: string) => void;
  labResults: Record<string, ApiLabResult | undefined>;
  activeActions: Record<string, boolean | undefined>;
  onRunLoadPrompts: () => void;
  onRunGenerateEmbeddings: () => void;
  onRunSemanticSearch: () => void;
  onRunSimilar: () => void;
  onRunPromptGraph: () => void;
  onRunDrilldown: () => void;
  onRunDuplicates: () => void;
  onRunScopeClusters: () => void;
  onRunVisualization: () => void;
  onRunClusterDetail: () => void;
  onRunHierarchyUpsert: () => void;
}

function ResponseBox({ result }: { result?: ApiLabResult }) {
  if (!result) {
    return <div className="response-empty">No request executed yet.</div>;
  }

  if (!result.ok) {
    return (
      <div className="response-box response-box-error">
        <div className="response-meta">{result.timestamp}</div>
        <pre>{result.error}</pre>
      </div>
    );
  }

  return (
    <div className="response-box">
      <div className="response-meta">{result.timestamp}</div>
      <pre>{JSON.stringify(result.body, null, 2)}</pre>
    </div>
  );
}

function RequestCard({
  title,
  path,
  method,
  description,
  running,
  onRun,
  children,
  result,
}: {
  title: string;
  path: string;
  method: string;
  description: string;
  running?: boolean;
  onRun: () => void;
  children?: ReactNode;
  result?: ApiLabResult;
}) {
  return (
    <article className="request-card">
      <header className="request-card-header">
        <div>
          <div className="request-meta">
            <span className="method-pill">{method}</span>
            <span className="request-path">{path}</span>
          </div>
          <h4>{title}</h4>
          <p>{description}</p>
        </div>
        <button className="ghost-button" type="button" onClick={onRun} disabled={running}>
          <Play size={14} />
          {running ? "Running" : "Run"}
        </button>
      </header>
      {children ? <div className="request-card-body">{children}</div> : null}
      <ResponseBox result={result} />
    </article>
  );
}

export function ApiLab({
  loadJson,
  onLoadJsonChange,
  onLoadSample,
  embeddingProvider,
  onEmbeddingProviderChange,
  embeddingModel,
  onEmbeddingModelChange,
  batchSize,
  onBatchSizeChange,
  queryInput,
  onQueryInputChange,
  searchThreshold,
  onSearchThresholdChange,
  ranker,
  threshold,
  neighborLimit,
  selectedPromptId,
  selectedClusterId,
  selectedRunId,
  hierarchyKind,
  onHierarchyKindChange,
  hierarchyPath,
  onHierarchyPathChange,
  labResults,
  activeActions,
  onRunLoadPrompts,
  onRunGenerateEmbeddings,
  onRunSemanticSearch,
  onRunSimilar,
  onRunPromptGraph,
  onRunDrilldown,
  onRunDuplicates,
  onRunScopeClusters,
  onRunVisualization,
  onRunClusterDetail,
  onRunHierarchyUpsert,
}: ApiLabProps) {
  return (
    <div className="lab-shell">
      <header className="lab-header">
        <div>
          <div className="eyebrow">
            <Braces size={14} />
            API Lab
          </div>
          <h3>Every endpoint is live from here.</h3>
        </div>
        <button className="ghost-button" type="button" onClick={onLoadSample}>
          <Wand2 size={14} />
          Load sample JSON
        </button>
      </header>

      <div className="request-grid">
        <RequestCard
          title="Load Prompts"
          path="/api/prompts/load"
          method="POST"
          description="Bootstrap the graph from a prompt collection."
          running={activeActions.load}
          onRun={onRunLoadPrompts}
          result={labResults.load}
        >
          <textarea
            className="lab-textarea"
            value={loadJson}
            onChange={(event) => onLoadJsonChange(event.target.value)}
          />
        </RequestCard>

        <RequestCard
          title="Generate Embeddings"
          path="/api/embeddings/generate"
          method="POST"
          description="Generate or regenerate embeddings through the backend provider."
          running={activeActions.embed}
          onRun={onRunGenerateEmbeddings}
          result={labResults.embed}
        >
          <div className="field-grid">
            <label className="field">
              <span>Provider</span>
              <select
                value={embeddingProvider}
                onChange={(event) =>
                  onEmbeddingProviderChange(event.target.value as EmbeddingProviderName)
                }
              >
                <option value="openai">openai</option>
                <option value="bedrock">bedrock</option>
              </select>
            </label>
            <label className="field">
              <span>Batch size</span>
              <input
                type="number"
                min={1}
                max={512}
                value={batchSize}
                onChange={(event) => onBatchSizeChange(Number(event.target.value))}
              />
            </label>
          </div>
          <label className="field">
            <span>Model</span>
            <input
              value={embeddingModel}
              onChange={(event) => onEmbeddingModelChange(event.target.value)}
            />
          </label>
        </RequestCard>

        <RequestCard
          title="Semantic Search"
          path="/api/search/semantic"
          method="POST"
          description="Run hybrid semantic search from a free-text query."
          running={activeActions.search}
          onRun={onRunSemanticSearch}
          result={labResults.search}
        >
          <div className="field-grid">
            <label className="field field-span">
              <span>Query</span>
              <input value={queryInput} onChange={(event) => onQueryInputChange(event.target.value)} />
            </label>
            <label className="field">
              <span>Threshold</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={searchThreshold}
                onChange={(event) => onSearchThresholdChange(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Ranker</span>
              <input value={ranker} readOnly />
            </label>
          </div>
        </RequestCard>

        <RequestCard
          title="Similar Prompts"
          path={`/api/prompts/${selectedPromptId || "{prompt_id}"}/similar`}
          method="GET"
          description="Prompt-to-prompt similarity for the current selection."
          running={activeActions.similar}
          onRun={onRunSimilar}
          result={labResults.similar}
        />

        <RequestCard
          title="Prompt Graph"
          path={`/api/prompts/${selectedPromptId || "{prompt_id}"}/graph`}
          method="GET"
          description="Structural graph detail for the current prompt."
          running={activeActions.graph}
          onRun={onRunPromptGraph}
          result={labResults.graph}
        />

        <RequestCard
          title="Drilldown Similarity"
          path={`/api/prompts/${selectedPromptId || "{prompt_id}"}/similar/drilldown`}
          method="GET"
          description="Global, same-layer, same-category, and family similarity slices."
          running={activeActions.drilldown}
          onRun={onRunDrilldown}
          result={labResults.drilldown}
        />

        <RequestCard
          title="Duplicate Analysis"
          path="/api/analysis/duplicates"
          method="GET"
          description="Thresholded duplicate clustering."
          running={activeActions.duplicates}
          onRun={onRunDuplicates}
          result={labResults.duplicates}
        >
          <div className="field-grid">
            <label className="field">
              <span>Threshold</span>
              <input value={threshold} readOnly />
            </label>
            <label className="field">
              <span>Neighbors</span>
              <input value={neighborLimit} readOnly />
            </label>
            <label className="field">
              <span>Ranker</span>
              <input value={ranker} readOnly />
            </label>
          </div>
        </RequestCard>

        <RequestCard
          title="Scoped Cluster Analysis"
          path={`/api/analysis/prompts/${selectedPromptId || "{prompt_id}"}/scopes`}
          method="GET"
          description="Category, layer, and prompt-family cluster slices."
          running={activeActions.scopes}
          onRun={onRunScopeClusters}
          result={labResults.scopes}
        />

        <RequestCard
          title="Cluster Visualization"
          path={`/api/analysis/runs/${selectedRunId || "{run_id}"}/visualization`}
          method="GET"
          description="Visualization-ready payload for a persisted cluster run."
          running={activeActions.visualization}
          onRun={onRunVisualization}
          result={labResults.visualization}
        />

        <RequestCard
          title="Cluster Detail"
          path={`/api/analysis/runs/${selectedRunId || "{run_id}"}/clusters/${selectedClusterId || "{cluster_id}"}`}
          method="GET"
          description="Detailed cluster payload from a persisted duplicate run."
          running={activeActions.clusterDetail}
          onRun={onRunClusterDetail}
          result={labResults.clusterDetail}
        />

        <RequestCard
          title="Hierarchy Upsert"
          path="/api/hierarchy/upsert"
          method="POST"
          description="Manual admin entry point for hierarchy paths."
          running={activeActions.hierarchy}
          onRun={onRunHierarchyUpsert}
          result={labResults.hierarchy}
        >
          <div className="field-grid">
            <label className="field">
              <span>Kind</span>
              <select
                value={hierarchyKind}
                onChange={(event) => onHierarchyKindChange(event.target.value as HierarchyKind)}
              >
                <option value="prompt_path">prompt_path</option>
                <option value="category">category</option>
                <option value="layer_path">layer_path</option>
              </select>
            </label>
            <label className="field field-span">
              <span>Path</span>
              <input value={hierarchyPath} onChange={(event) => onHierarchyPathChange(event.target.value)} />
            </label>
          </div>
        </RequestCard>
      </div>
    </div>
  );
}
