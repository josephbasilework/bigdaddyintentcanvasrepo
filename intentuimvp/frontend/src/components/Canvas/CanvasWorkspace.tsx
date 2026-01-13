"use client";

import { useEffect, useCallback, useState, useId, useRef } from "react";
import { createPortal } from "react-dom";
import {
  useCanvasStore,
  CanvasEdge,
  CanvasNode,
  CanvasEdgeRelationType,
  DAGData,
  DAGTask,
  PlanData,
} from "../../state/canvasStore";
import { Node } from "./Node";
import { EdgesLayer } from "./Edge";
import { EDGE_RELATION_OPTIONS, getEdgeRelationLabel } from "./edgeRelations";
import { useAutoSave } from "../../hooks/useAutoSave";
import { SaveStatusIndicator } from "./SaveStatusIndicator";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const NODE_TYPES: Set<CanvasNode["type"]> = new Set([
  "text",
  "document",
  "audio",
  "graph",
  "plan",
  "dag",
  "dashboard",
]);
const EDGE_STYLE_TYPES: Set<CanvasEdge["type"]> = new Set(["solid", "dashed", "dotted"]);
const EDGE_RELATION_TYPES: Set<CanvasEdgeRelationType> = new Set(
  EDGE_RELATION_OPTIONS.map((option) => option.value)
);
const DEFAULT_RELATION_TYPE: CanvasEdgeRelationType = "depends_on";
const DEFAULT_RELATION_LABEL = getEdgeRelationLabel(DEFAULT_RELATION_TYPE) ?? "Depends on";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const getString = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

const getNumber = (value: unknown, fallback: number): number =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;

const DAG_STATUS_VALUES = new Set<DAGTask["status"]>([
  "pending",
  "in_progress",
  "completed",
  "blocked",
]);
const DAG_PRIORITY_VALUES = new Set<DAGTask["priority"]>(["high", "medium", "low"]);
const DAG_DEPENDENCY_TYPES = new Set(["hard", "soft"]);

const normalizeText = (value: unknown): string | null => {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return null;
};

const normalizeTextArray = (value: unknown): string[] | undefined => {
  if (!Array.isArray(value)) return undefined;
  const items = value
    .map((item) => normalizeText(item))
    .filter((item): item is string => Boolean(item));
  return items.length > 0 ? items : [];
};

const normalizeDagStatus = (value: unknown): DAGTask["status"] => {
  const raw = normalizeText(value);
  if (!raw) return "pending";
  const normalized = raw.toLowerCase().replace(/\s+/g, "_");
  if (DAG_STATUS_VALUES.has(normalized as DAGTask["status"])) {
    return normalized as DAGTask["status"];
  }
  return "pending";
};

const normalizeDagPriority = (value: unknown): DAGTask["priority"] | undefined => {
  const raw = normalizeText(value);
  if (!raw) return undefined;
  const normalized = raw.toLowerCase();
  if (DAG_PRIORITY_VALUES.has(normalized as DAGTask["priority"])) {
    return normalized as DAGTask["priority"];
  }
  return undefined;
};

const normalizeDagDependencyType = (value: unknown): "hard" | "soft" | undefined => {
  const raw = normalizeText(value);
  if (!raw) return undefined;
  const normalized = raw.toLowerCase();
  return DAG_DEPENDENCY_TYPES.has(normalized)
    ? (normalized as "hard" | "soft")
    : undefined;
};

const normalizePlanData = (value: unknown): PlanData | undefined => {
  if (!isRecord(value)) return undefined;
  const goal = normalizeText(value.goal);
  const approach = normalizeText(value.approach);
  if (!goal || !approach) return undefined;

  const estimatedTotalEffort = normalizeText(
    value.estimatedTotalEffort ??
      value.estimated_total_effort ??
      value.estimated_effort
  );
  const assumptions = normalizeTextArray(value.assumptions);
  const risks = normalizeTextArray(value.risks);

  const plan: PlanData = { goal, approach };
  if (estimatedTotalEffort) plan.estimatedTotalEffort = estimatedTotalEffort;
  if (assumptions !== undefined) plan.assumptions = assumptions;
  if (risks !== undefined) plan.risks = risks;
  return plan;
};

