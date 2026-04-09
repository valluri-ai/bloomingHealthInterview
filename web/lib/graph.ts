import type { ElementDefinition } from "cytoscape";

import type {
  ClusterVisualizationResponse,
  ExplorerGraphResponse,
  GraphMode,
  PromptGraphResponse,
  ScopeClustersResponse,
  SimilarPromptResult,
} from "@/lib/types";

interface BuildGraphSceneInput {
  mode: GraphMode;
  visualization?: ClusterVisualizationResponse;
  scopeData?: ScopeClustersResponse;
  promptGraph?: PromptGraphResponse;
  similarResults: SimilarPromptResult[];
  searchResults: SimilarPromptResult[];
  selectedPromptId?: string;
  selectedClusterId?: string;
  semanticQuery: string;
}

export interface GraphScene {
  elements: ElementDefinition[];
  title: string;
  description: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  survey: "#7fe7f2",
  form: "#ff946b",
  os: "#f5cb6f",
  common: "#f88379",
  receptionist: "#a4f28b",
  verification: "#9dc6ff",
};

function getCategoryColor(category?: string | null) {
  if (!category) {
    return "#c6bcae";
  }
  return CATEGORY_COLORS[category] ?? "#c6bcae";
}

function addPromptNode(
  nodes: Map<string, ElementDefinition>,
  input: {
    id: string;
    label: string;
    category?: string | null;
    layerPath?: string | null;
    clusterId?: string | null;
    promptParent?: string | null;
  },
) {
  if (nodes.has(input.id)) {
    return;
  }
  nodes.set(input.id, {
    data: {
      id: input.id,
      label: input.label,
      kind: "prompt",
      category: input.category ?? "",
      layerPath: input.layerPath ?? "",
      clusterId: input.clusterId ?? "",
      promptParent: input.promptParent ?? "",
      color: getCategoryColor(input.category),
    },
    classes: "prompt-node",
  });
}

function addLineage(
  nodes: Map<string, ElementDefinition>,
  edges: Map<string, ElementDefinition>,
  promptGraph?: PromptGraphResponse,
  selectedPromptId?: string,
) {
  if (!promptGraph || !selectedPromptId) {
    return;
  }

  const lineageGroups = [
    {
      prefix: "path",
      label: "Prompt Path",
      values: promptGraph.prompt_path_lineage,
      terminalValue: promptGraph.prompt_path_lineage.at(-1),
    },
    {
      prefix: "layer",
      label: "Layer",
      values: promptGraph.layer_lineage,
      terminalValue: promptGraph.layer_lineage.at(-1),
    },
    {
      prefix: "category",
      label: "Category",
      values: promptGraph.category_lineage,
      terminalValue: promptGraph.category_lineage.at(-1),
    },
  ];

  for (const group of lineageGroups) {
    let previousNodeId = "";
    for (const value of group.values) {
      const nodeId = `lineage:${group.prefix}:${value}`;
      if (!nodes.has(nodeId)) {
        nodes.set(nodeId, {
          data: {
            id: nodeId,
            label: value,
            kind: "lineage",
            lineageGroup: group.prefix,
            color: "#bc8e34",
          },
          classes: "lineage-node",
        });
      }
      if (previousNodeId) {
        const edgeId = `${previousNodeId}->${nodeId}`;
        if (!edges.has(edgeId)) {
          edges.set(edgeId, {
            data: {
              id: edgeId,
              source: previousNodeId,
              target: nodeId,
              kind: "lineage",
              label: group.label,
            },
            classes: "lineage-edge",
          });
        }
      }
      previousNodeId = nodeId;
    }

    if (group.terminalValue) {
      const edgeId = `${selectedPromptId}->lineage:${group.prefix}:${group.terminalValue}`;
      if (!edges.has(edgeId)) {
        edges.set(edgeId, {
          data: {
            id: edgeId,
            source: selectedPromptId,
            target: `lineage:${group.prefix}:${group.terminalValue}`,
            kind: "lineage-link",
            label: group.label,
          },
          classes: "lineage-link-edge",
        });
      }
    }
  }
}

