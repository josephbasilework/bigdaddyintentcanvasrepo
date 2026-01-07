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

// Store state interface
interface CanvasState {
  // State
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  documents: CanvasDocument[];
  selectedNodeId: string | null;

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
}

// Create the store
export const useCanvasStore = create<CanvasState>((set) => ({
  // Initial state
  nodes: [],
  edges: [],
  documents: [],
  selectedNodeId: null,

  // Add a new node to the canvas
  addNode: (node) => {
    const id = `node-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    const newNode: CanvasNode = {
      ...node,
      id,
    };
    set((state) => ({
      nodes: [...state.nodes, newNode],
    }));
    return id;
  },

  // Remove a node from the canvas
  removeNode: (nodeId) => {
    set((state) => ({
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
    set((state) => ({
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
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === nodeId ? { ...node, ...updates } : node
      ),
    }));
  },

  // Clear selection
  clearSelection: () => {
    set({ selectedNodeId: null });
  },

  // Set all nodes (for bulk loading)
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
    set((state) => ({
      edges: [...state.edges, newEdge],
    }));
    return id;
  },

  // Remove an edge
  removeEdge: (edgeId) => {
    set((state) => ({
      edges: state.edges.filter((edge) => edge.id !== edgeId),
    }));
  },

  // Set all edges (for bulk loading)
  setEdges: (edges) => {
    set({ edges });
  },
}));