const normalizeDagTask = (value: unknown): DAGTask | null => {
  if (!isRecord(value)) return null;
  const id = normalizeText(value.id ?? value.task_id ?? value.taskId);
  const title = normalizeText(value.title ?? value.name);
  if (!id || !title) return null;

  const description = normalizeText(value.description);
  const estimatedEffort = normalizeText(
    value.estimatedEffort ?? value.estimated_effort ?? value.estimated
  );
  const priority = normalizeDagPriority(value.priority);
  const status = normalizeDagStatus(value.status);
  const dependencies = normalizeTextArray(value.dependencies);

  const task: DAGTask = { id, title, status };
  if (description) task.description = description;
  if (priority) task.priority = priority;
  if (estimatedEffort) task.estimatedEffort = estimatedEffort;
  if (dependencies !== undefined) task.dependencies = dependencies;
  return task;
};

type DagDependency = NonNullable<DAGData["dependencies"]>[number];

const normalizeDagDependency = (value: unknown): DagDependency | null => {
  if (!isRecord(value)) return null;
  const taskId = normalizeText(value.taskId ?? value.task_id ?? value.taskID ?? value.task);
  const dependsOnTaskId = normalizeText(
    value.dependsOnTaskId ??
      value.depends_on_task_id ??
      value.dependsOn ??
      value.depends_on
  );
  if (!taskId || !dependsOnTaskId) return null;

  const type = normalizeDagDependencyType(
    value.type ?? value.dependency_type ?? value.dependencyType
  );

  const dependency: DagDependency = { taskId, dependsOnTaskId };
  if (type) dependency.type = type;
  return dependency;
};

const normalizeDagData = (value: unknown): DAGData | undefined => {
  if (!isRecord(value)) return undefined;
  if (!Array.isArray(value.tasks)) return undefined;

  const tasks = value.tasks.map(normalizeDagTask).filter(Boolean) as DAGTask[];
  const dependenciesRaw = Array.isArray(value.dependencies) ? value.dependencies : [];
  const dependencies = dependenciesRaw
    .map(normalizeDagDependency)
    .filter(Boolean) as DagDependency[];

  let resolvedDependencies = dependencies;
  if (resolvedDependencies.length === 0) {
    const derived = tasks.flatMap((task) => {
      if (!Array.isArray(task.dependencies) || task.dependencies.length === 0) {
        return [];
      }
      return task.dependencies
        .map((dependencyId) =>
          dependencyId
            ? { taskId: task.id, dependsOnTaskId: dependencyId, type: "hard" as const }
            : null
        )
        .filter(Boolean) as DagDependency[];
    });

    if (derived.length > 0) {
      resolvedDependencies = derived;
    }
  }

  const dag: DAGData = { tasks };
  if (resolvedDependencies.length > 0) {
    dag.dependencies = resolvedDependencies;
  }
  return dag;
};

export const normalizeNode = (value: unknown): CanvasNode | null => {
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

  const planData = [
    value.planData,
    value.plan_data,
    value.plan_metadata,
    value.planMetadata,
    value.plan,
    metadata?.planData,
    metadata?.plan_data,
    metadata?.plan_metadata,
    metadata?.planMetadata,
    metadata?.plan,
  ]
    .map(normalizePlanData)
    .find(Boolean);

  const dagData = [
    value.dagData,
    value.dag_data,
    value.task_dag,
    value.taskDag,
    value.dag,
    metadata?.dagData,
    metadata?.dag_data,
    metadata?.task_dag,
    metadata?.taskDag,
    metadata?.dag,
  ]
    .map(normalizeDagData)
    .find(Boolean);

  const node: CanvasNode = { id, type, x, y, z, title };
  if (content) node.content = content;
  if (metadata) node.metadata = metadata;
  if (planData) node.planData = planData;
  if (dagData) node.dagData = dagData;
  return node;
};

export const normalizeEdge = (value: unknown, index: number): CanvasEdge | null => {
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
  const type = typeValue && EDGE_STYLE_TYPES.has(typeValue as CanvasEdge["type"])
    ? (typeValue as CanvasEdge["type"])
    : undefined;

  const relationValue = getString(value.relationType ?? value.relation_type);
  const relationType = relationValue && EDGE_RELATION_TYPES.has(relationValue as CanvasEdgeRelationType)
    ? (relationValue as CanvasEdgeRelationType)
    : typeValue && EDGE_RELATION_TYPES.has(typeValue as CanvasEdgeRelationType)
      ? (typeValue as CanvasEdgeRelationType)
      : undefined;

  const edge: CanvasEdge = { id, sourceNodeId, targetNodeId };
  if (label) edge.label = label;
  if (type) edge.type = type;
  if (relationType) edge.relationType = relationType;
  return edge;
};

