import { create } from 'zustand';
import {
  createOfflineQueueId,
  shouldQueueOfflineRequest,
  type OfflineRequestData,
  useOfflineQueueStore,
} from './offlineQueueStore';
import { setLastSyncedTurnSequence } from '../utils/turnSequence';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SESSION_ID_STORAGE_KEY = "intentui_workspace_session_id";

type CanvasActionType =
  | "node_created"
  | "node_updated"
  | "node_deleted"
  | "edge_created"
  | "edge_updated"
  | "edge_deleted";

type CanvasActionSource = "user" | "remote" | "system";

type CanvasActionContext = {
  source?: CanvasActionSource;
  log?: boolean;
  recordHistory?: boolean;
};

/**
 * Graph node annotation data.
 * Used for graph-type nodes to provide structured metadata.
 */
export interface GraphNodeAnnotation {
  /** Bullet-point annotations for the node */
  bullets?: string[];
  /** Tags for categorization */
  tags?: string[];
  /** Status of the graph node */
  status?: 'active' | 'archived' | 'draft' | 'review';
}

// Types for canvas entities
export interface CanvasNode {
  id: string;
  type: 'text' | 'document' | 'audio' | 'graph' | 'plan' | 'dag' | 'dashboard' | 'job';
  x: number;
  y: number;
  z: number;
  title: string;
  content?: string;
  metadata?: Record<string, unknown>;
  /** Graph-specific annotations (only for type='graph') */
  graphAnnotation?: GraphNodeAnnotation;
  /** Plan-specific data (only for type='plan') */
  planData?: PlanData;
  /** DAG-specific data (only for type='dag') */
  dagData?: DAGData;
  /** Job-specific data (only for type='job') */
  jobData?: JobData;
  /** Turn ID that created this node (for agent-created nodes) */
  createdByTurnId?: number | null;
}

type NodeDimensions = {
  width: number;
  height: number;
};

const DEFAULT_NODE_DIMENSIONS: NodeDimensions = { width: 240, height: 140 };
const NODE_DIMENSIONS_BY_TYPE: Record<CanvasNode['type'], NodeDimensions> = {
  text: { width: 240, height: 140 },
  document: { width: 260, height: 160 },
  audio: { width: 300, height: 180 },
  graph: { width: 280, height: 170 },
  plan: { width: 320, height: 200 },
  dag: { width: 360, height: 220 },
  dashboard: { width: 360, height: 220 },
  job: { width: 300, height: 180 },
};

const AUTO_EXPAND_PADDING = 24;
export const AUTO_EXPAND_ANIMATION_MS = 240;

const getNodeDimensions = (node: { type: CanvasNode['type'] }): NodeDimensions =>
  NODE_DIMENSIONS_BY_TYPE[node.type] ?? DEFAULT_NODE_DIMENSIONS;

type NodeBounds = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  centerX: number;
  centerY: number;
};

const buildNodeBounds = (node: Pick<CanvasNode, 'x' | 'y' | 'type'>): NodeBounds => {
  const { width, height } = getNodeDimensions(node);
  const pad = AUTO_EXPAND_PADDING / 2;
  return {
    x1: node.x - pad,
    y1: node.y - pad,
    x2: node.x + width + pad,
    y2: node.y + height + pad,
    centerX: node.x + width / 2,
    centerY: node.y + height / 2,
  };
};

const boundsOverlap = (a: NodeBounds, b: NodeBounds): boolean =>
  !(a.x2 <= b.x1 || a.x1 >= b.x2 || a.y2 <= b.y1 || a.y1 >= b.y2);

