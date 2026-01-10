"use client";

import { useEffect, useCallback, useState } from "react";
import { useCanvasStore, CanvasEdge, CanvasNode } from "../../state/canvasStore";
import { Node } from "./Node";
import { EdgesLayer } from "./Edge";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const NODE_TYPES: Set<CanvasNode["type"]> = new Set(["text", "document", "audio", "graph"]);
const EDGE_TYPES: Set<CanvasEdge["type"]> = new Set(["solid", "dashed", "dotted"]);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const getString = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

const getNumber = (value: unknown, fallback: number): number =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;

const normalizeNode = (value: unknown): CanvasNode | null => {
  if (!isRecord(value)) return null;

  const idValue = value.id ?? value.nodeId;
  if (idValue === undefined || idValue === null) return null;
  const id = typeof idValue === "string" ? idValue : String(idValue);

  const typeValue = getString(value.type);
  const type = typeValue && NODE_TYPES.has(typeValue as CanvasNode["type"])
    ? (typeValue as CanvasNode["type"])
    : "text";

  const position = isRecord(value.position) ? value.position : null;
  const x = getNumber(position?.x ?? value.x, 0);
  const y = getNumber(position?.y ?? value.y, 0);
  const z = getNumber(position?.z ?? value.z, 0);

  const titleValue = getString(value.title) ?? getString(value.label);
  const title = titleValue?.trim() || "Untitled";

  const content = getString(value.content);
  const metadataCandidate = value.metadata ?? value.node_metadata ?? value.nodeMetadata;
  const metadata = isRecord(metadataCandidate) ? metadataCandidate : undefined;

  const node: CanvasNode = { id, type, x, y, z, title };
  if (content) node.content = content;
  if (metadata) node.metadata = metadata;
  return node;
};

const normalizeEdge = (value: unknown, index: number): CanvasEdge | null => {
  if (!isRecord(value)) return null;

  const sourceValue = value.sourceNodeId ?? value.fromNodeId ?? value.from_node_id;
  const targetValue = value.targetNodeId ?? value.toNodeId ?? value.to_node_id;
  if (sourceValue === undefined || sourceValue === null) return null;
  if (targetValue === undefined || targetValue === null) return null;

  const sourceNodeId = typeof sourceValue === "string" ? sourceValue : String(sourceValue);
  const targetNodeId = typeof targetValue === "string" ? targetValue : String(targetValue);

  const idValue = value.id ?? `${sourceNodeId}-${targetNodeId}-${index}`;
  const id = typeof idValue === "string" ? idValue : String(idValue);

  const label = getString(value.label);
  const typeValue = getString(value.type);
  const type = typeValue && EDGE_TYPES.has(typeValue as CanvasEdge["type"])
    ? (typeValue as CanvasEdge["type"])
    : undefined;

  const edge: CanvasEdge = { id, sourceNodeId, targetNodeId };
  if (label) edge.label = label;
  if (type) edge.type = type;
  return edge;
};

const normalizeWorkspaceState = (
  value: unknown
): { nodes: CanvasNode[]; edges: CanvasEdge[]; hadCorruption: boolean } => {
  if (!isRecord(value)) {
    return { nodes: [], edges: [], hadCorruption: true };
  }

  const nodesRaw = value.nodes;
  if (!Array.isArray(nodesRaw)) {
    return { nodes: [], edges: [], hadCorruption: true };
  }

  const edgesRaw = value.edges;
  const edgesArray = Array.isArray(edgesRaw) ? edgesRaw : [];
  const edgesTypeInvalid = edgesRaw !== undefined && !Array.isArray(edgesRaw);

  const nodes = nodesRaw.map(normalizeNode).filter(Boolean) as CanvasNode[];
  const edges = edgesArray.map((edge, index) => normalizeEdge(edge, index)).filter(Boolean) as CanvasEdge[];

  const nodesInvalid = nodes.length !== nodesRaw.length;
  const edgesInvalid = edges.length !== edgesArray.length;
  const nodesMissing = nodesRaw.length > 0 && nodes.length === 0;

  return {
    nodes: nodesMissing ? [] : nodes,
    edges: nodesMissing ? [] : edges,
    hadCorruption: edgesTypeInvalid || nodesInvalid || edgesInvalid,
  };
};

/**
 * CanvasWorkspace component that renders all nodes on the canvas.
 *
 * Handles:
 * - Loading/saving canvas state from/to the backend API
 * - Rendering all nodes and edges from the store
 * - Clearing selection when clicking empty space
 */
export function CanvasWorkspace() {
  const { nodes, edges, clearSelection, setNodes, setEdges } = useCanvasStore();
  const [loadStatus, setLoadStatus] = useState<"loading" | "loaded" | "error">("loading");

  // Load canvas state on mount
  useEffect(() => {
    let isActive = true;
    const loadCanvas = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/workspace`);
        if (!response.ok) {
          throw new Error(`Workspace load failed: ${response.status}`);
        }

        const data = await response.json();
        const normalized = normalizeWorkspaceState(data);
        if (normalized.hadCorruption) {
          console.warn("Workspace state contained invalid data; recovered what we could.");
        }
        setNodes(normalized.nodes);
        setEdges(normalized.edges);
        if (isActive) {
          setLoadStatus("loaded");
        }
      } catch (error) {
        console.error("Failed to load canvas state:", error);
        if (isActive) {
          setLoadStatus("error");
        }
      }
    };

    loadCanvas();
    return () => {
      isActive = false;
    };
  }, [setNodes, setEdges]);

  // Save canvas state when nodes or edges change (debounced)
  useEffect(() => {
    if (nodes.length === 0 && edges.length === 0) return;

    const timeoutId = setTimeout(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/workspace`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ nodes, edges }),
        });

        if (!response.ok) {
          console.error("Failed to save canvas state");
        }
      } catch (error) {
        console.error("Failed to save canvas state:", error);
      }
    }, 500); // 500ms debounce

    return () => clearTimeout(timeoutId);
  }, [nodes, edges]);

  // Handle click on empty canvas area
  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    // Only clear selection if clicking directly on canvas (not on a node)
    if (e.target === e.currentTarget) {
      clearSelection();
    }
  }, [clearSelection]);

  const showEmptyState = loadStatus === "loaded" && nodes.length === 0 && edges.length === 0;

  return (
    <div
      onClick={handleCanvasClick}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "auto",
      }}
    >
      <EdgesLayer />
      {nodes.map((node) => (
        <Node key={node.id} node={node} />
      ))}
      {showEmptyState && (
        <div
          data-testid="empty-canvas-state"
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              maxWidth: "520px",
              padding: "20px 24px",
              borderRadius: "12px",
              backgroundColor: "rgba(15, 23, 42, 0.75)",
              border: "1px solid rgba(148, 163, 184, 0.2)",
              boxShadow: "0 12px 24px rgba(0, 0, 0, 0.35)",
              textAlign: "center",
            }}
          >
            <div
              style={{
                fontSize: "18px",
                fontWeight: 600,
                color: "#e2e8f0",
                marginBottom: "8px",
              }}
            >
              Your canvas is empty
            </div>
            <div
              style={{
                fontSize: "14px",
                color: "#94a3b8",
                lineHeight: 1.6,
              }}
            >
              Type a command in the box below to create your first node.
            </div>
            <div
              style={{
                marginTop: "10px",
                fontSize: "12px",
                color: "#64748b",
              }}
            >
              Try: /plan, /research, or &quot;Outline our next sprint&quot;
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
