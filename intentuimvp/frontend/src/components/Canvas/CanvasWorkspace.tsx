"use client";

import { useEffect, useCallback, useState, useId, useMemo, useRef } from "react";
import { createPortal } from "react-dom";
import {
  useCanvasStore,
  CanvasEdge,
  CanvasNode,
  CanvasEdgeRelationType,
  CanvasEdgeAnnotation,
  LayoutDirection,
  LayoutType,
  resolveNodeLayoutRegionInfo,
  DAGData,
  DAGTask,
  JobData,
  PlanData,
} from "../../state/canvasStore";
import { Node } from "./Node";
import { EdgesLayer } from "./Edge";
import { EdgeAnnotation } from "./EdgeAnnotation";
import {
  CUSTOM_EDGE_RELATION_VALUE,
  buildEdgeRelationOptions,
  getEdgeRelationLabel,
  normalizeEdgeRelationType,
} from "./edgeRelations";
import { resolveNodeTypeId } from "../../nodeTypes";
import { CanvasLayoutControls } from "./CanvasLayoutControls";
import {
  DEPENDENCY_CYCLE_MESSAGE,
  isDependencyRelationType,
  wouldCreateDependencyCycle,
} from "../../utils/dependencyCycles";
import { useAutoSave } from "../../hooks/useAutoSave";
import { SaveStatusIndicator } from "./SaveStatusIndicator";
import {
  buildHierarchyIndex,
  buildHiddenNodeSet,
  getNodeDepth,
  isContainerNode,
} from "../../utils/canvasHierarchy";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const EDGE_STYLE_TYPES: Set<CanvasEdge["type"]> = new Set(["solid", "dashed", "dotted"]);
const DEFAULT_RELATION_TYPE: CanvasEdgeRelationType = "dependency";
const DEFAULT_RELATION_LABEL = getEdgeRelationLabel(DEFAULT_RELATION_TYPE) ?? "Dependency";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const getString = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

const getNumber = (value: unknown, fallback: number): number =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;

const getOptionalNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

export const resolveCanvasMeta = (value: unknown): { id: number | null; name: string | null } => {
  if (!isRecord(value)) {
    return { id: null, name: null };
  }

  return {
    id: getOptionalNumber(value.id ?? value.canvasId ?? value.canvas_id),
    name: getString(value.name),
  };
};

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

const normalizeJobStatus = (value: unknown): string => {
  const raw = normalizeText(value);
  if (!raw) return "queued";
  return raw.toLowerCase().replace(/\s+/g, "_");
};

const normalizeJobType = (value: unknown): string => {
  const raw = normalizeText(value);
  if (!raw) return "unknown";
  if (raw.includes("_")) {
    return raw.toLowerCase();
  }
  const withUnderscores = raw
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/\s+/g, "_");
  return withUnderscores.toLowerCase();
};

const clampPercent = (value: number): number =>
  Math.min(100, Math.max(0, value));

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
  const statusUpdatedAt = normalizeText(
    value.statusUpdatedAt ?? value.status_updated_at ?? value.statusUpdated
  );
  const statusUpdatedBy = normalizeText(
    value.statusUpdatedBy ?? value.status_updated_by ?? value.statusUpdatedSource
  );
  const dependencies = normalizeTextArray(value.dependencies);
  const docCheckboxId = normalizeText(
    value.docCheckboxId ?? value.doc_checkbox_id ?? value.checkboxId ?? value.checkbox_id
  );
  const docTaskId = normalizeText(value.docTaskId ?? value.doc_task_id ?? value.docTask);
  const docDocumentId = normalizeText(
    value.docDocumentId ?? value.doc_document_id ?? value.documentId ?? value.document_id
  );
  const calendarSuggestionValue = value.calendarSuggestion ?? value.calendar_suggestion;
  const calendarSuggestion = isRecord(calendarSuggestionValue)
    ? calendarSuggestionValue
    : undefined;
  const calendarEventId = normalizeText(value.calendarEventId ?? value.calendar_event_id);
  const calendarEventUrl = normalizeText(
    value.calendarEventUrl ?? value.calendar_event_url
  );

  const task: DAGTask = { id, title, status };
  if (description) task.description = description;
  if (priority) task.priority = priority;
  if (estimatedEffort) task.estimatedEffort = estimatedEffort;
  if (statusUpdatedAt) task.statusUpdatedAt = statusUpdatedAt;
  if (statusUpdatedBy) task.statusUpdatedBy = statusUpdatedBy;
  if (dependencies !== undefined) task.dependencies = dependencies;
  if (docCheckboxId) task.docCheckboxId = docCheckboxId;
  if (docTaskId) task.docTaskId = docTaskId;
  if (docDocumentId) task.docDocumentId = docDocumentId;
  if (calendarSuggestion) task.calendarSuggestion = calendarSuggestion;
  if (calendarEventId) task.calendarEventId = calendarEventId;
  if (calendarEventUrl) task.calendarEventUrl = calendarEventUrl;
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

