"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  Layers3,
  ListChecks,
  Network,
  Search,
  Sparkles,
  SquareStack,
  Upload,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  analyzeMergeSuggestions,
  createTenant,
  createClusterRun,
  generateEmbeddings,
  getExplorerGraph,
  getClusterRun,
  getClusterRuns,
  getPromptPreviewHtml,
  getPrompts,
  getTenants,
  loadPrompts,
  getSimilarPrompts,
  semanticSearch,
} from "@/lib/api";
import { GraphCanvas } from "@/components/graph-canvas";
import { TenantSwitcher } from "@/components/tenant-switcher";
import { buildExplorerGraphElements } from "@/lib/graph";
import { parsePromptPayload } from "@/lib/prompt-payload";
import { SAMPLE_PROMPTS } from "@/lib/sample-prompts";
import { readStoredTenantId, writeStoredTenantId } from "@/lib/tenant-storage";
import type {
  DashboardTab,
  ClusterRunResponse,
  ClusterRunSummary,
  DuplicateScopeGroup,
  DuplicateScopeMode,
  DuplicateCluster,
  EmbeddingProviderName,
  ExplorerGraphResponse,
  MergeAnalysisResponse,
  PromptLoadResponse,
  PromptListItem,
  SimilarPromptResult,
  TenantSummary,
} from "@/lib/types";

function formatScore(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return value.toFixed(3);
}

function formatRunTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function ResultRow({
  row,
  showMetadata = false,
  onSelectPrompt,
  isSelected = false,
}: {
  row: SimilarPromptResult;
  showMetadata?: boolean;
  onSelectPrompt?: (promptId: string) => void;
  isSelected?: boolean;
}) {
  return (
    <article
      className={`result-row ${isSelected ? "is-selected" : ""} ${onSelectPrompt ? "result-row-clickable" : ""}`}
      onClick={onSelectPrompt ? () => onSelectPrompt(row.prompt_id) : undefined}
      role={onSelectPrompt ? "button" : undefined}
      tabIndex={onSelectPrompt ? 0 : undefined}
      onKeyDown={
        onSelectPrompt
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectPrompt(row.prompt_id);
              }
            }
          : undefined
      }
    >
      <div className="result-row-top">
        <strong>{row.prompt_id}</strong>
        <span>{formatScore(row.similarity_score ?? row.ranking_score)}</span>
      </div>
      <p>{row.content_preview}</p>
      {showMetadata ? (
        <div className="result-meta">
          <span>{row.category ?? "unknown category"}</span>
          <span>{row.layer_path ?? "unknown layer"}</span>
        </div>
      ) : null}
    </article>
  );
}

function ClusterCard({
  cluster,
  selectedPromptId,
  onSelectPrompt,
}: {
  cluster: DuplicateCluster;
  selectedPromptId?: string;
  onSelectPrompt?: (promptId: string) => void;
}) {
  return (
    <details className="cluster-card" key={cluster.cluster_id} open>
      <summary>
        <span>{cluster.cluster_id}</span>
        <span>{cluster.prompts.length} prompts</span>
      </summary>
      <div className="cluster-body">
        {cluster.prompts.map((prompt) => (
          <button
            className={`cluster-prompt-row ${selectedPromptId === prompt.prompt_id ? "is-selected" : ""}`}
            key={`${cluster.cluster_id}-${prompt.prompt_id}`}
            type="button"
            onClick={() => onSelectPrompt?.(prompt.prompt_id)}
          >
            <strong>{prompt.prompt_id}</strong>
            <div className="result-meta">
              <span>{formatScore(prompt.similarity_score)}</span>
              <span>{prompt.category ?? "unknown category"}</span>
              <span>{prompt.layer_path ?? "unknown layer"}</span>
            </div>
          </button>
        ))}
        <div className="merge-preview">
          <strong>Fast merge hint</strong>
          <p>{cluster.merge_suggestion.rationale}</p>
          <div className="result-meta">
            <span>Canonical: {cluster.merge_suggestion.canonical_prompt_id}</span>
            {cluster.merge_suggestion.optional_variables.length > 0 ? (
              <span>Optional vars: {cluster.merge_suggestion.optional_variables.join(", ")}</span>
            ) : null}
          </div>
        </div>
      </div>
    </details>
  );
}

function groupPrompts(prompts: PromptListItem[]) {
  const grouped = new Map<string, Map<string, PromptListItem[]>>();
  for (const prompt of prompts) {
    const layerGroup = grouped.get(prompt.layer_path) ?? new Map<string, PromptListItem[]>();
    const categoryGroup = layerGroup.get(prompt.category) ?? [];
    categoryGroup.push(prompt);
    layerGroup.set(prompt.category, categoryGroup);
    grouped.set(prompt.layer_path, layerGroup);
  }
  return [...grouped.entries()].map(([layerPath, categories]) => ({
    layerPath,
    categories: [...categories.entries()].map(([category, items]) => ({
      category,
      prompts: items.sort((left, right) => left.prompt_id.localeCompare(right.prompt_id)),
    })),
  }));
}

function compareHierarchySegments(left: string, right: string) {
  const order = ["org", "os", "team", "engine", "directive"];
  const leftIndex = order.indexOf(left);
  const rightIndex = order.indexOf(right);

  if (leftIndex !== -1 || rightIndex !== -1) {
    if (leftIndex === -1) {
      return 1;
    }
    if (rightIndex === -1) {
      return -1;
    }
    return leftIndex - rightIndex;
  }

  return left.localeCompare(right);
}

function collectHierarchySegments(prompts: PromptListItem[]) {
  const segments = new Set<string>();
  for (const prompt of prompts) {
    for (const segment of prompt.layer_path.split(".")) {
      if (segment) {
        segments.add(segment);
      }
    }
  }
  return [...segments].sort(compareHierarchySegments);
}

function groupClustersByScope(clusters: DuplicateCluster[], scopeType: DuplicateScopeMode): DuplicateScopeGroup[] {
  const grouped = new Map<string, DuplicateCluster[]>();
  for (const cluster of clusters) {
    const scopeValue = cluster.scope_key || "unscoped";
    const rows = grouped.get(scopeValue) ?? [];
    rows.push(cluster);
    grouped.set(scopeValue, rows);
  }
  return [...grouped.entries()]
    .map(([scopeValue, scopeClusters]) => ({
      scope_type: scopeType,
      scope_value: scopeValue,
      prompt_count: scopeClusters.reduce((total, cluster) => total + cluster.prompts.length, 0),
      clusters: scopeClusters,
    }))
    .sort((left, right) => left.scope_value.localeCompare(right.scope_value));
}