const resolveAutoExpansion = (
  nodes: CanvasNode[],
  newNode: CanvasNode
): { nodes: CanvasNode[]; didExpand: boolean } => {
  const newBounds = buildNodeBounds(newNode);
  let didExpand = false;

  const expandedNodes = nodes.map((node) => {
    const bounds = buildNodeBounds(node);
    if (!boundsOverlap(newBounds, bounds)) {
      return node;
    }

    const dx = bounds.centerX - newBounds.centerX;
    const dy = bounds.centerY - newBounds.centerY;
    const distance = Math.hypot(dx, dy);
    let ux = 1;
    let uy = 0;
    if (distance > 0) {
      ux = dx / distance;
      uy = dy / distance;
    }

    const overlapX = dx >= 0 ? newBounds.x2 - bounds.x1 : bounds.x2 - newBounds.x1;
    const overlapY = dy >= 0 ? newBounds.y2 - bounds.y1 : bounds.y2 - newBounds.y1;
    const safeOverlapX = Math.max(0, overlapX);
    const safeOverlapY = Math.max(0, overlapY);

    const tX = Math.abs(ux) < 1e-6
      ? Number.POSITIVE_INFINITY
      : safeOverlapX / Math.abs(ux);
    const tY = Math.abs(uy) < 1e-6
      ? Number.POSITIVE_INFINITY
      : safeOverlapY / Math.abs(uy);
    const displacement = Math.min(tX, tY);

    if (!Number.isFinite(displacement) || displacement <= 0) {
      return node;
    }

    didExpand = true;
    return {
      ...node,
      x: node.x + ux * displacement,
      y: node.y + uy * displacement,
    };
  });

  return { nodes: expandedNodes, didExpand };
};

/**
 * Job metadata for job-type nodes.
 */
export interface JobData {
  /** Job ID from the backend */
  jobId: string;
  /** Job type (deep_research, perspective_gather, synthesis, etc.) */
  jobType: string;
  /** Job status (queued, in_progress, complete, failed, cancelled) */
  status: string;
  /** Progress percentage (0-100) */
  progressPercent: number;
  /** Current step description */
  currentStep?: string;
  /** Step number */
  stepNumber?: number;
  /** Total steps */
  stepsTotal?: number;
  /** Additional job data */
  data?: Record<string, unknown>;
}

/**
 * Plan metadata for plan-type nodes.
 */
export interface PlanData {
  goal: string;
  approach: string;
  estimatedTotalEffort?: string;
  assumptions?: string[];
  risks?: string[];
}

/**
 * Task data for DAG visualization.
 */
export interface DAGTask {
  id: string;
  title: string;
  description?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  priority?: 'high' | 'medium' | 'low';
  estimatedEffort?: string;
  dependencies?: string[];
  calendarSuggestion?: Record<string, unknown>;
  calendarEventId?: string;
  calendarEventUrl?: string;
}

/**
 * DAG data for dag-type nodes.
 */
export interface DAGData {
  tasks: DAGTask[];
  dependencies?: Array<{
    taskId: string;
    dependsOnTaskId: string;
    type?: 'hard' | 'soft';
  }>;
}

export type CanvasEdgeRelationType =
  | 'depends_on'
  | 'references'
  | 'supports'
  | 'conflicts'
  | 'derived_from'
  | 'critiques';

export interface CanvasEdge {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  label?: string;
  type?: 'solid' | 'dashed' | 'dotted';
  relationType?: CanvasEdgeRelationType;
}

export interface CanvasDocument {
  id: string;
  nodeId: string;
  title: string;
  content: string;
  createdAt: Date;
  updatedAt: Date;
}

const buildDocumentForNode = (
  node: CanvasNode,
  existing?: CanvasDocument,
  touchUpdatedAt: boolean = false
): CanvasDocument => {
  const createdAt = existing?.createdAt ?? new Date();
  const updatedAt = touchUpdatedAt ? new Date() : existing?.updatedAt ?? createdAt;
  return {
    id: existing?.id ?? node.id,
    nodeId: node.id,
    title: node.title || existing?.title || "Untitled",
    content: node.content ?? existing?.content ?? "",
    createdAt,
    updatedAt,
  };
};

const syncDocumentsWithNodes = (
  nodes: CanvasNode[],
  documents: CanvasDocument[]
): CanvasDocument[] => {
  const docsByNodeId = new Map(documents.map((doc) => [doc.nodeId, doc]));
  return nodes
    .filter((node) => node.type === "document")
    .map((node) => buildDocumentForNode(node, docsByNodeId.get(node.id)));
};

export type NodeSelectionOptions = {
  additive?: boolean;
  toggle?: boolean;
};

const getOrCreateSessionId = (): string | null => {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const stored = localStorage.getItem(SESSION_ID_STORAGE_KEY);
    if (stored) {
      return stored;
    }
    const newSessionId =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(SESSION_ID_STORAGE_KEY, newSessionId);
    return newSessionId;
  } catch {
    return null;
  }
};

