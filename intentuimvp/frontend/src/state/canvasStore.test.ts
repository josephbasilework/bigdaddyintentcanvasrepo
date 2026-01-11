import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCanvasStore } from './canvasStore';

describe('canvasStore', () => {
  // Reset store state before each test
  beforeEach(() => {
    // Reset to initial state by creating a fresh store
    useCanvasStore.setState({
      nodes: [],
      edges: [],
      documents: [],
      selectedNodeId: null,
      selectedNodeIds: [],
      past: [],
      future: [],
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

    it('should have empty selectedNodeIds array', () => {
      const { result } = renderHook(() => useCanvasStore());
      expect(result.current.selectedNodeIds).toEqual([]);
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
      expect(result.current.selectedNodeIds).toEqual([]);
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
      expect(result.current.selectedNodeIds).toEqual([nodeId1]);
    });
  });

  describe('removeNodes', () => {
    it('should remove multiple nodes and linked artifacts', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId1 = '';
      let nodeId2 = '';
      let nodeId3 = '';

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
        nodeId3 = result.current.addNode({
          type: 'text',
          x: 200,
          y: 200,
          z: 0,
          title: 'Node 3',
        });
        result.current.addEdge({ sourceNodeId: nodeId1, targetNodeId: nodeId2 });
        result.current.addEdge({ sourceNodeId: nodeId2, targetNodeId: nodeId3 });
      });

      act(() => {
        useCanvasStore.setState({
          documents: [{
            id: 'doc-1',
            nodeId: nodeId1,
            title: 'Doc 1',
            content: 'Content',
            createdAt: new Date(),
            updatedAt: new Date(),
          }],
        });
        useCanvasStore.setState({ selectedNodeId: nodeId1, selectedNodeIds: [nodeId1, nodeId2] });
      });

      act(() => {
        result.current.removeNodes([nodeId1, nodeId2]);
      });

      expect(result.current.nodes).toHaveLength(1);
      expect(result.current.nodes[0].id).toBe(nodeId3);
      expect(result.current.edges).toHaveLength(0);
      expect(result.current.documents).toHaveLength(0);
      expect(result.current.selectedNodeId).toBeNull();
      expect(result.current.selectedNodeIds).toEqual([]);
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
      expect(result.current.selectedNodeIds).toEqual([nodeId]);
    });

    it('should add to selection when additive option is provided', () => {
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
        result.current.selectNode(nodeId2, { additive: true });
      });

      expect(result.current.selectedNodeIds).toEqual([nodeId1, nodeId2]);
      expect(result.current.selectedNodeId).toBe(nodeId2);
    });

    it('should toggle selection when toggle option is provided', () => {
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
        result.current.selectNode(nodeId2, { toggle: true });
      });

      expect(result.current.selectedNodeIds).toEqual([nodeId1, nodeId2]);
      expect(result.current.selectedNodeId).toBe(nodeId2);

      act(() => {
        result.current.selectNode(nodeId2, { toggle: true });
      });

      expect(result.current.selectedNodeIds).toEqual([nodeId1]);
      expect(result.current.selectedNodeId).toBe(nodeId1);

      act(() => {
        result.current.selectNode(nodeId1, { toggle: true });
      });

      expect(result.current.selectedNodeIds).toEqual([]);
      expect(result.current.selectedNodeId).toBeNull();
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
      expect(result.current.selectedNodeIds).toEqual([]);
    });
  });

  describe('setSelectedNodes', () => {
    it('should set selectedNodeIds and selectedNodeId', () => {
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
        result.current.setSelectedNodes([nodeId1, nodeId2]);
      });

      expect(result.current.selectedNodeIds).toEqual([nodeId1, nodeId2]);
      expect(result.current.selectedNodeId).toBe(nodeId2);
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
      expect(result.current.selectedNodeIds).toEqual([]);
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
