/**
 * Tests for canvasStore undo/redo functionality
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { useCanvasStore, CanvasNode, CanvasEdge } from '../state/canvasStore';

describe('canvasStore', () => {
  // Reset store state before each test
  beforeEach(() => {
    // Reset Zustand store state using setState
    useCanvasStore.setState({
      nodes: [],
      edges: [],
      documents: [],
      selectedNodeId: null,
      past: [],
      future: [],
    });
  });

  describe('addNode', () => {
    it('should add a node and record history', () => {
      const store = useCanvasStore.getState();

      const nodeId = store.addNode({
        type: 'text',
        x: 100,
        y: 200,
        z: 1,
        title: 'Test Node',
      });

      expect(nodeId).toMatch(/^node-/);
      expect(useCanvasStore.getState().nodes).toHaveLength(1);
      expect(useCanvasStore.getState().nodes[0].title).toBe('Test Node');
      expect(store.canUndo()).toBe(true);
      expect(useCanvasStore.getState().past).toHaveLength(1);
    });
  });

  describe('removeNode', () => {
    it('should remove a node and record history', () => {
      const store = useCanvasStore.getState();

      const nodeId = store.addNode({
        type: 'text',
        x: 0,
        y: 0,
        z: 1,
        title: 'To Delete',
      });

      store.removeNode(nodeId);

      expect(useCanvasStore.getState().nodes).toHaveLength(0);
      expect(store.canUndo()).toBe(true);
    });

    it('should remove associated edges when node is deleted', () => {
      const store = useCanvasStore.getState();

      const node1 = store.addNode({ type: 'text', x: 0, y: 0, z: 1, title: 'N1' });
      const node2 = store.addNode({ type: 'text', x: 100, y: 0, z: 1, title: 'N2' });

      store.addEdge({ sourceNodeId: node1, targetNodeId: node2 });

      expect(useCanvasStore.getState().edges).toHaveLength(1);

      store.removeNode(node1);

      expect(useCanvasStore.getState().edges).toHaveLength(0);
    });
  });

  describe('updateNodePosition', () => {
    it('should update node position and record history', () => {
      const store = useCanvasStore.getState();

      const nodeId = store.addNode({
        type: 'text',
        x: 100,
        y: 200,
        z: 1,
        title: 'Movable',
      });

      store.updateNodePosition(nodeId, 300, 400);

      const node = useCanvasStore.getState().nodes.find((n) => n.id === nodeId);
      expect(node?.x).toBe(300);
      expect(node?.y).toBe(400);
      expect(store.canUndo()).toBe(true);
    });

    it('should update z-index when provided', () => {
      const store = useCanvasStore.getState();

      const nodeId = store.addNode({
        type: 'text',
        x: 0,
        y: 0,
        z: 1,
        title: 'Test',
      });

      store.updateNodePosition(nodeId, 0, 0, 5);

      const node = useCanvasStore.getState().nodes.find((n) => n.id === nodeId);
      expect(node?.z).toBe(5);
    });
  });

  describe('addEdge', () => {
    it('should add an edge and record history', () => {
      const store = useCanvasStore.getState();

      const node1 = store.addNode({ type: 'text', x: 0, y: 0, z: 1, title: 'N1' });
      const node2 = store.addNode({ type: 'text', x: 100, y: 0, z: 1, title: 'N2' });

      const edgeId = store.addEdge({
        sourceNodeId: node1,
        targetNodeId: node2,
      });

      expect(edgeId).toMatch(/^edge-/);
      expect(useCanvasStore.getState().edges).toHaveLength(1);
      expect(useCanvasStore.getState().edges[0].sourceNodeId).toBe(node1);
      expect(useCanvasStore.getState().edges[0].targetNodeId).toBe(node2);
      expect(store.canUndo()).toBe(true);
    });
  });

  describe('removeEdge', () => {
    it('should remove an edge and record history', () => {
      const store = useCanvasStore.getState();

      const node1 = store.addNode({ type: 'text', x: 0, y: 0, z: 1, title: 'N1' });
      const node2 = store.addNode({ type: 'text', x: 100, y: 0, z: 1, title: 'N2' });

      const edgeId = store.addEdge({
        sourceNodeId: node1,
        targetNodeId: node2,
      });

      store.removeEdge(edgeId);

      expect(useCanvasStore.getState().edges).toHaveLength(0);
      expect(store.canUndo()).toBe(true);
    });
  });

  describe('undo', () => {
    it('should undo node addition', () => {
      const store = useCanvasStore.getState();

      store.addNode({ type: 'text', x: 0, y: 0, z: 1, title: 'Test' });
      expect(useCanvasStore.getState().nodes).toHaveLength(1);

      store.undo();
      expect(useCanvasStore.getState().nodes).toHaveLength(0);
      expect(store.canUndo()).toBe(false);
      expect(store.canRedo()).toBe(true);
    });

    it('should undo node removal', () => {
      const store = useCanvasStore.getState();

      const nodeId = store.addNode({
        type: 'text',
        x: 0,
        y: 0,
        z: 1,
        title: 'Test',
      });
      store.removeNode(nodeId);
      expect(useCanvasStore.getState().nodes).toHaveLength(0);

      store.undo();
      expect(useCanvasStore.getState().nodes).toHaveLength(1);
      expect(useCanvasStore.getState().nodes[0].id).toBe(nodeId);
    });

    it('should undo position change', () => {
      const store = useCanvasStore.getState();

      const nodeId = store.addNode({
        type: 'text',
        x: 100,
        y: 100,
        z: 1,
        title: 'Test',
      });
      store.updateNodePosition(nodeId, 300, 300);

      store.undo();

      const node = useCanvasStore.getState().nodes.find((n) => n.id === nodeId);
      expect(node?.x).toBe(100);
      expect(node?.y).toBe(100);
    });

    it('should do nothing when history is empty', () => {
      const store = useCanvasStore.getState();

      store.undo(); // Should not throw
      expect(useCanvasStore.getState().past).toHaveLength(0);
    });

    it('should clear future when new action is performed after undo', () => {
      const store = useCanvasStore.getState();

      store.addNode({ type: 'text', x: 0, y: 0, z: 1, title: 'N1' });
      store.addNode({ type: 'text', x: 100, y: 0, z: 1, title: 'N2' });
      expect(useCanvasStore.getState().nodes).toHaveLength(2);

      store.undo();
      expect(useCanvasStore.getState().nodes).toHaveLength(1);
      expect(store.canRedo()).toBe(true);

      // New action should clear future
      store.addNode({ type: 'text', x: 200, y: 0, z: 1, title: 'N3' });
      expect(store.canRedo()).toBe(false);
    });
  });

  describe('redo', () => {
    it('should redo undone node addition', () => {
      const store = useCanvasStore.getState();

      store.addNode({ type: 'text', x: 0, y: 0, z: 1, title: 'Test' });
      store.undo();
      expect(useCanvasStore.getState().nodes).toHaveLength(0);
      expect(store.canRedo()).toBe(true);

      store.redo();
      expect(useCanvasStore.getState().nodes).toHaveLength(1);
      expect(store.canUndo()).toBe(true);
      expect(store.canRedo()).toBe(false);
    });

    it('should redo undone position change', () => {
      const store = useCanvasStore.getState();

      const nodeId = store.addNode({
        type: 'text',
        x: 100,
        y: 100,
        z: 1,
        title: 'Test',
      });
      store.updateNodePosition(nodeId, 300, 300);

      store.undo();
      store.redo();

      const node = useCanvasStore.getState().nodes.find((n) => n.id === nodeId);
      expect(node?.x).toBe(300);
      expect(node?.y).toBe(300);
    });

    it('should do nothing when future is empty', () => {
      const store = useCanvasStore.getState();

      store.redo(); // Should not throw
      expect(useCanvasStore.getState().future).toHaveLength(0);
    });
  });

  describe('clearHistory', () => {
    it('should clear all history', () => {
      const store = useCanvasStore.getState();

      store.addNode({ type: 'text', x: 0, y: 0, z: 1, title: 'N1' });
      store.addNode({ type: 'text', x: 100, y: 0, z: 1, title: 'N2' });

      expect(store.canUndo()).toBe(true);

      store.clearHistory();

      expect(useCanvasStore.getState().past).toHaveLength(0);
      expect(useCanvasStore.getState().future).toHaveLength(0);
      expect(store.canUndo()).toBe(false);
      expect(store.canRedo()).toBe(false);
    });
  });

  describe('history capacity', () => {
    it('should limit history to 50 entries', () => {
      const store = useCanvasStore.getState();

      // Add 60 nodes (more than capacity)
      for (let i = 0; i < 60; i++) {
        store.addNode({
          type: 'text',
          x: i * 10,
          y: 0,
          z: 1,
          title: `Node ${i}`,
        });
      }

      // Should have max 50 past entries (capacity - 1 for current state)
      expect(useCanvasStore.getState().past.length).toBeLessThanOrEqual(50);
    });
  });
});