function promptMatchesDisplayFilters(
  prompt: SimilarPromptResult,
  categoryFilter: string,
  hierarchyFilter: string,
) {
  const matchesCategory = !categoryFilter || prompt.category === categoryFilter;
  const matchesHierarchy =
    !hierarchyFilter || Boolean(prompt.layer_path?.split(".").includes(hierarchyFilter));
  return matchesCategory && matchesHierarchy;
}

function filterClustersForDisplay(
  clusters: DuplicateCluster[],
  categoryFilter: string,
  hierarchyFilter: string,
) {
  if (!categoryFilter && !hierarchyFilter) {
    return clusters;
  }

  return clusters
    .map((cluster) => {
      const visiblePrompts = cluster.prompts.filter((prompt) =>
        promptMatchesDisplayFilters(prompt, categoryFilter, hierarchyFilter),
      );
      const visiblePromptIds = new Set(visiblePrompts.map((prompt) => prompt.prompt_id));

      return {
        ...cluster,
        prompts: visiblePrompts,
        edges: cluster.edges.filter(
          (edge) => visiblePromptIds.has(edge.source) && visiblePromptIds.has(edge.target),
        ),
      };
    })
    .filter((cluster) => cluster.prompts.length > 0);
}

function PromptPreviewPane({
  tenantId,
  promptId,
}: {
  tenantId: string;
  promptId: string | null;
}) {
  const previewQuery = useQuery({
    queryKey: ["prompt-preview", tenantId, promptId],
    queryFn: () => getPromptPreviewHtml(tenantId, promptId ?? ""),
    enabled: Boolean(promptId),
  });

  return (
    <aside className="preview-pane">
      <div className="preview-pane-header">
        <strong>Prompt preview</strong>
        <span>{promptId ?? "Select a prompt"}</span>
      </div>
      {promptId ? (
        previewQuery.isLoading ? (
          <div className="empty-state">Loading prompt preview...</div>
        ) : previewQuery.isError ? (
          <div className="empty-state">Preview unavailable for the selected prompt.</div>
        ) : (
          <iframe
            className="preview-frame"
            title={`Prompt preview ${promptId}`}
            srcDoc={previewQuery.data ?? ""}
          />
        )
      ) : (
        <div className="empty-state">Select a prompt from the results to load its document preview.</div>
      )}
    </aside>
  );
}

const SAMPLE_PROMPTS_JSON = JSON.stringify(SAMPLE_PROMPTS, null, 2);

const TABS: Array<{ key: DashboardTab; label: string; icon: typeof ListChecks }> = [
  { key: "load", label: "Load Prompts", icon: Upload },
  { key: "embeddings", label: "Generate Embeddings", icon: ListChecks },
  { key: "similar", label: "Similar Prompts", icon: Sparkles },
  { key: "search", label: "Semantic Search", icon: Search },
  { key: "clusters", label: "Duplicate Clusters", icon: Layers3 },
  { key: "graph", label: "Graph Explorer", icon: Network },
];