const resolveActionContext = (context?: CanvasActionContext) => {
  const source = context?.source ?? "user";
  const recordHistory = context?.recordHistory ?? source === "user";
  const shouldLog = context?.log === false ? false : source === "user";
  return { recordHistory, shouldLog };
};

const buildNodePayload = (node: CanvasNode): Record<string, unknown> => ({
  id: node.id,
  type: node.type,
  title: node.title,
  label: node.title,
  content: node.content,
  x: node.x,
  y: node.y,
  z: node.z,
  position: { x: node.x, y: node.y, z: node.z },
  metadata: node.metadata,
  createdByTurnId: node.createdByTurnId,
});

const buildEdgePayload = (edge: CanvasEdge): Record<string, unknown> => ({
  id: edge.id,
  sourceNodeId: edge.sourceNodeId,
  targetNodeId: edge.targetNodeId,
  fromNodeId: edge.sourceNodeId,
  toNodeId: edge.targetNodeId,
  relationType: edge.relationType,
  label: edge.label,
});

const extractSequenceNumber = (payload: unknown): number | null => {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const candidate = payload as { sequenceNumber?: unknown; sequence_number?: unknown };
  if (typeof candidate.sequenceNumber === "number") {
    return candidate.sequenceNumber;
  }
  if (typeof candidate.sequence_number === "number") {
    return candidate.sequence_number;
  }
  return null;
};

const logCanvasAction = (
  action: CanvasActionType,
  payload: Record<string, unknown>,
  options: { summary?: string; workspaceId?: number | null } = {}
) => {
  if (typeof process !== "undefined" && process.env.NODE_ENV === "test") {
    return;
  }
  if (typeof fetch !== "function") {
    return;
  }
  const sessionId = getOrCreateSessionId();
  const clientRequestId = createOfflineQueueId();
  const body: Record<string, unknown> = {
    action,
    payload,
    client_request_id: clientRequestId,
  };
  if (sessionId) {
    body.session_id = sessionId;
  }
  if (options.workspaceId !== null && options.workspaceId !== undefined) {
    body.workspace_id = options.workspaceId;
  }
  if (options.summary) {
    body.summary = options.summary;
  }

  const request: OfflineRequestData = {
    url: `${API_BASE_URL}/api/canvas/actions`,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    kind: "canvas_action",
    sessionId: sessionId ?? "",
  };

  const offlineState = useOfflineQueueStore.getState();
  const isNavigatorOnline =
    typeof navigator === "undefined" ? true : navigator.onLine;
  const shouldQueue = !isNavigatorOnline || shouldQueueOfflineRequest(offlineState);

  if (sessionId && shouldQueue) {
    offlineState.enqueue(request, { id: clientRequestId });
    return;
  }

  void fetch(request.url, {
    method: request.method,
    headers: request.headers,
    body: JSON.stringify(body),
  })
    .then(async (response) => {
      if (!response.ok) {
        const error = new Error(
          `Canvas action failed: ${response.status} ${response.statusText}`
        ) as Error & { status?: number };
        error.status = response.status;
        throw error;
      }
      try {
        const data = await response.json();
        const sequenceNumber = extractSequenceNumber(data);
        if (sessionId && sequenceNumber !== null) {
          setLastSyncedTurnSequence(sessionId, sequenceNumber);
        }
      } catch {
        // ignore response parsing errors
      }
    })
    .catch((error) => {
      const status = typeof (error as { status?: number })?.status === "number"
        ? (error as { status?: number }).status
        : undefined;
      if (sessionId && (status === undefined || status >= 500)) {
        useOfflineQueueStore.getState().enqueue(request, { id: clientRequestId });
      }
      console.warn("Failed to log canvas action:", error);
    });
};

// History snapshot type
interface CanvasSnapshot {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  documents: CanvasDocument[];
}

// Store state interface
interface CanvasState {
  canvasId: number | null;
  canvasName: string | null;
  // State
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  documents: CanvasDocument[];
  selectedNodeId: string | null;
  selectedNodeIds: string[];
  isAutoExpanding: boolean;

  // History state
  past: CanvasSnapshot[];
  future: CanvasSnapshot[];