export const normalizeWorkspaceState = (
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
 * - Shift/Command-drag region selection
 */
export function CanvasWorkspace() {
  const {
    nodes,
    edges,
    clearSelection,
    setNodes,
    setEdges,
    addEdge,
    setSelectedNodes,
  } = useCanvasStore();
  const { saveStatus, saveError } = useAutoSave({
    debounceMs: 500,
    maxRetries: 3,
  });
  const [loadStatus, setLoadStatus] = useState<"loading" | "loaded" | "error">("loading");
  const [connectSourceNodeId, setConnectSourceNodeId] = useState<string | null>(null);
  const [connectRelationType, setConnectRelationType] = useState<CanvasEdgeRelationType>(
    DEFAULT_RELATION_TYPE
  );
  const [connectLabel, setConnectLabel] = useState(DEFAULT_RELATION_LABEL);
  const [connectLabelTouched, setConnectLabelTouched] = useState(false);
  const connectRelationId = useId();
  const connectLabelId = useId();
  const selectionStartRef = useRef<{
    x: number;
    y: number;
    mode: "replace" | "additive" | "toggle";
  } | null>(null);
  const selectionHandlersRef = useRef<{
    move?: (event: MouseEvent) => void;
    up?: (event: MouseEvent) => void;
  } | null>(null);
  const skipClickRef = useRef(false);
  const [selectionBox, setSelectionBox] = useState<{
    left: number;
    top: number;
    width: number;
    height: number;
  } | null>(null);

  const scheduleSkipClickReset = useCallback(() => {
    if (typeof window === "undefined") {
      skipClickRef.current = false;
      return;
    }

    window.setTimeout(() => {
      skipClickRef.current = false;
    }, 0);
  }, []);

  const handleCancelConnect = useCallback(() => {
    setConnectSourceNodeId(null);
  }, []);

  const handleStartConnect = useCallback((nodeId: string) => {
    setConnectSourceNodeId(nodeId);
    setConnectRelationType(DEFAULT_RELATION_TYPE);
    setConnectLabel(DEFAULT_RELATION_LABEL);
    setConnectLabelTouched(false);
  }, []);

  const handleConnectTarget = useCallback((targetNodeId: string) => {
    if (!connectSourceNodeId) return;

    if (connectSourceNodeId === targetNodeId) {
      setConnectSourceNodeId(null);
      return;
    }

    const hasEdge = edges.some(
      (edge) => edge.sourceNodeId === connectSourceNodeId && edge.targetNodeId === targetNodeId
    );

    if (!hasEdge) {
      const trimmedLabel = connectLabel.trim();
      const resolvedLabel = trimmedLabel || getEdgeRelationLabel(connectRelationType) || undefined;
      const edgePayload: Omit<CanvasEdge, "id"> = {
        sourceNodeId: connectSourceNodeId,
        targetNodeId,
        relationType: connectRelationType,
      };
      if (resolvedLabel) {
        edgePayload.label = resolvedLabel;
      }
      addEdge(edgePayload);
    }

    setConnectSourceNodeId(null);
  }, [addEdge, connectLabel, connectRelationType, connectSourceNodeId, edges]);

  const handleRelationTypeChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      const nextType = event.target.value as CanvasEdgeRelationType;
      setConnectRelationType(nextType);
      if (!connectLabelTouched) {
        setConnectLabel(getEdgeRelationLabel(nextType) ?? "");
      }
    },
    [connectLabelTouched]
  );

  const handleLabelChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    setConnectLabel(event.target.value);
    setConnectLabelTouched(true);
  }, []);

  const cleanupSelectionHandlers = useCallback(() => {
    if (!selectionHandlersRef.current) return;
    const { move, up } = selectionHandlersRef.current;
    if (move) {
      window.removeEventListener("mousemove", move);
    }
    if (up) {
      window.removeEventListener("mouseup", up);
    }
    selectionHandlersRef.current = null;
  }, []);

  const updateSelectionBox = useCallback((startX: number, startY: number, endX: number, endY: number) => {
    const left = Math.min(startX, endX);
    const top = Math.min(startY, endY);
    const width = Math.abs(endX - startX);
    const height = Math.abs(endY - startY);
    setSelectionBox({ left, top, width, height });
  }, []);

  const applyRegionSelection = useCallback((endX: number, endY: number) => {
    const start = selectionStartRef.current;
    if (!start) return;

    const left = Math.min(start.x, endX);
    const right = Math.max(start.x, endX);
    const top = Math.min(start.y, endY);
    const bottom = Math.max(start.y, endY);

    const nodeElements = Array.from(
      document.querySelectorAll<HTMLElement>("[data-node-id]")
    );
    const idsInRegion = nodeElements
      .map((element) => {
        const nodeId = element.dataset.nodeId;
        if (!nodeId) return null;
        const rect = element.getBoundingClientRect();
        const intersects =
          rect.right >= left &&
          rect.left <= right &&
          rect.bottom >= top &&
          rect.top <= bottom;
        return intersects ? nodeId : null;
      })
      .filter((id): id is string => Boolean(id));

    const state = useCanvasStore.getState();
    const currentSelection = state.selectedNodeIds.length > 0
      ? state.selectedNodeIds
      : state.selectedNodeId
        ? [state.selectedNodeId]
        : [];
    let nextSelection = idsInRegion;

    if (start.mode === "additive") {
      nextSelection = [...currentSelection, ...idsInRegion];
    } else if (start.mode === "toggle") {
      const nextSet = new Set(currentSelection);
      for (const id of idsInRegion) {
        if (nextSet.has(id)) {
          nextSet.delete(id);
        } else {
          nextSet.add(id);
        }
      }
      nextSelection = Array.from(nextSet);
    }

    const uniqueSelection = Array.from(new Set(nextSelection));
    setSelectedNodes(uniqueSelection);
  }, [setSelectedNodes]);

  useEffect(() => {
    if (connectSourceNodeId) return;
    setConnectRelationType(DEFAULT_RELATION_TYPE);
    setConnectLabel(DEFAULT_RELATION_LABEL);
    setConnectLabelTouched(false);
  }, [connectSourceNodeId]);

  useEffect(() => () => {
    cleanupSelectionHandlers();
  }, [cleanupSelectionHandlers]);

  useEffect(() => {
    if (!connectSourceNodeId) return;
    const sourceExists = nodes.some((node) => node.id === connectSourceNodeId);
    if (!sourceExists) {
      setConnectSourceNodeId(null);
    }
  }, [connectSourceNodeId, nodes]);

  useEffect(() => {
    if (!connectSourceNodeId) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setConnectSourceNodeId(null);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [connectSourceNodeId]);

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

  const handleCanvasMouseDown = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return;
    if (connectSourceNodeId) return;

    const isSelectionGesture = event.shiftKey || event.metaKey || event.ctrlKey;
    if (!isSelectionGesture) return;

    event.preventDefault();
    event.stopPropagation();
    skipClickRef.current = true;

    const mode = event.metaKey || event.ctrlKey ? "toggle" : "additive";
    selectionStartRef.current = { x: event.clientX, y: event.clientY, mode };
    updateSelectionBox(event.clientX, event.clientY, event.clientX, event.clientY);

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const start = selectionStartRef.current;
      if (!start) return;
      updateSelectionBox(start.x, start.y, moveEvent.clientX, moveEvent.clientY);
    };

    const handleMouseUp = (upEvent: MouseEvent) => {
      applyRegionSelection(upEvent.clientX, upEvent.clientY);
      selectionStartRef.current = null;
      setSelectionBox(null);
      cleanupSelectionHandlers();
      scheduleSkipClickReset();
    };

    selectionHandlersRef.current = {
      move: handleMouseMove,
      up: handleMouseUp,
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  }, [
    applyRegionSelection,
    cleanupSelectionHandlers,
    connectSourceNodeId,
    scheduleSkipClickReset,
    updateSelectionBox,
  ]);

  // Handle click on empty canvas area
  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    if (skipClickRef.current) {
      skipClickRef.current = false;
      return;
    }
    // Only clear selection if clicking directly on canvas (not on a node)
    if (e.target === e.currentTarget) {
      if (connectSourceNodeId) {
        setConnectSourceNodeId(null);
      }
      clearSelection();
    }
  }, [clearSelection, connectSourceNodeId]);

  const showEmptyState = loadStatus === "loaded" && nodes.length === 0 && edges.length === 0;
  const loadStatusMessage = (() => {
    switch (loadStatus) {
      case "loading":
        return "Loading canvas.";
      case "loaded":
        return showEmptyState ? "Canvas loaded. Workspace is empty." : "Canvas loaded.";
      case "error":
        return "Failed to load canvas.";
      default:
        return "";
    }
  })();

  const connectSourceNode = connectSourceNodeId
    ? nodes.find((node) => node.id === connectSourceNodeId)
    : null;
  const connectSourceLabel = connectSourceNode?.title ?? "node";
  const connectBanner = connectSourceNodeId && typeof document !== "undefined"
    ? createPortal(
      <div
        data-testid="connect-mode-banner"
        role="region"
        aria-label="Connect nodes"
        style={{
          position: "fixed",
          top: "16px",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 10002,
          backgroundColor: "rgba(15, 23, 42, 0.95)",
          border: "1px solid rgba(148, 163, 184, 0.4)",
          borderRadius: "12px",
          padding: "12px 16px",
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
          color: "#e2e8f0",
          boxShadow: "0 8px 18px rgba(0, 0, 0, 0.45)",
          maxWidth: "680px",
          width: "calc(100% - 32px)",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", flex: "1 1 320px" }}>
          <div style={{ fontSize: "11px", letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8" }}>
            Connect mode
          </div>
          <div style={{ fontSize: "14px", lineHeight: 1.4 }}>
            Connecting from <span style={{ fontWeight: 600 }}>{connectSourceLabel}</span>. Choose a relation and label, then select another node to create an edge.
          </div>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px", minWidth: "160px" }}>
              <label htmlFor={connectRelationId} style={{ fontSize: "11px", color: "#94a3b8" }}>
                Relation
              </label>
              <select
                id={connectRelationId}
                value={connectRelationType}
                onChange={handleRelationTypeChange}
                style={{
                  backgroundColor: "#0f172a",
                  border: "1px solid rgba(148, 163, 184, 0.45)",
                  borderRadius: "8px",
                  color: "#e2e8f0",
                  fontSize: "12px",
                  padding: "6px 10px",
                }}
              >
                {EDGE_RELATION_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px", flex: "1 1 220px" }}>
              <label htmlFor={connectLabelId} style={{ fontSize: "11px", color: "#94a3b8" }}>
                Edge label
              </label>
              <input
                id={connectLabelId}
                type="text"
                value={connectLabel}
                onChange={handleLabelChange}
                placeholder="Optional label"
                style={{
                  backgroundColor: "#0f172a",
                  border: "1px solid rgba(148, 163, 184, 0.45)",
                  borderRadius: "8px",
                  color: "#e2e8f0",
                  fontSize: "12px",
                  padding: "6px 10px",
                }}
              />
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={handleCancelConnect}
          style={{
            border: "1px solid rgba(148, 163, 184, 0.5)",
            backgroundColor: "transparent",
            color: "#e2e8f0",
            borderRadius: "999px",
            padding: "6px 12px",
            fontSize: "12px",
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          Cancel
        </button>
      </div>,
      document.body
    )
    : null;
  const selectionOverlay = selectionBox && typeof document !== "undefined"
    ? createPortal(
      <div
        aria-hidden="true"
        style={{
          position: "fixed",
          left: selectionBox.left,
          top: selectionBox.top,
          width: selectionBox.width,
          height: selectionBox.height,
          border: "1px solid rgba(96, 165, 250, 0.9)",
          backgroundColor: "rgba(96, 165, 250, 0.18)",
          borderRadius: "4px",
          pointerEvents: "none",
          zIndex: 10001,
        }}
      />,
      document.body
    )
    : null;

  return (
    <div
      data-testid="canvas-workspace"
      onMouseDown={handleCanvasMouseDown}
      onClick={handleCanvasClick}
      aria-busy={loadStatus === "loading"}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "auto",
      }}
    >
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {loadStatusMessage}
      </div>
      <EdgesLayer />
      {nodes.map((node) => (
        <Node
          key={node.id}
          node={node}
          onStartConnect={handleStartConnect}
          connectSourceNodeId={connectSourceNodeId}
          onConnectTarget={handleConnectTarget}
        />
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
                color: "#94a3b8",
              }}
            >
              Try: /plan, /research, or &quot;Outline our next sprint&quot;
            </div>
          </div>
        </div>
      )}
      {connectBanner}
      {selectionOverlay}
      <SaveStatusIndicator saveStatus={saveStatus} saveError={saveError} />
    </div>
  );
}