export function Dashboard() {
  const queryClient = useQueryClient();
  const [activeTenantId, setActiveTenantId] = useState("sample-prompts");
  const [tab, setTab] = useState<DashboardTab>("load");
  const [provider, setProvider] = useState<EmbeddingProviderName>("openai");
  const [model, setModel] = useState("text-embedding-3-large");
  const [batchSize, setBatchSize] = useState(32);
  const [selectedPromptIds, setSelectedPromptIds] = useState<string[]>([]);
  const [loadPayload, setLoadPayload] = useState(SAMPLE_PROMPTS_JSON);
  const [loadValidation, setLoadValidation] = useState<{
    promptCount: number;
    promptIds: string[];
  } | null>(null);
  const [loadFileName, setLoadFileName] = useState("");
  const [loadResult, setLoadResult] = useState<PromptLoadResponse | null>(null);
  const [similarPromptId, setSimilarPromptId] = useState("verification.dob");
  const [similarLimit, setSimilarLimit] = useState(5);
  const [similarThreshold, setSimilarThreshold] = useState(0.8);
  const [semanticQuery, setSemanticQuery] = useState("how to handle user interruptions");
  const [semanticLimit, setSemanticLimit] = useState(10);
  const [semanticThreshold, setSemanticThreshold] = useState(0);
  const [clusterThreshold, setClusterThreshold] = useState(0.9);
  const [clusterCategoryFilter, setClusterCategoryFilter] = useState("");
  const [clusterHierarchyFilter, setClusterHierarchyFilter] = useState("");
  const [clusterScopeMode, setClusterScopeMode] = useState<DuplicateScopeMode>("category");
  const [selectedPreviewPromptId, setSelectedPreviewPromptId] = useState<string | null>(null);
  const [embeddingsResult, setEmbeddingsResult] = useState<{
    generated_count: number;
    prompt_ids: string[];
    provider: string;
    model: string;
  } | null>(null);
  const [similarResults, setSimilarResults] = useState<SimilarPromptResult[]>([]);
  const [semanticResults, setSemanticResults] = useState<SimilarPromptResult[]>([]);
  const [globalDuplicateClusters, setGlobalDuplicateClusters] = useState<DuplicateCluster[]>([]);
  const [scopedDuplicateGroups, setScopedDuplicateGroups] = useState<DuplicateScopeGroup[]>([]);
  const [globalClusterRun, setGlobalClusterRun] = useState<ClusterRunResponse | null>(null);
  const [scopedClusterRun, setScopedClusterRun] = useState<ClusterRunResponse | null>(null);
  const [selectedGlobalRunId, setSelectedGlobalRunId] = useState<string | null>(null);
  const [selectedScopedRunId, setSelectedScopedRunId] = useState<string | null>(null);
  const [mergeAnalysis, setMergeAnalysis] = useState<MergeAnalysisResponse | null>(null);
  const [mergeAnalysisLabel, setMergeAnalysisLabel] = useState("");
  const [graphView, setGraphView] = useState("global");
  const [graphCategoryFilter, setGraphCategoryFilter] = useState("");
  const [graphHierarchyFilter, setGraphHierarchyFilter] = useState("");
  const [graphLayerPathFilter, setGraphLayerPathFilter] = useState("");
  const [graphPromptQuery, setGraphPromptQuery] = useState("");
  const [graphSelection, setGraphSelection] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState("");
  const loadFileInputRef = useRef<HTMLInputElement | null>(null);

  const tenantsQuery = useQuery({
    queryKey: ["tenants"],
    queryFn: getTenants,
  });
  const tenants = tenantsQuery.data ?? [];
  const promptsQuery = useQuery({
    queryKey: ["prompts", activeTenantId],
    queryFn: () => getPrompts(activeTenantId),
    enabled: tenantsQuery.isSuccess && tenants.some((tenant) => tenant.tenant_id === activeTenantId),
  });
  const explorerQuery = useQuery({
    queryKey: [
      "graph-explorer",
      activeTenantId,
      graphView,
      graphCategoryFilter,
      graphHierarchyFilter,
      graphLayerPathFilter,
      graphPromptQuery,
    ],
    queryFn: () =>
      getExplorerGraph(activeTenantId, {
        view: graphView,
        category: graphCategoryFilter || undefined,
        hierarchy: graphHierarchyFilter || undefined,
        layer_path: graphLayerPathFilter || undefined,
        prompt_query: graphPromptQuery || undefined,
      }),
    enabled:
      tab === "graph" &&
      tenantsQuery.isSuccess &&
      tenants.some((tenant) => tenant.tenant_id === activeTenantId),
  });
  const clusterRunsQuery = useQuery({
    queryKey: ["cluster-runs", activeTenantId],
    queryFn: () => getClusterRuns(activeTenantId),
    enabled: tenantsQuery.isSuccess && tenants.some((tenant) => tenant.tenant_id === activeTenantId),
  });

  const prompts = promptsQuery.data ?? [];
  const clusterRuns = clusterRunsQuery.data ?? [];
  const promptTree = groupPrompts(prompts);
  const allPromptIds = prompts.map((prompt) => prompt.prompt_id);
  const displayedGlobalDuplicateClusters = filterClustersForDisplay(
    globalClusterRun?.clusters ?? globalDuplicateClusters,
    clusterCategoryFilter,
    clusterHierarchyFilter,
  );
  const displayedScopedDuplicateGroups = groupClustersByScope(
    filterClustersForDisplay(
      scopedClusterRun?.clusters ?? scopedDuplicateGroups.flatMap((group) => group.clusters),
      clusterCategoryFilter,
      clusterHierarchyFilter,
    ),
    (scopedClusterRun?.scope_mode as DuplicateScopeMode | undefined) ?? clusterScopeMode,
  );
  const globalAnalyzableClusters = displayedGlobalDuplicateClusters
    .filter((cluster) => cluster.prompts.length > 1)
    .map((cluster) => ({
      cluster_id: cluster.cluster_id,
      prompt_ids: cluster.prompts.map((prompt) => prompt.prompt_id),
    }));
  const scopedAnalyzableClusters = displayedScopedDuplicateGroups
    .flatMap((group) => group.clusters)
    .filter((cluster) => cluster.prompts.length > 1)
    .map((cluster) => ({
      cluster_id: cluster.cluster_id,
      prompt_ids: cluster.prompts.map((prompt) => prompt.prompt_id),
    }));
  const clusterCategories = [...new Set(prompts.map((prompt) => prompt.category))].sort();
  const clusterHierarchySegments = collectHierarchySegments(prompts);
  const globalRunSummaries = clusterRuns.filter((run) => run.scope_mode === "global");
  const scopedRunSummaries = clusterRuns.filter((run) => run.scope_mode !== "global");
  const explorerGraph = explorerQuery.data as ExplorerGraphResponse | undefined;
  const explorerElements = buildExplorerGraphElements(explorerGraph);

  useEffect(() => {
    const storedTenantId = readStoredTenantId();
    if (storedTenantId) {
      setActiveTenantId(storedTenantId);
    }
  }, []);

  useEffect(() => {
    if (!tenants.length) {
      return;
    }
    const tenantExists = tenants.some((tenant) => tenant.tenant_id === activeTenantId);
    if (!tenantExists) {
      setActiveTenantId(tenants[0].tenant_id);
    }
  }, [tenants, activeTenantId]);

  useEffect(() => {
    if (!activeTenantId) {
      return;
    }
    writeStoredTenantId(activeTenantId);
    setSelectedPromptIds([]);
    setSimilarPromptId("");
    setSelectedPreviewPromptId(null);
    setSimilarResults([]);
    setSemanticResults([]);
    setGlobalDuplicateClusters([]);
    setScopedDuplicateGroups([]);
    setGlobalClusterRun(null);
    setScopedClusterRun(null);
    setSelectedGlobalRunId(null);
    setSelectedScopedRunId(null);
    setLoadFileName("");
    setMergeAnalysis(null);
    setGraphView("global");
    setGraphCategoryFilter("");
    setGraphHierarchyFilter("");
    setGraphLayerPathFilter("");
    setGraphPromptQuery("");
    setGraphSelection(null);
  }, [activeTenantId]);

  useEffect(() => {
    if (!prompts.length) {
      return;
    }
    if (!prompts.some((prompt) => prompt.prompt_id === similarPromptId)) {
      setSimilarPromptId(prompts[0].prompt_id);
    }
  }, [prompts, similarPromptId]);

  async function runAction(action: string, work: () => Promise<void>) {
    setActiveAction(action);
    setErrorMessage("");
    try {
      await work();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setActiveAction("");
    }
  }

  function togglePromptSelection(promptId: string) {
    setSelectedPromptIds((current) =>
      current.includes(promptId)
        ? current.filter((value) => value !== promptId)
        : [...current, promptId],
    );
  }

  const activeModelLabel = `${provider}:${model}`;

  function resetMergeAnalysis() {
    setMergeAnalysis(null);
    setMergeAnalysisLabel("");
  }

  function applySavedRun(run: ClusterRunResponse) {
    setClusterThreshold(run.threshold);
    setClusterCategoryFilter(run.category_filter ?? "");
    setClusterHierarchyFilter(run.hierarchy_filter ?? "");
    resetMergeAnalysis();
    const firstPromptId = run.clusters[0]?.prompts[0]?.prompt_id ?? null;
    setSelectedPreviewPromptId(firstPromptId);

    if (run.scope_mode === "global") {
      setGlobalClusterRun(run);
      setGlobalDuplicateClusters(run.clusters);
      setSelectedGlobalRunId(run.run_id);
      setScopedClusterRun(null);
      setScopedDuplicateGroups([]);
      setSelectedScopedRunId(null);
      return;
    }

    const scopeMode = run.scope_mode as DuplicateScopeMode;
    setClusterScopeMode(scopeMode);
    setScopedClusterRun(run);
    setScopedDuplicateGroups(groupClustersByScope(run.clusters, scopeMode));
    setSelectedScopedRunId(run.run_id);
    setGlobalClusterRun(null);
    setGlobalDuplicateClusters([]);
    setSelectedGlobalRunId(null);
  }

  async function loadSavedRun(summary: ClusterRunSummary) {
    await runAction(`load-run-${summary.run_id}`, async () => {
      const run = await getClusterRun(activeTenantId, summary.run_id);
      applySavedRun(run);
    });
  }

  return (
    <main className="simple-dashboard">
      <header className="simple-hero">
        <div>
          <div className="simple-kicker">
            <SquareStack size={14} />
            Prompt Similarity Service
          </div>
          <h1>Five workflows. No noise.</h1>
          <p>
            Load prompt JSON, generate embeddings from a prompt tree, inspect similar prompts,
            run semantic search, and review duplicate clusters with simple scope filters.
          </p>
        </div>
        <div className="hero-controls">
          <section className="control-card">
            <div className="control-card-header">
              <strong>Workspace</strong>
              <span>Switch the active tenant before loading, searching, or clustering.</span>
            </div>
            <TenantSwitcher
              tenants={tenants}
              activeTenantId={activeTenantId}
              onTenantChange={setActiveTenantId}
              busy={activeAction === "create-tenant"}
              loading={tenantsQuery.isLoading}
              onCreateTenant={async (input) => {
                await runAction("create-tenant", async () => {
                  const tenant = await createTenant(input);
                  await queryClient.invalidateQueries({ queryKey: ["tenants"] });
                  setActiveTenantId(tenant.tenant_id);
                });
              }}
            />
          </section>
          <section className="control-card">
            <div className="control-card-header">
              <strong>Embedding profile</strong>
              <span>These settings drive prompt similarity, semantic search, and duplicate analysis.</span>
            </div>
            <div className="model-bar">
              <label className="field compact-field">
                <span>Provider</span>
                <select value={provider} onChange={(event) => setProvider(event.target.value as EmbeddingProviderName)}>
                  <option value="openai">openai</option>
                  <option value="bedrock">bedrock</option>
                </select>
              </label>
              <label className="field compact-field model-field">
                <span>Model</span>
                <input value={model} onChange={(event) => setModel(event.target.value)} />
              </label>
            </div>
            <div className="active-model-pill">{activeModelLabel}</div>
          </section>
        </div>
      </header>

      {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}

      <nav className="tab-bar" aria-label="Prompt workflows">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            className={`tab-button ${tab === key ? "tab-button-active" : ""}`}
            type="button"
            onClick={() => setTab(key)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </nav>

      {tab === "load" ? (
        <section className="simple-panel">
          <div className="panel-header">
            <div>
              <h2>Load Prompts</h2>
              <p>Paste prompt JSON or upload a `.json` file, validate it locally, then ingest it into the active prompt store and Neo4j.</p>
            </div>
          </div>
          <div className="help-panel">
            <strong>Accepted formats</strong>
            <p>
              Paste either a raw JSON array of prompt objects or an object shaped like
              <code>{' { "prompts": [...] } '}</code>.
            </p>
            <p>
              You can also upload a file directly. The benchmark dataset shipped with this repo is
              <code> tmp/benchmark-dataset-1000.json </code>.
            </p>
          </div>
          <input
            ref={loadFileInputRef}
            type="file"
            accept=".json,application/json"
            style={{ display: "none" }}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) {
                return;
              }
              void runAction("upload-load-file", async () => {
                const text = await file.text();
                const parsed = parsePromptPayload(text);
                setLoadPayload(parsed.normalizedText);
                setLoadValidation({
                  promptCount: parsed.prompts.length,
                  promptIds: parsed.prompts.map((prompt) => prompt.prompt_id),
                });
                setLoadResult(null);
                setLoadFileName(file.name);
              });
              event.currentTarget.value = "";
            }}
          />
          <label className="field">
            <span>Prompt payload</span>
            <textarea
              className="payload-textarea"
              value={loadPayload}
              onChange={(event) => setLoadPayload(event.target.value)}
              spellCheck={false}
            />
          </label>
          <div className="toolbar-row">
            <button
              className="ghost-button"
              type="button"
              onClick={() => loadFileInputRef.current?.click()}
            >
              {activeAction === "upload-load-file" ? "Reading file..." : "Upload JSON file"}
            </button>
            <button
              className="ghost-button"
              type="button"
              onClick={() => {
                setLoadPayload(SAMPLE_PROMPTS_JSON);
                setLoadValidation(null);
                setLoadFileName("");
              }}
            >
              Load sample data
            </button>
            <button
              className="ghost-button"
              type="button"
              onClick={() => {
                setLoadPayload("");
                setLoadValidation(null);
                setLoadResult(null);
                setLoadFileName("");
              }}
            >
              Clear
            </button>
            <button
              className="ghost-button"
              type="button"
              onClick={() =>
                void runAction("validate-load", async () => {
                  const parsed = parsePromptPayload(loadPayload);
                  setLoadPayload(parsed.normalizedText);
                  setLoadValidation({
                    promptCount: parsed.prompts.length,
                    promptIds: parsed.prompts.map((prompt) => prompt.prompt_id),
                  });
                })
              }
            >
              {activeAction === "validate-load" ? "Validating..." : "Validate"}
            </button>
            <button
              className="primary-button"
              type="button"
              disabled={activeAction === "load-prompts"}
              onClick={() =>
                void runAction("load-prompts", async () => {
                  const parsed = parsePromptPayload(loadPayload);
                  setLoadPayload(parsed.normalizedText);
                  setLoadValidation({
                    promptCount: parsed.prompts.length,
                    promptIds: parsed.prompts.map((prompt) => prompt.prompt_id),
                  });
                  const result = await loadPrompts(activeTenantId, parsed.prompts);
                  setLoadResult(result);
                  setSelectedPromptIds(result.prompt_ids);
                  await queryClient.invalidateQueries({ queryKey: ["prompts", activeTenantId] });
                  await queryClient.invalidateQueries({ queryKey: ["graph-explorer", activeTenantId] });
                  await queryClient.invalidateQueries({ queryKey: ["tenants"] });
                })
              }
            >
              {activeAction === "load-prompts" ? "Ingesting..." : "Ingest prompts"}
            </button>
          </div>

          {loadValidation ? (
            <div className="result-panel">
              <h3>Validated payload</h3>
              <div className="result-meta">
                <span>{loadValidation.promptCount} prompts ready</span>
                {loadFileName ? <span>Source file: {loadFileName}</span> : null}
              </div>
              <div className="chip-strip">
                {loadValidation.promptIds.map((promptId) => (
                  <span className="result-chip" key={`validation-${promptId}`}>
                    {promptId}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          {loadResult ? (
            <div className="result-panel">
              <h3>Latest ingestion</h3>
              <div className="result-meta">
                <span>{loadResult.loaded_count} loaded</span>
                <span>Prompt tree refreshed</span>
              </div>
              <div className="storage-list">
                {loadResult.stored_prompts.map((storedPrompt) => (
                  <article className="storage-row" key={storedPrompt.prompt_id}>
                    <div className="result-row-top">
                      <strong>{storedPrompt.prompt_id}</strong>
                      <span>{storedPrompt.version_id ?? "no version id"}</span>
                    </div>
                    <div className="result-meta">
                      <span>{storedPrompt.bucket}</span>
                      <span>{storedPrompt.key}</span>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {tab === "embeddings" ? (
        <section className="simple-panel">
          <div className="panel-header">
            <div>
              <h2>Generate Embeddings</h2>
              <p>Select prompts from the tree, choose a model, and store model-scoped embeddings.</p>
            </div>
            <label className="field compact-field">
              <span>Batch size</span>
              <input
                type="number"
                min={1}
                max={512}
                value={batchSize}
                onChange={(event) => setBatchSize(Number(event.target.value))}
              />
            </label>
          </div>

          <div className="toolbar-row">
            <button
              className="ghost-button"
              type="button"
              onClick={() => setSelectedPromptIds(allPromptIds)}
            >
              Select all
            </button>
            <button className="ghost-button" type="button" onClick={() => setSelectedPromptIds([])}>
              Clear
            </button>
            <button
              className="primary-button"
              type="button"
              disabled={activeAction === "embeddings" || selectedPromptIds.length === 0}
              onClick={() =>
                void runAction("embeddings", async () => {
                  const result = await generateEmbeddings({
                    tenantId: activeTenantId,
                    prompt_ids: selectedPromptIds,
                    batch_size: batchSize,
                    provider,
                    model,
                  });
                  setEmbeddingsResult(result);
                  await queryClient.invalidateQueries({ queryKey: ["prompts", activeTenantId] });
                })
              }
            >
              {activeAction === "embeddings" ? "Generating..." : "Generate embeddings"}
            </button>
          </div>

          <div className="selected-summary">
            <strong>{selectedPromptIds.length}</strong> prompt{selectedPromptIds.length === 1 ? "" : "s"} selected
          </div>

          <div className="tree-shell">
            {promptsQuery.isLoading ? <div className="empty-state">Loading prompts...</div> : null}
            {!promptsQuery.isLoading && promptTree.length === 0 ? (
              <div className="empty-state">No prompts found. Load prompt data into the backend first.</div>
            ) : null}
            {promptTree.map((layerGroup) => (
              <details className="tree-layer" key={layerGroup.layerPath} open>
                <summary>
                  <span className="summary-label">
                    <ChevronDown size={14} />
                    {layerGroup.layerPath}
                  </span>
                  <span>{layerGroup.categories.reduce((total, category) => total + category.prompts.length, 0)} prompts</span>
                </summary>
                <div className="tree-layer-body">
                  {layerGroup.categories.map((categoryGroup) => (
                    <details className="tree-category" key={`${layerGroup.layerPath}-${categoryGroup.category}`} open>
                      <summary>
                        <span className="summary-label">
                          <ChevronRight size={14} />
                          {categoryGroup.category}
                        </span>
                        <span>{categoryGroup.prompts.length}</span>
                      </summary>
                      <div className="tree-prompt-list">
                        {categoryGroup.prompts.map((prompt) => (
                          <label className="tree-prompt-row" key={prompt.prompt_id}>
                            <input
                              type="checkbox"
                              checked={selectedPromptIds.includes(prompt.prompt_id)}
                              onChange={() => togglePromptSelection(prompt.prompt_id)}
                            />
                            <div>
                              <strong>{prompt.prompt_id}</strong>
                              <p>{prompt.name || "Untitled prompt"}</p>
                            </div>
                            <div className="model-chip-row">
                              {prompt.available_embedding_models.map((embeddingModel) => (
                                <span className="model-chip" key={embeddingModel}>
                                  {embeddingModel}
                                </span>
                              ))}
                            </div>
                          </label>
                        ))}
                      </div>
                    </details>
                  ))}
                </div>
              </details>
            ))}
          </div>

          {embeddingsResult ? (
            <div className="result-panel">
              <h3>Latest run</h3>
              <div className="result-meta">
                <span>{embeddingsResult.generated_count} generated</span>
                <span>{embeddingsResult.provider}</span>
                <span>{embeddingsResult.model}</span>
              </div>
              <div className="chip-strip">
                {embeddingsResult.prompt_ids.map((promptId) => (
                  <span className="result-chip" key={promptId}>
                    {promptId}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {tab === "similar" ? (
        <section className="simple-panel">
          <div className="panel-header">
            <div>
              <h2>Similar Prompts</h2>
              <p>Select one prompt and return its nearest semantic matches.</p>
            </div>
          </div>
          <div className="form-grid">
            <label className="field field-span">
              <span>Prompt</span>
              <select value={similarPromptId} onChange={(event) => setSimilarPromptId(event.target.value)}>
                {prompts.length === 0 ? <option value="">No prompts loaded for this tenant</option> : null}
                {prompts.map((prompt) => (
                  <option key={prompt.prompt_id} value={prompt.prompt_id}>
                    {prompt.prompt_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Limit</span>
              <input type="number" min={1} max={25} value={similarLimit} onChange={(event) => setSimilarLimit(Number(event.target.value))} />
            </label>
            <label className="field">
              <span>Threshold</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={similarThreshold}
                onChange={(event) => setSimilarThreshold(Number(event.target.value))}
              />
            </label>
          </div>
          <div className="toolbar-row">
            <button
              className="primary-button"
              type="button"
              disabled={activeAction === "similar" || !similarPromptId || !prompts.some((prompt) => prompt.prompt_id === similarPromptId)}
              onClick={() =>
                void runAction("similar", async () => {
                  const result = await getSimilarPrompts(activeTenantId, similarPromptId, {
                    limit: similarLimit,
                    threshold: similarThreshold,
                    provider,
                    model,
                  });
                  setSimilarResults(result);
                  setSelectedPreviewPromptId(result[0]?.prompt_id ?? similarPromptId);
                })
              }
            >
              {activeAction === "similar" ? "Loading..." : "Find similar prompts"}
            </button>
          </div>
          <div className="workspace-with-preview">
            <div className="results-stack">
              {similarResults.map((row) => (
                <ResultRow
                  key={row.prompt_id}
                  row={row}
                  onSelectPrompt={setSelectedPreviewPromptId}
                  isSelected={selectedPreviewPromptId === row.prompt_id}
                />
              ))}
              {similarResults.length === 0 ? (
                <div className="empty-state">Run the query to see similar prompts.</div>
              ) : null}
            </div>
            <PromptPreviewPane tenantId={activeTenantId} promptId={selectedPreviewPromptId} />
          </div>
        </section>
      ) : null}

      {tab === "search" ? (
        <section className="simple-panel">
          <div className="panel-header">
            <div>
              <h2>Semantic Search</h2>
              <p>Use free text and inspect matching prompts with category and layer metadata.</p>
            </div>
          </div>
          <div className="form-grid">
            <label className="field field-span">
              <span>Query</span>
              <input value={semanticQuery} onChange={(event) => setSemanticQuery(event.target.value)} />
            </label>
            <label className="field">
              <span>Limit</span>
              <input type="number" min={1} max={25} value={semanticLimit} onChange={(event) => setSemanticLimit(Number(event.target.value))} />
            </label>
            <label className="field">
              <span>Threshold</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={semanticThreshold}
                onChange={(event) => setSemanticThreshold(Number(event.target.value))}
              />
            </label>
          </div>
          <div className="toolbar-row">
            <button
              className="primary-button"
              type="button"
              disabled={activeAction === "search" || !semanticQuery.trim()}
              onClick={() =>
                void runAction("search", async () => {
                  const result = await semanticSearch({
                    tenantId: activeTenantId,
                    query: semanticQuery,
                    limit: semanticLimit,
                    threshold: semanticThreshold,
                    provider,
                    model,
                  });
                  setSemanticResults(result);
                  setSelectedPreviewPromptId(result[0]?.prompt_id ?? null);
                })
              }
            >
              {activeAction === "search" ? "Searching..." : "Run semantic search"}
            </button>
          </div>
          <div className="workspace-with-preview">
            <div className="results-stack">
              {semanticResults.map((row) => (
                <ResultRow
                  key={row.prompt_id}
                  row={row}
                  showMetadata
                  onSelectPrompt={setSelectedPreviewPromptId}
                  isSelected={selectedPreviewPromptId === row.prompt_id}
                />
              ))}
              {semanticResults.length === 0 ? (
                <div className="empty-state">Run a semantic query to see matches.</div>
              ) : null}
            </div>
            <PromptPreviewPane tenantId={activeTenantId} promptId={selectedPreviewPromptId} />
          </div>
        </section>
      ) : null}

      {tab === "clusters" ? (
        <section className="simple-panel">
          <div className="panel-header">
            <div>
              <h2>Duplicate Clusters</h2>
              <p>Show filtered global clusters first, then recompute scoped clusters by category, hierarchy, or prompt family.</p>
            </div>
          </div>
          <div className="form-grid">
            <label className="field">
              <span>Threshold</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={clusterThreshold}
                onChange={(event) => {
                  setClusterThreshold(Number(event.target.value));
                  resetMergeAnalysis();
                }}
              />
            </label>
            <label className="field">
              <span>Category filter</span>
              <select
                value={clusterCategoryFilter}
                onChange={(event) => {
                  setClusterCategoryFilter(event.target.value);
                  resetMergeAnalysis();
                }}
              >
                <option value="">All categories</option>
                {clusterCategories.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Hierarchy filter</span>
              <select
                value={clusterHierarchyFilter}
                onChange={(event) => {
                  setClusterHierarchyFilter(event.target.value);
                  resetMergeAnalysis();
                }}
              >
                <option value="">All hierarchy scopes</option>
                {clusterHierarchySegments.map((segment) => (
                  <option key={segment} value={segment}>
                    {segment}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Scoped mode</span>
              <select
                value={clusterScopeMode}
                onChange={(event) => {
                  setClusterScopeMode(event.target.value as DuplicateScopeMode);
                  resetMergeAnalysis();
                }}
              >
                <option value="category">category</option>
                <option value="hierarchy">hierarchy</option>
                <option value="prompt_family">prompt family</option>
              </select>
            </label>
          </div>
          <div className="toolbar-row">
            <button
              className="primary-button"
              type="button"
              disabled={activeAction === "clusters"}
              onClick={() =>
                void runAction("clusters", async () => {
                  const [globalResult, scopedResult] = await Promise.all([
                    createClusterRun({
                      tenantId: activeTenantId,
                      scope_mode: "global",
                      threshold: clusterThreshold,
                      provider,
                      model,
                      category_filter: clusterCategoryFilter || undefined,
                      hierarchy_filter: clusterHierarchyFilter || undefined,
                    }),
                    createClusterRun({
                      tenantId: activeTenantId,
                      scope_mode: clusterScopeMode,
                      threshold: clusterThreshold,
                      provider,
                      model,
                      category_filter: clusterCategoryFilter || undefined,
                      hierarchy_filter: clusterHierarchyFilter || undefined,
                    }),
                  ]);
                  const scopedGroups = groupClustersByScope(scopedResult.clusters, clusterScopeMode);
                  await queryClient.invalidateQueries({ queryKey: ["cluster-runs", activeTenantId] });
                  setGlobalClusterRun(globalResult);
                  setScopedClusterRun(scopedResult);
                  setSelectedGlobalRunId(globalResult.run_id);
                  setSelectedScopedRunId(scopedResult.run_id);
                  setGlobalDuplicateClusters(globalResult.clusters);
                  setScopedDuplicateGroups(scopedGroups);
                  setSelectedPreviewPromptId(
                    globalResult.clusters[0]?.prompts[0]?.prompt_id ??
                      scopedResult.clusters[0]?.prompts[0]?.prompt_id ??
                      null,
                  );
                  resetMergeAnalysis();
                })
              }
            >
              {activeAction === "clusters" ? "Loading..." : "Find duplicate clusters"}
            </button>
            <div className="scope-note">
              These controls define the next clustering run. If a run is already loaded, category and hierarchy also filter the visible cluster cards client-side until you rerun. Hierarchy is descendant-aware: `os` includes everything under `org.os`.
            </div>
          </div>
          <div className="result-panel">
            <div className="section-header">
              <div>
                <h3>Saved runs</h3>
                <div className="result-meta">
                  <span>{clusterRuns.length} runs for this tenant</span>
                  <span>Click a run to restore its filters and cluster results.</span>
                </div>
              </div>
            </div>
            <div className="saved-run-columns">
              <section className="saved-run-column">
                <div className="saved-run-column-header">
                  <strong>Global</strong>
                  <span>{globalRunSummaries.length} runs</span>
                </div>
                <div className="saved-run-list">
                  {globalRunSummaries.map((run) => (
                    <button
                      className={`saved-run-button ${selectedGlobalRunId === run.run_id ? "is-selected" : ""}`}
                      key={run.run_id}
                      type="button"
                      onClick={() => void loadSavedRun(run)}
                    >
                      <div className="result-row-top">
                        <strong>{run.run_id}</strong>
                        <span>{run.cluster_count} clusters</span>
                      </div>
                      <div className="result-meta">
                        <span>{formatRunTimestamp(run.created_at)}</span>
                        <span>threshold {formatScore(run.threshold)}</span>
                        {run.category_filter ? <span>category {run.category_filter}</span> : null}
                        {run.hierarchy_filter ? <span>hierarchy {run.hierarchy_filter}</span> : null}
                      </div>
                    </button>
                  ))}
                  {globalRunSummaries.length === 0 ? (
                    <div className="empty-state">No saved global runs yet.</div>
                  ) : null}
                </div>
              </section>
              <section className="saved-run-column">
                <div className="saved-run-column-header">
                  <strong>Scoped</strong>
                  <span>{scopedRunSummaries.length} runs</span>
                </div>
                <div className="saved-run-list">
                  {scopedRunSummaries.map((run) => (
                    <button
                      className={`saved-run-button ${selectedScopedRunId === run.run_id ? "is-selected" : ""}`}
                      key={run.run_id}
                      type="button"
                      onClick={() => void loadSavedRun(run)}
                    >
                      <div className="result-row-top">
                        <strong>{run.run_id}</strong>
                        <span>{run.cluster_count} clusters</span>
                      </div>
                      <div className="result-meta">
                        <span>{run.scope_mode.replace("_", " ")}</span>
                        <span>{formatRunTimestamp(run.created_at)}</span>
                        <span>threshold {formatScore(run.threshold)}</span>
                        {run.category_filter ? <span>category {run.category_filter}</span> : null}
                        {run.hierarchy_filter ? <span>hierarchy {run.hierarchy_filter}</span> : null}
                      </div>
                    </button>
                  ))}
                  {scopedRunSummaries.length === 0 ? (
                    <div className="empty-state">No saved scoped runs yet.</div>
                  ) : null}
                </div>
              </section>
            </div>
          </div>
          <div className="workspace-with-preview">
            <div className="results-stack">
              <div className="result-panel">
                <div className="section-header">
                  <div>
                    <h3>Global Reclustering</h3>
                    <div className="result-meta">
                      <span>{displayedGlobalDuplicateClusters.length} visible clusters</span>
                      {globalClusterRun ? <span>{globalClusterRun.cluster_count} clusters in saved run</span> : null}
                      {globalClusterRun ? <span>Run: {globalClusterRun.run_id}</span> : null}
                    </div>
                  </div>
                  <button
                    className="ghost-button"
                    type="button"
                    disabled={activeAction === "merge-analysis-global" || globalAnalyzableClusters.length === 0}
                    onClick={() =>
                      void runAction("merge-analysis-global", async () => {
                        const result = await analyzeMergeSuggestions({
                          tenantId: activeTenantId,
                          clusters: globalAnalyzableClusters,
                          scope_hierarchy: clusterHierarchyFilter || undefined,
                          scope_category: clusterCategoryFilter || undefined,
                        });
                        setMergeAnalysis(result);
                        setMergeAnalysisLabel("Global clusters");
                      })
                    }
                  >
                    {activeAction === "merge-analysis-global" ? "Analyzing..." : "Analyze global clusters"}
                  </button>
                </div>
                <div className="results-stack">
                  {displayedGlobalDuplicateClusters.map((cluster) => (
                    <ClusterCard
                      cluster={cluster}
                      key={cluster.cluster_id}
                      selectedPromptId={selectedPreviewPromptId ?? undefined}
                      onSelectPrompt={setSelectedPreviewPromptId}
                    />
                  ))}
                  {displayedGlobalDuplicateClusters.length === 0 ? (
                    <div className="empty-state">
                      {globalClusterRun
                        ? "No visible clusters match the current category or hierarchy filters."
                        : "Run duplicate analysis to see filtered global clusters."}
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="result-panel">
                <div className="section-header">
                  <div>
                    <h3>Scoped Reclustering</h3>
                    <div className="result-meta">
                      <span>Mode: {(scopedClusterRun?.scope_mode ?? clusterScopeMode).replace("_", " ")}</span>
                      <span>{displayedScopedDuplicateGroups.length} visible scope groups</span>
                      {scopedClusterRun ? <span>{scopedClusterRun.cluster_count} clusters in saved run</span> : null}
                      {scopedClusterRun ? <span>Run: {scopedClusterRun.run_id}</span> : null}
                    </div>
                  </div>
                  <button
                    className="ghost-button"
                    type="button"
                    disabled={activeAction === "merge-analysis-scoped" || scopedAnalyzableClusters.length === 0}
                    onClick={() =>
                      void runAction("merge-analysis-scoped", async () => {
                        const result = await analyzeMergeSuggestions({
                          tenantId: activeTenantId,
                          clusters: scopedAnalyzableClusters,
                          scope_hierarchy: clusterHierarchyFilter || undefined,
                          scope_category: clusterCategoryFilter || undefined,
                        });
                        setMergeAnalysis(result);
                        setMergeAnalysisLabel(`Scoped ${clusterScopeMode.replace("_", " ")}`);
                      })
                    }
                  >
                    {activeAction === "merge-analysis-scoped" ? "Analyzing..." : "Analyze scoped clusters"}
                  </button>
                </div>
                <div className="results-stack">
                  {displayedScopedDuplicateGroups.map((group) => (
                    <details className="scope-group-card" key={`${group.scope_type}-${group.scope_value}`} open>
                      <summary>
                        <span>{group.scope_value}</span>
                        <span>{group.clusters.length} clusters</span>
                      </summary>
                      <div className="scope-group-body">
                        <div className="result-meta">
                          <span>{group.prompt_count} prompts in scope</span>
                          <span>{group.scope_type.replace("_", " ")}</span>
                        </div>
                        <div className="results-stack">
                          {group.clusters.map((cluster) => (
                            <ClusterCard
                              cluster={cluster}
                              key={cluster.cluster_id}
                              selectedPromptId={selectedPreviewPromptId ?? undefined}
                              onSelectPrompt={setSelectedPreviewPromptId}
                            />
                          ))}
                        </div>
                      </div>
                    </details>
                  ))}
                  {displayedScopedDuplicateGroups.length === 0 ? (
                    <div className="empty-state">
                      {scopedClusterRun
                        ? "No visible scoped clusters match the current category or hierarchy filters."
                        : "Run duplicate analysis to see scoped reclustering groups."}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
            <PromptPreviewPane tenantId={activeTenantId} promptId={selectedPreviewPromptId} />
          </div>
          {mergeAnalysis ? (
            <div className="result-panel">
              <h3>Deep merge analysis</h3>
              <div className="result-meta">
                <span>Target: {mergeAnalysisLabel || "current view"}</span>
                <span>Hierarchy: {mergeAnalysis.scope.hierarchy ?? "all"}</span>
                <span>Category: {mergeAnalysis.scope.category ?? "all"}</span>
              </div>
              <div className="analysis-stack">
                {mergeAnalysis.results.map((result) => (
                  <article className="analysis-card" key={result.cluster_id}>
                    <div className="result-row-top">
                      <strong>{result.cluster_id}</strong>
                      {result.analysis ? <span>{formatScore(result.analysis.confidence)}</span> : null}
                    </div>
                    <div className="chip-strip">
                      {result.prompt_ids.map((promptId) => (
                        <span className="result-chip" key={`${result.cluster_id}-${promptId}`}>
                          {promptId}
                        </span>
                      ))}
                    </div>
                    {result.error ? <p>{result.error}</p> : null}
                    {result.analysis ? (
                      <>
                        <p>{result.analysis.reasoning}</p>
                        <div className="result-meta">
                          <span>Canonical: {result.analysis.canonical_prompt_id}</span>
                          <span>Can merge: {result.analysis.can_merge ? "yes" : "no"}</span>
                        </div>
                        <div className="analysis-block">
                          <strong>{result.analysis.merged_prompt_name}</strong>
                          <pre>{result.analysis.unified_prompt_template}</pre>
                        </div>
                        {result.analysis.differences_to_preserve.length > 0 ? (
                          <div className="analysis-list">
                            <strong>Differences to preserve</strong>
                            <ul>
                              {result.analysis.differences_to_preserve.map((item) => (
                                <li key={`${result.cluster_id}-${item}`}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {result.analysis.migration_steps.length > 0 ? (
                          <div className="analysis-list">
                            <strong>Migration steps</strong>
                            <ul>
                              {result.analysis.migration_steps.map((item) => (
                                <li key={`${result.cluster_id}-step-${item}`}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                      </>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {tab === "graph" ? (
        <section className="simple-panel">
          <div className="panel-header">
            <div>
              <h2>Graph Explorer</h2>
              <p>Explore the active tenant graph by category, hierarchy segment, layer path, and prompt id text.</p>
            </div>
          </div>
          <div className="form-grid">
            <label className="field">
              <span>View</span>
              <select value={graphView} onChange={(event) => setGraphView(event.target.value)}>
                <option value="global">global</option>
                <option value="category">category</option>
                <option value="hierarchy">hierarchy</option>
                <option value="layer_path">layer path</option>
                <option value="prompt_family">prompt family</option>
              </select>
            </label>
            <label className="field">
              <span>Category</span>
              <select value={graphCategoryFilter} onChange={(event) => setGraphCategoryFilter(event.target.value)}>
                <option value="">All categories</option>
                {clusterCategories.map((category) => (
                  <option key={`graph-${category}`} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Hierarchy</span>
              <select value={graphHierarchyFilter} onChange={(event) => setGraphHierarchyFilter(event.target.value)}>
                <option value="">All hierarchy segments</option>
                {clusterHierarchySegments.map((segment) => (
                  <option key={`hierarchy-${segment}`} value={segment}>
                    {segment}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Layer path</span>
              <input value={graphLayerPathFilter} onChange={(event) => setGraphLayerPathFilter(event.target.value)} placeholder="org.os.team.engine" />
            </label>
            <label className="field field-span">
              <span>Prompt query</span>
              <input value={graphPromptQuery} onChange={(event) => setGraphPromptQuery(event.target.value)} placeholder="verification.identity" />
            </label>
          </div>
          <div className="result-panel">
            <div className="result-meta">
              <span>Tenant: {activeTenantId}</span>
              <span>{explorerGraph?.summary.prompt_count ?? 0} prompts</span>
              <span>{explorerGraph?.summary.category_count ?? 0} categories</span>
            </div>
          </div>
          <GraphCanvas
            title="Tenant Graph"
            description="Prompt nodes are tenant-local. Layer taxonomy remains shared, but this view only renders the active tenant slice."
            elements={explorerElements}
            selectedPromptId={graphSelection ?? undefined}
            onPromptSelect={(promptId) => {
              setGraphSelection(promptId);
              const cleanedPromptId = promptId.startsWith("prompt:") ? promptId.replace(/^prompt:/, "") : promptId;
              setSelectedPreviewPromptId(cleanedPromptId);
            }}
          />
          <div className="workspace-with-preview">
            <div className="results-stack">
              {explorerQuery.isLoading ? <div className="empty-state">Loading tenant graph...</div> : null}
              {explorerQuery.isError ? <div className="empty-state">Unable to load the tenant graph.</div> : null}
              {!explorerQuery.isLoading && explorerElements.length === 0 ? (
                <div className="empty-state">No nodes matched the current tenant graph filters.</div>
              ) : null}
            </div>
            <PromptPreviewPane tenantId={activeTenantId} promptId={selectedPreviewPromptId} />
          </div>
        </section>
      ) : null}
    </main>
  );
}
