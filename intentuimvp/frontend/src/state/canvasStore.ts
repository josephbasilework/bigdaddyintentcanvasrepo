import { create } from 'zustand';

// Types for canvas entities
export interface CanvasNode {
  id: string;
  type: 'text' | 'document' | 'audio' | 'graph';
  x: number;
  y: number;
  z: number;
  title: string;
  content?: string;
  metadata?: Record<string, unknown>;
}

export interface CanvasEdge {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  label?: string;
  type?: 'solid' | 'dashed' | 'dotted';
}

export interface CanvasDocument {
  id: string;
  nodeId: string;
  title: string;
  content: string;
  createdAt: Date;
  updatedAt: Date;
}

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

  // History state
  past: CanvasSnapshot[];
  future: CanvasSnapshot[];

  // Actions
  addNode: (node: Omit<CanvasNode, 'id'>) => string;
  removeNode: (nodeId: string) => void;
  updateNodePosition: (nodeId: string, x: number, y: number, z?: number) => void;
  selectNode: (nodeId: string | null) => void;
  updateNode: (nodeId: string, updates: Partial<CanvasNode>) => void;
  clearSelection: () => void;
  setNodes: (nodes: CanvasNode[]) => void;
  addEdge: (edge: Omit<CanvasEdge, 'id'>) => string;
  removeEdge: (edgeId: string) => void;
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
      withHistory((state) => ({
        nodes: state.nodes.filter((node) => node.id !== nodeId),
        edges: state.edges.filter(
          (edge) => edge.sourceNodeId !== nodeId && edge.targetNodeId !== nodeId
        ),
        documents: state.documents.filter((doc) => doc.nodeId !== nodeId),
        selectedNodeId: state.selectedNodeId === nodeId ? null : state.selectedNodeId,
      }));
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
    selectNode: (nodeId) => {
      set({ selectedNodeId: nodeId });
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
      set({ selectedNodeId: null });
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