  // Actions
  addNode: (
    node: Omit<CanvasNode, 'id'> & { id?: string },
    context?: CanvasActionContext
  ) => string;
  setCanvasMeta: (meta: { id?: number | null; name?: string | null }) => void;
  removeNode: (nodeId: string, context?: CanvasActionContext) => void;
  removeNodes: (nodeIds: string[], context?: CanvasActionContext) => void;
  updateNodePosition: (
    nodeId: string,
    x: number,
    y: number,
    z?: number,
    context?: CanvasActionContext
  ) => void;
  selectNode: (nodeId: string | null, options?: NodeSelectionOptions) => void;
  setSelectedNodes: (nodeIds: string[]) => void;
  updateNode: (
    nodeId: string,
    updates: Partial<CanvasNode>,
    context?: CanvasActionContext
  ) => void;
  clearSelection: () => void;
  setNodes: (nodes: CanvasNode[]) => void;
  addEdge: (
    edge: Omit<CanvasEdge, 'id'> & { id?: string },
    context?: CanvasActionContext
  ) => string;
  removeEdge: (edgeId: string, context?: CanvasActionContext) => void;
  updateEdge: (
    edgeId: string,
    updates: Partial<CanvasEdge>,
    context?: CanvasActionContext
  ) => void;
  setEdges: (edges: CanvasEdge[]) => void;

  // History actions
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  clearHistory: () => void;

  // Turn attribution actions
  getNodesByTurnId: (turnId: number) => CanvasNode[];
  removeNodesByTurnId: (turnId: number, context?: CanvasActionContext) => string[];
}

