import { create } from 'zustand';

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

export type NodeSelectionOptions = {
  additive?: boolean;
  toggle?: boolean;
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
  addNode: (node: Omit<CanvasNode, 'id'> & { id?: string }) => string;
  setCanvasMeta: (meta: { id?: number | null; name?: string | null }) => void;
  removeNode: (nodeId: string) => void;
  removeNodes: (nodeIds: string[]) => void;
  updateNodePosition: (nodeId: string, x: number, y: number, z?: number) => void;
  selectNode: (nodeId: string | null, options?: NodeSelectionOptions) => void;
  setSelectedNodes: (nodeIds: string[]) => void;
  updateNode: (nodeId: string, updates: Partial<CanvasNode>) => void;
  clearSelection: () => void;
  setNodes: (nodes: CanvasNode[]) => void;
  addEdge: (edge: Omit<CanvasEdge, 'id'>) => string;
  removeEdge: (edgeId: string) => void;
  updateEdge: (edgeId: string, updates: Partial<CanvasEdge>) => void;
  setEdges: (edges: CanvasEdge[]) => void;

  // History actions
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  clearHistory: () => void;
}

// Create the store
export const useCanvasStore = create<CanvasState>((set, get) => {
  // Helper to create history-aware setter
  const withHistory = (updater: (state: CanvasState) => Partial<CanvasState>) => {
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
    addNode: (node) => {
      const id = node.id ?? `node-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const newNode: CanvasNode = {
        ...node,
        id,
      };
      let didExpand = false;
      withHistory((state) => {
        const expansion = resolveAutoExpansion(state.nodes, newNode);
        didExpand = expansion.didExpand;
        return {
          nodes: [...expansion.nodes, newNode],
          ...(didExpand ? { isAutoExpanding: true } : {}),
        };
      });
      if (didExpand) {
        if (autoExpandTimer) {
          clearTimeout(autoExpandTimer);
        }
        autoExpandTimer = setTimeout(() => {
          set({ isAutoExpanding: false });
        }, AUTO_EXPAND_ANIMATION_MS);
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
    removeNode: (nodeId) => {
      withHistory((state) => {
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
      });
    },

    // Remove multiple nodes from the canvas
    removeNodes: (nodeIds) => {
      const uniqueIds = Array.from(new Set(nodeIds)).filter(Boolean);
      if (uniqueIds.length === 0) return;
      const idsToRemove = new Set(uniqueIds);
      withHistory((state) => {
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
      });
    },

    // Update node position
    updateNodePosition: (nodeId, x, y, z) => {
      withHistory((state) => ({
        nodes: state.nodes.map((node) =>
          node.id === nodeId
            ? { ...node, x, y, ...(z !== undefined && { z }) }
            : node
        ),
      }));
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
    updateNode: (nodeId, updates) => {
      withHistory((state) => ({
        nodes: state.nodes.map((node) =>
          node.id === nodeId ? { ...node, ...updates } : node
        ),
      }));
    },

    // Clear selection
    clearSelection: () => {
      set({ selectedNodeId: null, selectedNodeIds: [] });
    },

    // Set all nodes (for bulk loading) - doesn't record history
    setNodes: (nodes) => {
      set({ nodes });
    },

    // Add an edge between two nodes
    addEdge: (edge) => {
      const id = `edge-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const newEdge: CanvasEdge = {
        ...edge,
        id,
      };
      withHistory((state) => ({
        edges: [...state.edges, newEdge],
      }));
      return id;
    },

    // Remove an edge
    removeEdge: (edgeId) => {
      withHistory((state) => ({
        edges: state.edges.filter((edge) => edge.id !== edgeId),
      }));
    },

    // Update edge properties
    updateEdge: (edgeId, updates) => {
      withHistory((state) => ({
        edges: state.edges.map((edge) =>
          edge.id === edgeId ? { ...edge, ...updates } : edge
        ),
      }));
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
  };
});
