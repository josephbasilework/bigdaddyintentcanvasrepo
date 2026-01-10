import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCanvasStore } from './canvasStore';

describe('canvasStore', () => {
  // Reset store state before each test
  beforeEach(() => {
    // Reset to initial state by creating a fresh store
    useCanvasStore.setState({
      nodes: [],
      documents: [],
      selectedNodeId: null,
    });
  });

  describe('initial state', () => {
    it('should have empty nodes array', () => {
      const { result } = renderHook(() => useCanvasStore());
      expect(result.current.nodes).toEqual([]);
    });

    it('should have empty documents array', () => {
      const { result } = renderHook(() => useCanvasStore());
      expect(result.current.documents).toEqual([]);
    });

    it('should have null selectedNodeId', () => {
      const { result } = renderHook(() => useCanvasStore());
      expect(result.current.selectedNodeId).toBeNull();
    });
  });

  describe('addNode', () => {
    it('should add a node to the store', () => {
      const { result } = renderHook(() => useCanvasStore());

      act(() => {
        result.current.addNode({
          type: 'text',
          x: 100,
          y: 200,
          z: 1,
          title: 'Test Node',
          content: 'Test content',
        });
      });

      expect(result.current.nodes).toHaveLength(1);
      expect(result.current.nodes[0]).toMatchObject({
        type: 'text',
        x: 100,
        y: 200,
        z: 1,
        title: 'Test Node',
        content: 'Test content',
      });
      expect(result.current.nodes[0].id).toBeDefined();
      expect(result.current.nodes[0].id).toMatch(/^node-\d+-[a-z0-9]+$/);
    });

    it('should return unique node IDs', () => {
      const { result } = renderHook(() => useCanvasStore());

      let id1 = '';
      let id2 = '';

      act(() => {
        id1 = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node 1',
        });
        id2 = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node 2',
        });
      });

      expect(id1).not.toBe(id2);
    });
  });

  describe('removeNode', () => {
    it('should remove a node from the store', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Test Node',
        });
      });

      expect(result.current.nodes).toHaveLength(1);

      act(() => {
        result.current.removeNode(nodeId);
      });

      expect(result.current.nodes).toHaveLength(0);
    });

    it('should clear selectedNodeId when removing selected node', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Test Node',
        });
        result.current.selectNode(nodeId);
      });

      expect(result.current.selectedNodeId).toBe(nodeId);

      act(() => {
        result.current.removeNode(nodeId);
      });

      expect(result.current.selectedNodeId).toBeNull();
    });

    it('should not affect selectedNodeId when removing non-selected node', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId1 = '';
      let nodeId2 = '';

      act(() => {
        nodeId1 = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node 1',
        });
        nodeId2 = result.current.addNode({
          type: 'text',
          x: 100,
          y: 100,
          z: 0,
          title: 'Node 2',
        });
        result.current.selectNode(nodeId1);
      });

      expect(result.current.selectedNodeId).toBe(nodeId1);

      act(() => {
        result.current.removeNode(nodeId2);
      });

      expect(result.current.selectedNodeId).toBe(nodeId1);
    });
  });

  describe('updateNodePosition', () => {
    it('should update node x, y coordinates', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Test Node',
        });
        result.current.updateNodePosition(nodeId, 100, 200);
      });

      const node = result.current.nodes.find((n) => n.id === nodeId);
      expect(node?.x).toBe(100);
      expect(node?.y).toBe(200);
    });

    it('should update node x, y, z coordinates when z is provided', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Test Node',
        });
        result.current.updateNodePosition(nodeId, 100, 200, 5);
      });

      const node = result.current.nodes.find((n) => n.id === nodeId);
      expect(node?.x).toBe(100);
      expect(node?.y).toBe(200);
      expect(node?.z).toBe(5);
    });

    it('should not modify z coordinate when z is not provided', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 3,
          title: 'Test Node',
        });
        result.current.updateNodePosition(nodeId, 100, 200);
      });

      const node = result.current.nodes.find((n) => n.id === nodeId);
      expect(node?.z).toBe(3);
    });

    it('should not affect other nodes', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId1 = '';
      let nodeId2 = '';

      act(() => {
        nodeId1 = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node 1',
        });
        nodeId2 = result.current.addNode({
          type: 'text',
          x: 100,
          y: 100,
          z: 0,
          title: 'Node 2',
        });
        result.current.updateNodePosition(nodeId1, 50, 50);
      });

      const node2 = result.current.nodes.find((n) => n.id === nodeId2);
      expect(node2?.x).toBe(100);
      expect(node2?.y).toBe(100);
    });
  });

  describe('selectNode', () => {
    it('should set selectedNodeId', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Test Node',
        });
        result.current.selectNode(nodeId);
      });

      expect(result.current.selectedNodeId).toBe(nodeId);
    });

    it('should allow selecting null to deselect', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Test Node',
        });
        result.current.selectNode(nodeId);
      });

      expect(result.current.selectedNodeId).toBe(nodeId);

      act(() => {
        result.current.selectNode(null);
      });

      expect(result.current.selectedNodeId).toBeNull();
    });
  });

  describe('clearSelection', () => {
    it('should set selectedNodeId to null', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Test Node',
        });
        result.current.selectNode(nodeId);
      });

      expect(result.current.selectedNodeId).toBe(nodeId);

      act(() => {
        result.current.clearSelection();
      });

      expect(result.current.selectedNodeId).toBeNull();
    });
  });

  describe('updateNode', () => {
    it('should update node properties', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Original Title',
          content: 'Original content',
        });
        result.current.updateNode(nodeId, {
          title: 'Updated Title',
          content: 'Updated content',
        });
      });

      const node = result.current.nodes.find((n) => n.id === nodeId);
      expect(node?.title).toBe('Updated Title');
      expect(node?.content).toBe('Updated content');
    });

    it('should not affect position when updating other properties', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId: string;

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 100,
          y: 200,
          z: 1,
          title: 'Test Node',
        });
        result.current.updateNode(nodeId, { title: 'New Title' });
      });

      const node = result.current.nodes.find((n) => n.id === nodeId);
      expect(node?.x).toBe(100);
      expect(node?.y).toBe(200);
      expect(node?.z).toBe(1);
    });
  });

  describe('reactivity', () => {
    it('should trigger re-renders when state changes', () => {
      const { result } = renderHook(() => useCanvasStore());

      const initialRenderCount = result.current.nodes.length;

      act(() => {
        result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Test Node',
        });
      });

      // After adding a node, the nodes array should be different
      expect(result.current.nodes.length).toBe(initialRenderCount + 1);
    });
  });
});
