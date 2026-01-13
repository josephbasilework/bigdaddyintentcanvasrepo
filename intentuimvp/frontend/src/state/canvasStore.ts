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
  type: 'text' | 'document' | 'audio' | 'graph' | 'plan' | 'dag';
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
  // State
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  documents: CanvasDocument[];
  selectedNodeId: string | null;
  selectedNodeIds: string[];

  // History state
  past: CanvasSnapshot[];
  future: CanvasSnapshot[];

  // Actions
  addNode: (node: Omit<CanvasNode, 'id'>) => string;
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

  return {
    // Initial state
    nodes: [],
    edges: [],
    documents: [],
    selectedNodeId: null,
    selectedNodeIds: [],
    past: [],
    future: [],

    // Add a new node to the canvas
    addNode: (node) => {
      const id = `node-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const newNode: CanvasNode = {
        ...node,
        id,
      };
      withHistory((state) => ({
        nodes: [...state.nodes, newNode],
      }));
      return id;
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