function buildClusterScope(
  title: string,
  description: string,
  clusters: ScopeClustersResponse["category"]["clusters"],
  promptGraph?: PromptGraphResponse,
  selectedPromptId?: string,
) {
  const nodes = new Map<string, ElementDefinition>();
  const edges = new Map<string, ElementDefinition>();

  for (const cluster of clusters) {
    for (const prompt of cluster.prompts) {
      addPromptNode(nodes, {
        id: prompt.prompt_id,
        label: prompt.prompt_id,
        category: prompt.category,
        layerPath: prompt.layer_path,
        clusterId: cluster.cluster_id,
        promptParent: prompt.prompt_parent,
      });
    }
    for (const edge of cluster.edges) {
      const edgeId = `${edge.source}->${edge.target}`;
      edges.set(edgeId, {
        data: {
          id: edgeId,
          source: edge.source,
          target: edge.target,
          label: edge.similarity_score.toFixed(3),
          weight: edge.similarity_score,
          clusterId: cluster.cluster_id,
        },
        classes: "cluster-edge",
      });
    }
  }

  if (selectedPromptId && !nodes.has(selectedPromptId)) {
    addPromptNode(nodes, {
      id: selectedPromptId,
      label: selectedPromptId,
      category: promptGraph?.category,
      layerPath: promptGraph?.layer_path,
      promptParent: promptGraph?.prompt_parent,
    });
  }

  addLineage(nodes, edges, promptGraph, selectedPromptId);

  return {
    title,
    description,
    elements: [...nodes.values(), ...edges.values()],
  };
}

export function buildGraphScene({
  mode,
  visualization,
  scopeData,
  promptGraph,
  similarResults,
  searchResults,
  selectedPromptId,
  semanticQuery,
}: BuildGraphSceneInput): GraphScene {
  if (mode === "category" && scopeData) {
    return buildClusterScope(
      `Category Scope · ${scopeData.category.scope_value}`,
      "Clusters restricted to the selected prompt's category.",
      scopeData.category.clusters,
      promptGraph,
      selectedPromptId,
    );
  }

  if (mode === "layer" && scopeData) {
    return buildClusterScope(
      `Layer Scope · ${scopeData.layer.scope_value}`,
      "Clusters restricted to the selected prompt's layer lineage.",
      scopeData.layer.clusters,
      promptGraph,
      selectedPromptId,
    );
  }

  if (mode === "prompt_family" && scopeData) {
    return buildClusterScope(
      `Prompt Family Scope · ${scopeData.prompt_family.scope_value}`,
      "Clusters restricted to the selected prompt's prompt-path family.",
      scopeData.prompt_family.clusters,
      promptGraph,
      selectedPromptId,
    );
  }

  if (mode === "global") {
    const nodes = new Map<string, ElementDefinition>();
    const edges = new Map<string, ElementDefinition>();

    if (selectedPromptId) {
      addPromptNode(nodes, {
        id: selectedPromptId,
        label: selectedPromptId,
        category: promptGraph?.category,
        layerPath: promptGraph?.layer_path,
        promptParent: promptGraph?.prompt_parent,
      });
      for (const match of similarResults) {
        addPromptNode(nodes, {
          id: match.prompt_id,
          label: match.prompt_id,
          category: match.category,
          layerPath: match.layer_path,
          promptParent: match.prompt_parent,
        });
        edges.set(`${selectedPromptId}->${match.prompt_id}`, {
          data: {
            id: `${selectedPromptId}->${match.prompt_id}`,
            source: selectedPromptId,
            target: match.prompt_id,
            label: (match.similarity_score ?? match.ranking_score).toFixed(3),
            weight: match.similarity_score ?? match.ranking_score,
          },
          classes: "similarity-edge",
        });
      }
    } else if (searchResults.length > 0) {
      nodes.set("query", {
        data: {
          id: "query",
          label: semanticQuery,
          kind: "query",
          color: "#7fe7f2",
        },
        classes: "query-node",
      });
      for (const match of searchResults) {
        addPromptNode(nodes, {
          id: match.prompt_id,
          label: match.prompt_id,
          category: match.category,
          layerPath: match.layer_path,
          promptParent: match.prompt_parent,
        });
        edges.set(`query->${match.prompt_id}`, {
          data: {
            id: `query->${match.prompt_id}`,
            source: "query",
            target: match.prompt_id,
            label: match.ranking_score.toFixed(3),
            weight: match.ranking_score,
          },
          classes: "semantic-edge",
        });
      }
    }

    addLineage(nodes, edges, promptGraph, selectedPromptId);

    return {
      title: "Global Similarity",
      description:
        "Nearest semantic neighbors centered on the selected prompt or the last semantic search.",
      elements: [...nodes.values(), ...edges.values()],
    };
  }

  const nodes = new Map<string, ElementDefinition>();
  const edges = new Map<string, ElementDefinition>();
  if (visualization) {
    const clusterLookup = new Map<string, string>();
    for (const cluster of visualization.clusters) {
      for (const prompt of cluster.prompts) {
        clusterLookup.set(prompt.prompt_id, cluster.cluster_id);
      }
    }

    for (const node of visualization.nodes) {
      addPromptNode(nodes, {
        id: node.id,
        label: node.label,
        category: node.category,
        layerPath: node.layer_path,
        clusterId: clusterLookup.get(node.id),
        promptParent: node.prompt_parent,
      });
    }

    for (const edge of visualization.edges) {
      const edgeId = `${edge.source}->${edge.target}`;
      edges.set(edgeId, {
        data: {
          id: edgeId,
          source: edge.source,
          target: edge.target,
          label: edge.similarity_score.toFixed(3),
          weight: edge.similarity_score,
          sharedCategory: edge.shared_category,
          sharedLayer: edge.shared_layer_path,
          sharedFamily: edge.shared_prompt_path_parent,
        },
        classes: "cluster-edge",
      });
    }
  }

  if (selectedPromptId && !nodes.has(selectedPromptId)) {
    addPromptNode(nodes, {
      id: selectedPromptId,
      label: selectedPromptId,
      category: promptGraph?.category,
      layerPath: promptGraph?.layer_path,
      promptParent: promptGraph?.prompt_parent,
    });
  }

  addLineage(nodes, edges, promptGraph, selectedPromptId);

  return {
    title: "Duplicate Clusters",
    description:
      "Thresholded duplicate candidates from hybrid retrieval, augmented with the selected prompt's hierarchy.",
    elements: [...nodes.values(), ...edges.values()],
  };
}

