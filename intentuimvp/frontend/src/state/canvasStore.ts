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
  documents: CanvasDocument[];
  selectedNodeId: string | null;

  // Actions
  addNode: (node: Omit<CanvasNode, 'id'>) => string;
  removeNode: (nodeId: string) => void;
  updateNodePosition: (nodeId: string, x: number, y: number, z?: number) => void;
  selectNode: (nodeId: string | null) => void;
  updateNode: (nodeId: string, updates: Partial<CanvasNode>) => void;
  clearSelection: () => void;
}

// Create the store
export const useCanvasStore = create<CanvasState>((set) => ({
  // Initial state
  nodes: [],
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
}));
