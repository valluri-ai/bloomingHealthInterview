"use client";

import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { Network, Orbit } from "lucide-react";
import { useEffect, useRef } from "react";

interface GraphCanvasProps {
  title: string;
  description: string;
  elements: ElementDefinition[];
  selectedPromptId?: string;
  selectedClusterId?: string;
  onPromptSelect: (promptId: string, clusterId?: string) => void;
}

export function GraphCanvas({
  title,
  description,
  elements,
  selectedPromptId,
  selectedClusterId,
  onPromptSelect,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      layout: {
        name: elements.length > 16 ? "cose" : "circle",
        animate: false,
        padding: 48,
      },
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            color: "#f2eee6",
            "font-size": "12px",
            "text-wrap": "wrap",
            "text-max-width": "110px",
            "font-family": "IBM Plex Sans, sans-serif",
            "background-color": "data(color)",
            width: "28px",
            height: "28px",
            "border-color": "#151819",
            "border-width": "2px",
          },
        },
        {
          selector: ".prompt-node",
          style: {
            shape: "ellipse",
          },
        },
        {
          selector: ".query-node",
          style: {
            shape: "round-rectangle",
            width: "150px",
            height: "50px",
            "font-style": "italic",
            "font-size": "13px",
          },
        },
        {
          selector: ".lineage-node",
          style: {
            shape: "diamond",
            width: "22px",
            height: "22px",
            color: "#d9c6a2",
            "font-size": "10px",
            "background-color": "#bc8e34",
          },
        },
        {
          selector: ".layer-node",
          style: {
            shape: "diamond",
            width: "24px",
            height: "24px",
            color: "#eefbff",
            "font-size": "10px",
            "background-color": "#27576b",
            "border-color": "#7fe7f2",
            "border-width": "2px",
            "text-outline-color": "#27576b",
            "text-outline-width": "2px",
          },
        },
        {
          selector: ".category-node",
          style: {
            shape: "round-rectangle",
            width: "110px",
            height: "38px",
            color: "#f6efe1",
            "font-size": "12px",
            "font-weight": "bold",
            "background-color": "#8d5f1f",
            "border-color": "#f4c871",
            "border-width": "2px",
            "text-outline-color": "#8d5f1f",
            "text-outline-width": "2px",
          },
        },
        {
          selector: ".family-node",
          style: {
            shape: "round-rectangle",
            width: "130px",
            height: "42px",
            color: "#eef6ef",
            "font-size": "11px",
            "font-weight": "bold",
            "background-color": "#2f5a3f",
            "border-color": "#a4f28b",
            "border-width": "2px",
            "text-outline-color": "#2f5a3f",
            "text-outline-width": "2px",
          },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(weight, 0, 1, 1.5, 6)",
            "line-color": "rgba(127, 231, 242, 0.35)",
            "target-arrow-shape": "none",
            label: "data(label)",
            color: "rgba(242, 238, 230, 0.6)",
            "font-size": "9px",
            "curve-style": "bezier",
          },
        },
        {
          selector: ".lineage-edge, .lineage-link-edge",
          style: {
            "line-style": "dashed",
            "line-color": "rgba(188, 142, 52, 0.36)",
            width: "1.2px",
          },
        },
        {
          selector: ".cluster-edge",
          style: {
            "line-style": "solid",
            "line-color": "rgba(127, 231, 242, 0.32)",
            width: "2px",
          },
        },
        {
          selector: ".is-selected",
          style: {
            "border-width": "4px",
            "border-color": "#f4c871",
            "overlay-color": "#f4c871",
            "overlay-opacity": 0.14,
            "overlay-padding": "12px",
          },
        },
        {
          selector: ".is-clustered",
          style: {
            "underlay-color": "#7fe7f2",
            "underlay-padding": "10px",
            "underlay-opacity": 0.08,
          },
        },
        {
          selector: ".is-muted",
          style: {
            opacity: 0.18,
          },
        },
      ],
    });

    cy.on("tap", "node", (event) => {
      const node = event.target;
      if (node.data("kind") !== "prompt") {
        return;
      }
      const clusterId = node.data("clusterId");
      onPromptSelect(node.id(), clusterId || undefined);
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [elements, onPromptSelect]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }

    cy.elements().removeClass("is-selected");
    cy.elements().removeClass("is-clustered");
    cy.elements().removeClass("is-muted");

    if (selectedClusterId) {
      cy.nodes().addClass("is-muted");
      cy.edges().addClass("is-muted");
      cy.nodes().forEach((node) => {
        if (node.data("clusterId") === selectedClusterId) {
          node.removeClass("is-muted");
          node.addClass("is-clustered");
        }
      });
      cy.edges().forEach((edge) => {
        if (edge.data("clusterId") === selectedClusterId) {
          edge.removeClass("is-muted");
        }
      });
    }

    if (selectedPromptId) {
      const selected = cy.getElementById(selectedPromptId);
      if (selected.nonempty()) {
        selected.removeClass("is-muted");
        selected.addClass("is-selected");
        cy.animate({ fit: { eles: selected.closedNeighborhood(), padding: 80 }, duration: 360 });
      }
    }
  }, [selectedPromptId, selectedClusterId]);

  return (
    <div className="graph-shell">
      <div className="graph-overlay">
        <div className="graph-kicker">
          <Orbit size={14} />
          Graph Layer
        </div>
        <div className="graph-heading-row">
          <div>
            <h2>{title}</h2>
            <p>{description}</p>
          </div>
          <div className="graph-stat-pill">
            <Network size={14} />
            {elements.filter((element) => "source" in (element.data ?? {})).length} edges
          </div>
        </div>
      </div>
      {elements.length === 0 ? (
        <div className="graph-empty">
          <p>No graph data for the current mode yet.</p>
          <span>Load prompts, generate embeddings, or pick another prompt to seed the view.</span>
        </div>
      ) : null}
      <div className="graph-canvas" ref={containerRef} />
    </div>
  );
}