export function buildExplorerGraphElements(graph?: ExplorerGraphResponse): ElementDefinition[] {
  if (!graph) {
    return [];
  }

  const nodes = new Map<string, ElementDefinition>();
  const edges = new Map<string, ElementDefinition>();

  for (const rawNode of graph.nodes) {
    const node = rawNode as Record<string, unknown>;
    const id = String(node.id);
    const kind = String(node.kind ?? "prompt");
    const category = typeof node.category === "string" ? node.category : null;
    const classes =
      kind === "prompt"
        ? "prompt-node"
        : kind === "category"
          ? "category-node"
          : kind === "layer"
            ? "layer-node"
            : kind === "prompt_family"
              ? "family-node"
              : "lineage-node";
    nodes.set(id, {
      data: {
        id,
        label: String(node.label ?? id),
        kind,
        category: category ?? "",
        layerPath: typeof node.layer_path === "string" ? node.layer_path : "",
        clusterId: "",
        promptParent: typeof node.prompt_parent === "string" ? node.prompt_parent : "",
        color:
          kind === "prompt"
            ? getCategoryColor(category)
            : kind === "category"
              ? "#f5cb6f"
              : kind === "layer"
                ? "#7fe7f2"
                : kind === "prompt_family"
                  ? "#a4f28b"
                  : "#bc8e34",
      },
      classes,
    });
  }

  for (const rawEdge of graph.edges) {
    const edge = rawEdge as Record<string, unknown>;
    const id = String(edge.id ?? `${edge.source}->${edge.target}`);
    const kind = typeof edge.kind === "string" ? edge.kind : "";
    const edgeClasses =
      kind === "layer_child" || kind === "contains_category"
        ? "lineage-edge"
        : "cluster-edge";
    edges.set(id, {
      data: {
        id,
        source: String(edge.source),
        target: String(edge.target),
        label: kind.replaceAll("_", " "),
        weight: 0.5,
      },
      classes: edgeClasses,
    });
  }

  return [...nodes.values(), ...edges.values()];
}