// Create the store
export const useCanvasStore = create<CanvasState>((set, get) => {
  // Helper to apply updates with optional history tracking
  const applyUpdate = (
    updater: (state: CanvasState) => Partial<CanvasState>,
    recordHistory: boolean
  ) => {
    if (!recordHistory) {
      set((state) => updater(state));
      return;
    }
    set((state) => {
      const snapshot: CanvasSnapshot = {
        nodes: state.nodes,
        edges: state.edges,
        documents: state.documents,
      };
      const update = updater(state);
      return {
        ...update,
        past: [...state.past.slice(-49), snapshot], // Keep last 50
        future: [], // Clear future on new action
      };
    });
  };

  let autoExpandTimer: ReturnType<typeof setTimeout> | null = null;

  return {
    // Initial state
    canvasId: null,
    canvasName: null,
    nodes: [],
    edges: [],
    documents: [],
    selectedNodeId: null,
    selectedNodeIds: [],
    isAutoExpanding: false,
    past: [],
    future: [],

    // Add a new node to the canvas
    addNode: (node, context) => {
      const { recordHistory, shouldLog } = resolveActionContext(context);
      const id = node.id ?? `node-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const newNode: CanvasNode = {
        ...node,
        id,
      };
      let didExpand = false;
      applyUpdate((state) => {
        const expansion = resolveAutoExpansion(state.nodes, newNode);
        didExpand = expansion.didExpand;
        let nextDocuments = state.documents;
        if (newNode.type === "document") {
          const existingDoc = state.documents.find((doc) => doc.nodeId === newNode.id);
          if (existingDoc) {
            nextDocuments = state.documents.map((doc) =>
              doc.nodeId === newNode.id ? buildDocumentForNode(newNode, existingDoc) : doc
            );
          } else {
            nextDocuments = [...state.documents, buildDocumentForNode(newNode)];
          }
        }
        return {
          nodes: [...expansion.nodes, newNode],
          documents: nextDocuments,
          ...(didExpand ? { isAutoExpanding: true } : {}),
        };
      }, recordHistory);
      if (didExpand) {
        if (autoExpandTimer) {
          clearTimeout(autoExpandTimer);
        }
        autoExpandTimer = setTimeout(() => {
          set({ isAutoExpanding: false });
        }, AUTO_EXPAND_ANIMATION_MS);
      }
      if (shouldLog) {
        const summary = newNode.title ? `Node created: ${newNode.title}` : "Node created";
        logCanvasAction(
          "node_created",
          { node: buildNodePayload(newNode) },
          { summary, workspaceId: get().canvasId }
        );
      }
      return id;
    },

    setCanvasMeta: (meta) => {
      set((state) => ({
        canvasId: meta.id === undefined ? state.canvasId : meta.id,
        canvasName: meta.name === undefined ? state.canvasName : meta.name,
      }));
    },

    // Remove a node from the canvas
    removeNode: (nodeId, context) => {
      const { recordHistory, shouldLog } = resolveActionContext(context);
      const existingNode = get().nodes.find((node) => node.id === nodeId);
      const relatedEdges = get().edges.filter(
        (edge) => edge.sourceNodeId === nodeId || edge.targetNodeId === nodeId
      );
      applyUpdate((state) => {
        const nextSelectedIds = state.selectedNodeIds.filter((id) => id !== nodeId);
        let nextSelectedNodeId = state.selectedNodeId;
        if (nextSelectedNodeId === nodeId) {
          nextSelectedNodeId = nextSelectedIds.length > 0 ? nextSelectedIds[0] : null;
        }
        return {
          nodes: state.nodes.filter((node) => node.id !== nodeId),
          edges: state.edges.filter(
            (edge) => edge.sourceNodeId !== nodeId && edge.targetNodeId !== nodeId
          ),
          documents: state.documents.filter((doc) => doc.nodeId !== nodeId),
          selectedNodeIds: nextSelectedIds,
          selectedNodeId: nextSelectedNodeId,
        };
      }, recordHistory);
      if (shouldLog) {
        const summary = existingNode?.title
          ? `Node deleted: ${existingNode.title}`
          : "Node deleted";
        logCanvasAction(
          "node_deleted",
          {
            node: existingNode ? buildNodePayload(existingNode) : { id: nodeId },
            edges: relatedEdges.map(buildEdgePayload),
          },
          { summary, workspaceId: get().canvasId }
        );
      }
    },

    // Remove multiple nodes from the canvas
    removeNodes: (nodeIds, context) => {
      const { recordHistory, shouldLog } = resolveActionContext(context);
      const uniqueIds = Array.from(new Set(nodeIds)).filter(Boolean);
      if (uniqueIds.length === 0) return;
      const idsToRemove = new Set(uniqueIds);
      const existingNodes = get().nodes.filter((node) => idsToRemove.has(node.id));
      const relatedEdges = get().edges.filter(
        (edge) => idsToRemove.has(edge.sourceNodeId) || idsToRemove.has(edge.targetNodeId)
      );
      applyUpdate((state) => {
        const nextSelectedIds = state.selectedNodeIds.filter((id) => !idsToRemove.has(id));
        let nextSelectedNodeId = state.selectedNodeId;
        if (nextSelectedNodeId && idsToRemove.has(nextSelectedNodeId)) {
          nextSelectedNodeId = null;
        }
        if (!nextSelectedNodeId && nextSelectedIds.length > 0) {
          nextSelectedNodeId = nextSelectedIds[0];
        }
        return {
          nodes: state.nodes.filter((node) => !idsToRemove.has(node.id)),
          edges: state.edges.filter(
            (edge) => !idsToRemove.has(edge.sourceNodeId) && !idsToRemove.has(edge.targetNodeId)
          ),
          documents: state.documents.filter((doc) => !idsToRemove.has(doc.nodeId)),
          selectedNodeId: nextSelectedNodeId,
          selectedNodeIds: nextSelectedIds,
        };
      }, recordHistory);
      if (shouldLog) {
        existingNodes.forEach((node) => {
          const summary = node.title ? `Node deleted: ${node.title}` : "Node deleted";
          const nodeEdges = relatedEdges.filter(
            (edge) => edge.sourceNodeId === node.id || edge.targetNodeId === node.id
          );
          logCanvasAction(
            "node_deleted",
            {
              node: buildNodePayload(node),
              edges: nodeEdges.map(buildEdgePayload),
            },
            { summary, workspaceId: get().canvasId }
          );
        });
      }
    },

    // Update node position
    updateNodePosition: (nodeId, x, y, z, context) => {
      const { recordHistory, shouldLog } = resolveActionContext(context);
      const existingNode = get().nodes.find((node) => node.id === nodeId);
      const nextZ = z ?? existingNode?.z ?? 0;
      applyUpdate((state) => ({
        nodes: state.nodes.map((node) =>
          node.id === nodeId
            ? { ...node, x, y, ...(z !== undefined && { z }) }
            : node
        ),
      }), recordHistory);
      if (shouldLog && existingNode) {
        const nextNode = { ...existingNode, x, y, z: nextZ };
        logCanvasAction(
          "node_updated",
          {
            node: buildNodePayload(nextNode),
            updates: { position: { x, y, z: nextZ }, x, y, z: nextZ },
            previous: { x: existingNode.x, y: existingNode.y, z: existingNode.z },
          },
          { summary: "Node moved", workspaceId: get().canvasId }
        );
      }
    },

    // Select a node
    selectNode: (nodeId, options) => {
      set((state) => {
        if (!nodeId) {
          return {
            selectedNodeId: null,
            selectedNodeIds: [],
          };
        }

        const { additive, toggle } = options ?? {};
        if (!additive && !toggle) {
          return {
            selectedNodeId: nodeId,
            selectedNodeIds: [nodeId],
          };
        }

        const currentIds = state.selectedNodeIds.length > 0
          ? state.selectedNodeIds
          : state.selectedNodeId
            ? [state.selectedNodeId]
            : [];
        const uniqueIds = Array.from(new Set(currentIds));
        const isSelected = uniqueIds.includes(nodeId);
        let nextSelectedIds = uniqueIds;

        if (toggle) {
          nextSelectedIds = isSelected
            ? uniqueIds.filter((id) => id !== nodeId)
            : [...uniqueIds, nodeId];
        } else if (additive) {
          nextSelectedIds = isSelected ? uniqueIds : [...uniqueIds, nodeId];
        }

        const nextSelectedNodeId = nextSelectedIds.length === 0
          ? null
          : nextSelectedIds.includes(nodeId)
            ? nodeId
            : nextSelectedIds[0];

        return {
          selectedNodeId: nextSelectedNodeId,
          selectedNodeIds: nextSelectedIds,
        };
      });
    },

    // Select multiple nodes at once
    setSelectedNodes: (nodeIds) => {
      const uniqueIds = Array.from(new Set(nodeIds.filter(Boolean)));
      set({
        selectedNodeId: uniqueIds.length > 0 ? uniqueIds[uniqueIds.length - 1] : null,
        selectedNodeIds: uniqueIds,
      });
    },

    // Update node properties
    updateNode: (nodeId, updates, context) => {
      const { recordHistory, shouldLog } = resolveActionContext(context);
      const existingNode = get().nodes.find((node) => node.id === nodeId);
      applyUpdate((state) => {
        const existingNode = state.nodes.find((node) => node.id === nodeId);
        const nextNodes = state.nodes.map((node) =>
          node.id === nodeId ? { ...node, ...updates } : node
        );
        if (!existingNode) {
          return { nodes: nextNodes };
        }
        const nextType = updates.type ?? existingNode.type;
        let nextDocuments = state.documents;
        if (nextType === "document") {
          const existingDoc = state.documents.find((doc) => doc.nodeId === nodeId);
          const shouldTouch = "title" in updates || "content" in updates;
          const mergedNode: CanvasNode = {
            ...existingNode,
            ...updates,
            type: nextType,
          };
          if (existingDoc) {
            const nextDoc = buildDocumentForNode(mergedNode, existingDoc, shouldTouch);
            nextDocuments = state.documents.map((doc) =>
              doc.nodeId === nodeId ? nextDoc : doc
            );
          } else {
            nextDocuments = [...state.documents, buildDocumentForNode(mergedNode, undefined, shouldTouch)];
          }
        } else {
          nextDocuments = state.documents.filter((doc) => doc.nodeId !== nodeId);
        }
        return { nodes: nextNodes, documents: nextDocuments };
      }, recordHistory);
      if (shouldLog && existingNode) {
        const nextNode = { ...existingNode, ...updates };
        const summary = nextNode.title ? `Node updated: ${nextNode.title}` : "Node updated";
        logCanvasAction(
          "node_updated",
          {
            node: buildNodePayload(nextNode),
            updates,
            previous: {
              title: existingNode.title,
              content: existingNode.content,
              metadata: existingNode.metadata,
              type: existingNode.type,
            },
          },
          { summary, workspaceId: get().canvasId }
        );
      }
    },

    // Clear selection
    clearSelection: () => {
      set({ selectedNodeId: null, selectedNodeIds: [] });
    },

    // Set all nodes (for bulk loading) - doesn't record history
    setNodes: (nodes) => {
      set((state) => ({
        nodes,
        documents: syncDocumentsWithNodes(nodes, state.documents),
      }));
    },

    // Add an edge between two nodes
    addEdge: (edge, context) => {
      const { recordHistory, shouldLog } = resolveActionContext(context);
      const id = edge.id ?? `edge-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const newEdge: CanvasEdge = {
        ...edge,
        id,
      };
      applyUpdate((state) => ({
        edges: [...state.edges, newEdge],
      }), recordHistory);
      if (shouldLog) {
        logCanvasAction(
          "edge_created",
          { edge: buildEdgePayload(newEdge) },
          { summary: "Edge created", workspaceId: get().canvasId }
        );
      }
      return id;
    },

    // Remove an edge
    removeEdge: (edgeId, context) => {
      const { recordHistory, shouldLog } = resolveActionContext(context);
      const existingEdge = get().edges.find((edge) => edge.id === edgeId);
      applyUpdate((state) => ({
        edges: state.edges.filter((edge) => edge.id !== edgeId),
      }), recordHistory);
      if (shouldLog) {
        logCanvasAction(
          "edge_deleted",
          { edge: existingEdge ? buildEdgePayload(existingEdge) : { id: edgeId } },
          { summary: "Edge deleted", workspaceId: get().canvasId }
        );
      }
    },

    // Update edge properties
    updateEdge: (edgeId, updates, context) => {
      const { recordHistory, shouldLog } = resolveActionContext(context);
      const existingEdge = get().edges.find((edge) => edge.id === edgeId);
      applyUpdate((state) => ({
        edges: state.edges.map((edge) =>
          edge.id === edgeId ? { ...edge, ...updates } : edge
        ),
      }), recordHistory);
      if (shouldLog && existingEdge) {
        const nextEdge = { ...existingEdge, ...updates };
        logCanvasAction(
          "edge_updated",
          {
            edge: buildEdgePayload(nextEdge),
            updates,
            previous: {
              relationType: existingEdge.relationType,
              label: existingEdge.label,
            },
          },
          { summary: "Edge updated", workspaceId: get().canvasId }
        );
      }
    },

    // Set all edges (for bulk loading) - doesn't record history
    setEdges: (edges) => {
      set({ edges });
    },

    // Undo: restore previous state
    undo: () => {
      const state = get();
      if (state.past.length === 0) return;

      const previous = state.past[state.past.length - 1];
      const newPast = state.past.slice(0, -1);

      // Current state becomes the future
      const currentSnapshot: CanvasSnapshot = {
        nodes: state.nodes,
        edges: state.edges,
        documents: state.documents,
      };

      set({
        nodes: previous.nodes,
        edges: previous.edges,
        documents: previous.documents,
        isAutoExpanding: false,
        past: newPast,
        future: [currentSnapshot, ...state.future],
      });
    },

    // Redo: restore next state
    redo: () => {
      const state = get();
      if (state.future.length === 0) return;

      const next = state.future[0];
      const newFuture = state.future.slice(1);

      // Current state becomes past
      const currentSnapshot: CanvasSnapshot = {
        nodes: state.nodes,
        edges: state.edges,
        documents: state.documents,
      };

      set({
        nodes: next.nodes,
        edges: next.edges,
        documents: next.documents,
        isAutoExpanding: false,
        past: [...state.past, currentSnapshot],
        future: newFuture,
      });
    },

    // Check if undo is available
    canUndo: () => get().past.length > 0,

    // Check if redo is available
    canRedo: () => get().future.length > 0,

    // Clear all history
    clearHistory: () => {
      set({ past: [], future: [] });
    },

    // Get nodes created by a specific turn
    getNodesByTurnId: (turnId: number) => {
      return get().nodes.filter((node) => node.createdByTurnId === turnId);
    },

    // Remove all nodes created by a specific turn (for "undo agent action" capability)
    removeNodesByTurnId: (turnId: number, context?: CanvasActionContext) => {
      const nodesToRemove = get().nodes.filter((node) => node.createdByTurnId === turnId);
      if (nodesToRemove.length === 0) {
        return [];
      }
      const nodeIdsToRemove = nodesToRemove.map((node) => node.id);
      get().removeNodes(nodeIdsToRemove, context);
      return nodeIdsToRemove;
    },
  };
});