const normalizeJobData = (value: unknown): JobData | undefined => {
  if (!isRecord(value)) return undefined;

  const jobId = normalizeText(value.jobId ?? value.job_id ?? value.jobID ?? value.id);
  if (!jobId) return undefined;

  const jobType = normalizeJobType(value.jobType ?? value.job_type);
  const status = normalizeJobStatus(value.status);
  const progressRaw = getOptionalNumber(
    value.progressPercent ?? value.progress_percent
  );
  const progressPercent = clampPercent(progressRaw ?? 0);
  const currentStep = normalizeText(value.currentStep ?? value.current_step);
  const stepNumber = getOptionalNumber(value.stepNumber ?? value.step_number);
  const stepsTotal = getOptionalNumber(value.stepsTotal ?? value.steps_total);
  const data = isRecord(value.data) ? value.data : undefined;

  const jobData: JobData = {
    jobId,
    jobType,
    status,
    progressPercent,
  };

  if (currentStep) jobData.currentStep = currentStep;
  if (stepNumber !== null) jobData.stepNumber = stepNumber;
  if (stepsTotal !== null) jobData.stepsTotal = stepsTotal;
  if (data) jobData.data = data;

  return jobData;
};

export const normalizeNode = (value: unknown): CanvasNode | null => {
  if (!isRecord(value)) return null;

  const idValue = value.id ?? value.nodeId;
  if (idValue === undefined || idValue === null) return null;
  const id = typeof idValue === "string" ? idValue : String(idValue);

  const typeValue = getString(value.type);
  const resolvedType = resolveNodeTypeId(typeValue);

  const position = isRecord(value.position) ? value.position : null;
  const x = getNumber(position?.x ?? value.x, 0);
  const y = getNumber(position?.y ?? value.y, 0);
  const z = getNumber(position?.z ?? value.z, 0);

  const titleValue = getString(value.title) ?? getString(value.label);
  const title = titleValue?.trim() || "Untitled";

  const metadataCandidate = value.metadata ?? value.node_metadata ?? value.nodeMetadata;
  const metadata = isRecord(metadataCandidate) ? metadataCandidate : undefined;
  const content = getString(value.content) ?? getString(metadata?.content);

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

  const jobData = [
    value.jobData,
    value.job_data,
    value.job_metadata,
    value.jobMetadata,
    value.job,
    metadata?.jobData,
    metadata?.job_data,
    metadata?.job_metadata,
    metadata?.jobMetadata,
    metadata?.job,
  ]
    .map(normalizeJobData)
    .find(Boolean);

  const type: CanvasNode["type"] = jobData && resolvedType === "text" ? "job" : resolvedType;

  const node: CanvasNode = { id, type, x, y, z, title };
  if (content) node.content = content;
  if (metadata) node.metadata = metadata;
  if (planData) node.planData = planData;
  if (dagData) node.dagData = dagData;
  if (jobData) node.jobData = jobData;
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
  let relationType = normalizeEdgeRelationType(relationValue) ?? undefined;
  if (!relationType && typeValue && !EDGE_STYLE_TYPES.has(typeValue as CanvasEdge["type"])) {
    relationType = normalizeEdgeRelationType(typeValue) ?? undefined;
  }

  const metadataValue = value.metadata ?? value.edge_metadata ?? value.edgeMetadata;
  const metadata = isRecord(metadataValue) ? metadataValue : undefined;

  const edge: CanvasEdge = { id, sourceNodeId, targetNodeId };
  if (label) edge.label = label;
  if (type) edge.type = type;
  if (relationType) edge.relationType = relationType;
  if (metadata) edge.metadata = metadata;
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

type LayoutRegionEntry = {
  nodeIds: string[];
  layout?: LayoutType;
  locked?: boolean;
  direction?: LayoutDirection;
};

const collectLayoutRegions = (nodes: CanvasNode[]): Map<string, LayoutRegionEntry> => {
  const regions = new Map<string, LayoutRegionEntry>();
  nodes.forEach((node) => {
    const info = resolveNodeLayoutRegionInfo(node);
    if (!info) return;
    const existing = regions.get(info.regionId);
    if (existing) {
      existing.nodeIds.push(node.id);
      if (!existing.layout && info.layout) {
        existing.layout = info.layout;
      }
      if (existing.locked === undefined && info.locked !== undefined) {
        existing.locked = info.locked;
      }
      if (!existing.direction && info.direction) {
        existing.direction = info.direction;
      }
      return;
    }
    regions.set(info.regionId, {
      nodeIds: [node.id],
      ...(info.layout ? { layout: info.layout } : {}),
      ...(info.locked !== undefined ? { locked: info.locked } : {}),
      ...(info.direction ? { direction: info.direction } : {}),
    });
  });
  return regions;
};

const hasOverlappingPositions = (nodes: CanvasNode[]): boolean => {
  if (nodes.length < 2) return false;
  const counts = new Map<string, number>();
  nodes.forEach((node) => {
    const key = `${Math.round(node.x)}:${Math.round(node.y)}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  });
  const maxOverlap = Math.max(...counts.values());
  return maxOverlap >= Math.max(2, Math.ceil(nodes.length * 0.6));
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
    updateEdge,
    setSelectedNodes,
    setCanvasMeta,
    applyLayout,
  } = useCanvasStore();
  const { saveStatus, saveError } = useAutoSave({
    debounceMs: 500,
    maxRetries: 3,
  });
  const [loadStatus, setLoadStatus] = useState<"loading" | "loaded" | "error">("loading");
  const [connectSourceNodeId, setConnectSourceNodeId] = useState<string | null>(null);
  const [connectRelationSelection, setConnectRelationSelection] = useState<string>(
    DEFAULT_RELATION_TYPE
  );
  const [connectCustomRelationType, setConnectCustomRelationType] = useState("");
  const [connectLabel, setConnectLabel] = useState(DEFAULT_RELATION_LABEL);
  const [connectLabelTouched, setConnectLabelTouched] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [connectPreview, setConnectPreview] = useState<{ x: number; y: number } | null>(null);
  const [activeEdgeId, setActiveEdgeId] = useState<string | null>(null);
  const connectRelationId = useId();
  const connectCustomRelationId = useId();
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
  const connectDragRef = useRef<{ startX: number; startY: number; didDrag: boolean } | null>(null);
  const connectSourcePointRef = useRef<{ x: number; y: number } | null>(null);
  const skipClickRef = useRef(false);
  const [selectionBox, setSelectionBox] = useState<{
    left: number;
    top: number;
    width: number;
    height: number;
  } | null>(null);
  const hierarchyIndex = useMemo(() => buildHierarchyIndex(nodes), [nodes]);
  const hiddenNodeIds = useMemo(
    () => buildHiddenNodeSet(nodes, hierarchyIndex),
    [nodes, hierarchyIndex]
  );
  const visibleNodes = useMemo(
    () => nodes.filter((node) => !hiddenNodeIds.has(node.id)),
    [nodes, hiddenNodeIds]
  );
  const orderedNodes = useMemo(() => {
    const parentById = hierarchyIndex.parentById;
    return [...visibleNodes].sort((a, b) => {
      const depthA = getNodeDepth(a.id, parentById);
      const depthB = getNodeDepth(b.id, parentById);
      if (depthA !== depthB) {
        return depthA - depthB;
      }
      const aContainer = isContainerNode(a);
      const bContainer = isContainerNode(b);
      if (aContainer !== bContainer) {
        return aContainer ? -1 : 1;
      }
      return a.z - b.z;
    });
  }, [hierarchyIndex.parentById, visibleNodes]);

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
    setConnectError(null);
    setConnectPreview(null);
    connectDragRef.current = null;
    connectSourcePointRef.current = null;
  }, []);

  const handleStartConnect = useCallback((nodeId: string) => {
    setConnectSourceNodeId(nodeId);
    setConnectRelationSelection(DEFAULT_RELATION_TYPE);
    setConnectCustomRelationType("");
    setConnectLabel(DEFAULT_RELATION_LABEL);
    setConnectLabelTouched(false);
    setConnectError(null);
    setConnectPreview(null);
    connectDragRef.current = null;
    connectSourcePointRef.current = null;
  }, []);

  const findNodeIdFromPoint = useCallback((x: number, y: number): string | null => {
    if (typeof document === "undefined") return null;
    const element = document.elementFromPoint(x, y);
    if (!element) return null;
    const nodeElement = element.closest<HTMLElement>("[data-node-id]");
    return nodeElement?.dataset.nodeId ?? null;
  }, []);

  const handleConnectTarget = useCallback((targetNodeId: string) => {
    if (!connectSourceNodeId) return;

    if (connectSourceNodeId === targetNodeId) {
      setConnectError("Cannot connect a node to itself.");
      return;
    }

    const resolvedRelationType =
      connectRelationSelection === CUSTOM_EDGE_RELATION_VALUE
        ? normalizeEdgeRelationType(connectCustomRelationType)
        : normalizeEdgeRelationType(connectRelationSelection);

    if (!resolvedRelationType) {
      setConnectError("Choose an edge type to continue.");
      return;
    }

    const resolveEdgeLabel = (edge: CanvasEdge): string =>
      edge.label ?? getEdgeRelationLabel(edge.relationType) ?? "";

    const trimmedLabel = connectLabel.trim();
    const resolvedLabel =
      trimmedLabel || getEdgeRelationLabel(resolvedRelationType) || "";
    const duplicateEdge = edges.some(
      (edge) =>
        edge.sourceNodeId === connectSourceNodeId &&
        edge.targetNodeId === targetNodeId &&
        normalizeEdgeRelationType(edge.relationType ?? DEFAULT_RELATION_TYPE) ===
          resolvedRelationType &&
        resolveEdgeLabel(edge) === resolvedLabel
    );

    if (duplicateEdge) {
      setConnectError("An edge with this relation already exists.");
      return;
    }

    const candidateEdge: CanvasEdge = {
      id: `candidate-${connectSourceNodeId}-${targetNodeId}`,
      sourceNodeId: connectSourceNodeId,
      targetNodeId,
      relationType: resolvedRelationType,
      ...(resolvedLabel ? { label: resolvedLabel } : {}),
    };
    if (isDependencyRelationType(resolvedRelationType) &&
      wouldCreateDependencyCycle(edges, candidateEdge)
    ) {
      setConnectError(DEPENDENCY_CYCLE_MESSAGE);
      return;
    }

    const edgePayload: Omit<CanvasEdge, "id"> = {
      sourceNodeId: connectSourceNodeId,
      targetNodeId,
      relationType: resolvedRelationType,
      ...(resolvedLabel ? { label: resolvedLabel } : {}),
    };
    addEdge(edgePayload);

    setConnectSourceNodeId(null);
    setConnectError(null);
  }, [
    addEdge,
    connectCustomRelationType,
    connectLabel,
    connectRelationSelection,
    connectSourceNodeId,
    edges,
  ]);

  const handleStartConnectDrag = useCallback(
    (nodeId: string, event: React.PointerEvent<HTMLButtonElement>) => {
      event.preventDefault();
      event.stopPropagation();
      handleStartConnect(nodeId);

      connectDragRef.current = {
        startX: event.clientX,
        startY: event.clientY,
        didDrag: false,
      };

      if (typeof document !== "undefined") {
        const sourceElement = document.querySelector<HTMLElement>(`[data-node-id="${nodeId}"]`);
        if (sourceElement) {
          const rect = sourceElement.getBoundingClientRect();
          connectSourcePointRef.current = {
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
          };
        } else {
          connectSourcePointRef.current = { x: event.clientX, y: event.clientY };
        }
      }

      const handleMouseMove = (moveEvent: MouseEvent) => {
        const dragState = connectDragRef.current;
        if (!dragState) return;
        const dx = moveEvent.clientX - dragState.startX;
        const dy = moveEvent.clientY - dragState.startY;
        const distance = Math.hypot(dx, dy);
        if (distance > 6) {
          dragState.didDrag = true;
        }
        if (dragState.didDrag) {
          setConnectPreview({ x: moveEvent.clientX, y: moveEvent.clientY });
        }
      };

      const handleMouseUp = (upEvent: MouseEvent) => {
        window.removeEventListener("mousemove", handleMouseMove);
        const dragState = connectDragRef.current;
        connectDragRef.current = null;
        setConnectPreview(null);
        connectSourcePointRef.current = null;

        if (!dragState) return;
        if (!dragState.didDrag) {
          return;
        }

        const targetNodeId = findNodeIdFromPoint(upEvent.clientX, upEvent.clientY);
        if (targetNodeId) {
          handleConnectTarget(targetNodeId);
        } else {
          setConnectError("Drop on a node to connect.");
        }
      };

      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp, { once: true });
    },
    [findNodeIdFromPoint, handleConnectTarget, handleStartConnect]
  );

  const handleRelationTypeChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      const nextSelection = event.target.value;
      const trimmedLabel = connectLabel.trim();
      const currentType =
        connectRelationSelection === CUSTOM_EDGE_RELATION_VALUE
          ? normalizeEdgeRelationType(connectCustomRelationType)
          : normalizeEdgeRelationType(connectRelationSelection);
      const currentDefaultLabel = getEdgeRelationLabel(currentType) ?? "";
      const labelMatchesDefault =
        trimmedLabel === "" || trimmedLabel === currentDefaultLabel;
      setConnectRelationSelection(nextSelection);
      setConnectError(null);
      const nextType =
        nextSelection === CUSTOM_EDGE_RELATION_VALUE
          ? normalizeEdgeRelationType(connectCustomRelationType)
          : normalizeEdgeRelationType(nextSelection);
      if (!connectLabelTouched || labelMatchesDefault) {
        setConnectLabel(getEdgeRelationLabel(nextType) ?? "");
        setConnectLabelTouched(false);
      }
    },
    [
      connectCustomRelationType,
      connectLabel,
      connectLabelTouched,
      connectRelationSelection,
    ]
  );

  const handleCustomRelationTypeChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const nextValue = event.target.value;
      const trimmedLabel = connectLabel.trim();
      const currentDefaultLabel =
        getEdgeRelationLabel(normalizeEdgeRelationType(connectCustomRelationType)) ?? "";
      const labelMatchesDefault =
        trimmedLabel === "" || trimmedLabel === currentDefaultLabel;
      setConnectCustomRelationType(nextValue);
      setConnectError(null);
      if (!connectLabelTouched || labelMatchesDefault) {
        setConnectLabel(getEdgeRelationLabel(normalizeEdgeRelationType(nextValue)) ?? "");
        setConnectLabelTouched(false);
      }
    },
    [connectCustomRelationType, connectLabel, connectLabelTouched]
  );

  const handleLabelChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const nextValue = event.target.value;
      const trimmedValue = nextValue.trim();
      const resolvedType =
        connectRelationSelection === CUSTOM_EDGE_RELATION_VALUE
          ? normalizeEdgeRelationType(connectCustomRelationType)
          : normalizeEdgeRelationType(connectRelationSelection);
      const currentDefaultLabel = getEdgeRelationLabel(resolvedType) ?? "";
      const labelMatchesDefault =
        trimmedValue === "" || trimmedValue === currentDefaultLabel;
      setConnectLabel(nextValue);
      setConnectLabelTouched(!labelMatchesDefault);
      setConnectError(null);
    },
    [connectCustomRelationType, connectRelationSelection]
  );

  const handleAnnotateEdge = useCallback((edgeId: string) => {
    setActiveEdgeId(edgeId);
  }, []);

  const handleCloseEdgeAnnotation = useCallback(() => {
    setActiveEdgeId(null);
  }, []);

  const handleSaveEdgeAnnotation = useCallback(
    (annotation: CanvasEdgeAnnotation) => {
      if (!activeEdgeId) return;
      const edge = edges.find((item) => item.id === activeEdgeId);
      const nextMetadata = {
        ...(edge?.metadata ?? {}),
        annotation,
      };
      updateEdge(activeEdgeId, { metadata: nextMetadata });
      setActiveEdgeId(null);
    },
    [activeEdgeId, edges, updateEdge]
  );

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
    setConnectRelationSelection(DEFAULT_RELATION_TYPE);
    setConnectLabel(DEFAULT_RELATION_LABEL);
    setConnectLabelTouched(false);
    setConnectError(null);
    setConnectPreview(null);
    connectDragRef.current = null;
    connectSourcePointRef.current = null;
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
        const meta = resolveCanvasMeta(data);
        if (normalized.hadCorruption) {
          console.warn("Workspace state contained invalid data; recovered what we could.");
        }
        setCanvasMeta(meta);
        setNodes(normalized.nodes);
        setEdges(normalized.edges);
        if (isActive) {
          setLoadStatus("loaded");
        }
      } catch (error) {
        console.error("Failed to load canvas state:", error);
        if (isActive) {
          setCanvasMeta({ id: null, name: null });
          setLoadStatus("error");
        }
      }
    };

    loadCanvas();
    return () => {
      isActive = false;
    };
  }, [setCanvasMeta, setNodes, setEdges]);

  const layoutRegions = useMemo(() => collectLayoutRegions(nodes), [nodes]);
  const autoLayoutRef = useRef<Map<string, number>>(new Map());
  const importLayoutAppliedRef = useRef(false);

  useEffect(() => {
    if (loadStatus !== "loaded") return;
    layoutRegions.forEach((region, regionId) => {
      if (region.locked) {
        autoLayoutRef.current.set(regionId, region.nodeIds.length);
        return;
      }
      const prevCount = autoLayoutRef.current.get(regionId);
      if (prevCount === region.nodeIds.length) {
        return;
      }
      const regionNodes = region.nodeIds
        .map((nodeId) => nodes.find((node) => node.id === nodeId))
        .filter(Boolean) as CanvasNode[];
      if (regionNodes.length < 2 || !hasOverlappingPositions(regionNodes)) {
        autoLayoutRef.current.set(regionId, region.nodeIds.length);
        return;
      }
      applyLayout(
        {
          layout: region.layout ?? "grid",
          direction: region.direction ?? "down",
          nodeIds: region.nodeIds,
          regionId,
        },
        { source: "system", recordHistory: false, log: false }
      );
      autoLayoutRef.current.set(regionId, region.nodeIds.length);
    });
  }, [applyLayout, layoutRegions, loadStatus, nodes]);

  useEffect(() => {
    if (loadStatus !== "loaded" || importLayoutAppliedRef.current) return;
    if (layoutRegions.size > 0) {
      importLayoutAppliedRef.current = true;
      return;
    }
    if (nodes.length < 2 || !hasOverlappingPositions(nodes)) {
      importLayoutAppliedRef.current = true;
      return;
    }
    applyLayout(
      {
        layout: "grid",
        nodeIds: nodes.map((node) => node.id),
      },
      { source: "system", recordHistory: false, log: false }
    );
    importLayoutAppliedRef.current = true;
  }, [applyLayout, layoutRegions.size, loadStatus, nodes]);

  const handleCanvasMouseDown = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement | null;
    const isEdgeLayerClick =
      target instanceof SVGSVGElement && target.dataset.edgeLayer === "true";
    if (!isEdgeLayerClick && event.target !== event.currentTarget) return;
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
    const target = e.target as HTMLElement | null;
    const isEdgeLayerClick =
      target instanceof SVGSVGElement && target.dataset.edgeLayer === "true";
    // Only clear selection if clicking directly on canvas (not on a node)
    if (e.target === e.currentTarget || isEdgeLayerClick) {
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
  const connectRelationOptions = useMemo(() => {
    const customValues =
      connectRelationSelection === CUSTOM_EDGE_RELATION_VALUE
        ? [connectCustomRelationType]
        : [];
    return buildEdgeRelationOptions([
      ...edges.map((edge) => edge.relationType),
      ...customValues,
    ]);
  }, [connectCustomRelationType, connectRelationSelection, edges]);
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
            Connecting from <span style={{ fontWeight: 600 }}>{connectSourceLabel}</span>. Choose an edge type and label, then select another node to create an edge.
          </div>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px", minWidth: "160px" }}>
              <label htmlFor={connectRelationId} style={{ fontSize: "11px", color: "#94a3b8" }}>
                Edge type
              </label>
              <select
                id={connectRelationId}
                value={connectRelationSelection}
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
                {connectRelationOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
                <option value={CUSTOM_EDGE_RELATION_VALUE}>Custom...</option>
              </select>
            </div>
            {connectRelationSelection === CUSTOM_EDGE_RELATION_VALUE && (
              <div style={{ display: "flex", flexDirection: "column", gap: "4px", minWidth: "160px" }}>
                <label htmlFor={connectCustomRelationId} style={{ fontSize: "11px", color: "#94a3b8" }}>
                  Custom type
                </label>
                <input
                  id={connectCustomRelationId}
                  type="text"
                  value={connectCustomRelationType}
                  onChange={handleCustomRelationTypeChange}
                  placeholder="e.g., blocks"
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
            )}
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
          {connectError && (
            <div
              role="alert"
              style={{
                backgroundColor: "rgba(239, 68, 68, 0.15)",
                border: "1px solid rgba(239, 68, 68, 0.4)",
                borderRadius: "8px",
                color: "#fecaca",
                fontSize: "12px",
                padding: "8px 10px",
              }}
            >
              {connectError}
            </div>
          )}
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
  const activeEdge = activeEdgeId ? edges.find((edge) => edge.id === activeEdgeId) : null;
  const annotationValue = activeEdge?.metadata?.annotation;
  const activeAnnotation = isRecord(annotationValue)
    ? (annotationValue as CanvasEdgeAnnotation)
    : undefined;
  const activeEdgeLabel = activeEdge
    ? activeEdge.label ?? getEdgeRelationLabel(activeEdge.relationType) ?? "Edge"
    : "";
  const connectPreviewOverlay =
    connectPreview && connectSourcePointRef.current && typeof document !== "undefined"
      ? createPortal(
        <svg
          aria-hidden="true"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
            zIndex: 10000,
          }}
        >
          <line
            x1={connectSourcePointRef.current.x}
            y1={connectSourcePointRef.current.y}
            x2={connectPreview.x}
            y2={connectPreview.y}
            stroke="rgba(148, 163, 184, 0.9)"
            strokeWidth="2"
            strokeDasharray="6,6"
            strokeLinecap="round"
          />
          <circle
            cx={connectPreview.x}
            cy={connectPreview.y}
            r="4"
            fill="rgba(148, 163, 184, 0.9)"
          />
        </svg>,
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
      <EdgesLayer onAnnotate={handleAnnotateEdge} hiddenNodeIds={hiddenNodeIds} />
      {orderedNodes.map((node) => (
        <Node
          key={node.id}
          node={node}
          onStartConnect={handleStartConnect}
          onStartConnectDrag={handleStartConnectDrag}
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
      {connectPreviewOverlay}
      {connectBanner}
      {selectionOverlay}
      {activeEdge && (
        <EdgeAnnotation
          annotation={activeAnnotation}
          edgeLabel={activeEdgeLabel}
          onSave={handleSaveEdgeAnnotation}
          onCancel={handleCloseEdgeAnnotation}
        />
      )}
      <SaveStatusIndicator saveStatus={saveStatus} saveError={saveError} />
      <CanvasLayoutControls />
    </div>
  );
}
