import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCanvasStore } from './canvasStore';
import { getContainerMetadata, updateContainerMetadata } from '../utils/canvasHierarchy';

describe('canvasStore', () => {
  // Reset store state before each test
  beforeEach(() => {
    // Reset to initial state by creating a fresh store
    useCanvasStore.setState({
      canvasId: null,
      canvasName: null,
      nodes: [],
      edges: [],
      documents: [],
      selectedNodeId: null,
      selectedNodeIds: [],
      isAutoExpanding: false,
      isAutoLayoutAnimating: false,
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

    it('should push colliding nodes outward from the insertion point', () => {
      const { result } = renderHook(() => useCanvasStore());

      let firstId = '';
      let secondId = '';

      act(() => {
        firstId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node 1',
        });
      });

      act(() => {
        secondId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node 2',
        });
      });

      const movedNode = result.current.nodes.find((node) => node.id === firstId);
      const newNode = result.current.nodes.find((node) => node.id === secondId);

      expect(newNode?.x).toBe(0);
      expect(newNode?.y).toBe(0);
      expect(movedNode).toBeDefined();
      expect(movedNode?.x === 0 && movedNode?.y === 0).toBe(false);
    });

    it('should not move nodes when there is no collision', () => {
      const { result } = renderHook(() => useCanvasStore());

      let firstId = '';

      act(() => {
        firstId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node 1',
        });
      });

      act(() => {
        result.current.addNode({
          type: 'text',
          x: 1000,
          y: 1000,
          z: 0,
          title: 'Node 2',
        });
      });

      const originalNode = result.current.nodes.find((node) => node.id === firstId);
      expect(originalNode?.x).toBe(0);
      expect(originalNode?.y).toBe(0);
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

    it('moves container descendants when dragging a container', () => {
      const { result } = renderHook(() => useCanvasStore());
      let containerId = '';
      let childId = '';

      act(() => {
        containerId = result.current.addNode({
          type: 'container',
          x: 0,
          y: 0,
          z: 0,
          title: 'Container',
        });
        childId = result.current.addNode({
          type: 'text',
          x: 20,
          y: 30,
          z: 1,
          title: 'Child',
          metadata: updateContainerMetadata(undefined, {
            parentId: containerId,
            offset: { x: 20, y: 30 },
          }),
        });
      });

      act(() => {
        result.current.updateNodePosition(containerId, 100, 120);
      });

      const child = useCanvasStore.getState().nodes.find((n) => n.id === childId);
      expect(child?.x).toBe(120);
      expect(child?.y).toBe(150);
      const metadata = child?.metadata ? getContainerMetadata(child.metadata) : {};
      expect(metadata.offset).toEqual({ x: 20, y: 30 });
    });

    it('updates child offset metadata when moving a child node', () => {
      const { result } = renderHook(() => useCanvasStore());
      let containerId = '';
      let childId = '';

      act(() => {
        containerId = result.current.addNode({
          type: 'container',
          x: 10,
          y: 15,
          z: 0,
          title: 'Container',
        });
        childId = result.current.addNode({
          type: 'text',
          x: 25,
          y: 40,
          z: 1,
          title: 'Child',
          metadata: updateContainerMetadata(undefined, {
            parentId: containerId,
            offset: { x: 15, y: 25 },
          }),
        });
      });

      act(() => {
        result.current.updateNodePosition(childId, 60, 80);
      });

      const child = useCanvasStore.getState().nodes.find((n) => n.id === childId);
      const metadata = child?.metadata ? getContainerMetadata(child.metadata) : {};
      expect(metadata.offset).toEqual({ x: 50, y: 65 });
    });

    it('assigns a container parent when dropped inside a container', () => {
      const { result } = renderHook(() => useCanvasStore());
      let containerId = '';
      let nodeId = '';

      act(() => {
        containerId = result.current.addNode({
          type: 'container',
          x: 0,
          y: 0,
          z: 0,
          title: 'Container',
        });
        nodeId = result.current.addNode({
          type: 'text',
          x: 500,
          y: 500,
          z: 1,
          title: 'Child',
        });
      });

      act(() => {
        result.current.updateNodePosition(nodeId, 40, 40, undefined, {
          resolveContainerParent: true,
        });
      });

      const child = useCanvasStore.getState().nodes.find((n) => n.id === nodeId);
      const metadata = child?.metadata ? getContainerMetadata(child.metadata) : {};
      expect(metadata.parentId).toBe(containerId);
      expect(metadata.offset).toEqual({ x: 40, y: 40 });
    });

    it('clears container parent when dropped outside containers', () => {
      const { result } = renderHook(() => useCanvasStore());
      let containerId = '';
      let nodeId = '';

      act(() => {
        containerId = result.current.addNode({
          type: 'container',
          x: 0,
          y: 0,
          z: 0,
          title: 'Container',
        });
        nodeId = result.current.addNode({
          type: 'text',
          x: 20,
          y: 30,
          z: 1,
          title: 'Child',
          metadata: updateContainerMetadata(undefined, {
            parentId: containerId,
            offset: { x: 20, y: 30 },
          }),
        });
      });

      act(() => {
        result.current.updateNodePosition(nodeId, 500, 500, undefined, {
          resolveContainerParent: true,
        });
      });

      const child = useCanvasStore.getState().nodes.find((n) => n.id === nodeId);
      const metadata = child?.metadata ? getContainerMetadata(child.metadata) : {};
      expect(metadata.parentId).toBeUndefined();
      expect(metadata.offset).toBeUndefined();
    });

    it('prefers the deepest container when nested containers overlap', () => {
      const { result } = renderHook(() => useCanvasStore());
      let outerId = '';
      let innerId = '';
      let nodeId = '';

      act(() => {
        outerId = result.current.addNode({
          type: 'container',
          x: 0,
          y: 0,
          z: 0,
          title: 'Outer',
          metadata: updateContainerMetadata(undefined, {
            size: { width: 500, height: 400 },
          }),
        });
        innerId = result.current.addNode({
          type: 'container',
          x: 50,
          y: 50,
          z: 1,
          title: 'Inner',
          metadata: updateContainerMetadata(undefined, {
            parentId: outerId,
            offset: { x: 50, y: 50 },
            size: { width: 200, height: 200 },
          }),
        });
        nodeId = result.current.addNode({
          type: 'text',
          x: 600,
          y: 600,
          z: 2,
          title: 'Child',
        });
      });

      act(() => {
        result.current.updateNodePosition(nodeId, 80, 80, undefined, {
          resolveContainerParent: true,
        });
      });

      const child = useCanvasStore.getState().nodes.find((n) => n.id === nodeId);
      const metadata = child?.metadata ? getContainerMetadata(child.metadata) : {};
      expect(metadata.parentId).toBe(innerId);
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

  describe('document nodes', () => {
    it('should create a document entry when adding a document node', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'document',
          x: 0,
          y: 0,
          z: 0,
          title: 'Doc Title',
          content: 'Doc content',
        });
      });

      const document = result.current.documents.find((doc) => doc.nodeId === nodeId);
      expect(document?.title).toBe('Doc Title');
      expect(document?.content).toBe('Doc content');
    });

    it('should update document entries when document nodes change', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'document',
          x: 0,
          y: 0,
          z: 0,
          title: 'Doc Title',
          content: 'Doc content',
        });
        result.current.updateNode(nodeId, {
          title: 'Updated Title',
          content: 'Updated content',
        });
      });

      const document = result.current.documents.find((doc) => doc.nodeId === nodeId);
      expect(document?.title).toBe('Updated Title');
      expect(document?.content).toBe('Updated content');
      expect(document?.updatedAt.getTime()).toBeGreaterThanOrEqual(
        document?.createdAt.getTime() ?? 0
      );
    });

    it('should remove documents when nodes change type', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'document',
          x: 0,
          y: 0,
          z: 0,
          title: 'Doc Title',
        });
        result.current.updateNode(nodeId, { type: 'text' });
      });

      expect(result.current.documents).toHaveLength(0);
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

  describe('turn attribution', () => {
    it('should store createdByTurnId on nodes', () => {
      const { result } = renderHook(() => useCanvasStore());

      let nodeId = '';

      act(() => {
        nodeId = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Agent Created Node',
          createdByTurnId: 42,
        });
      });

      const node = result.current.nodes.find((n) => n.id === nodeId);
      expect(node?.createdByTurnId).toBe(42);
    });

    it('should get nodes by turn ID', () => {
      const { result } = renderHook(() => useCanvasStore());

      act(() => {
        result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node from turn 1',
          createdByTurnId: 1,
        });
        result.current.addNode({
          type: 'text',
          x: 100,
          y: 0,
          z: 0,
          title: 'Another node from turn 1',
          createdByTurnId: 1,
        });
        result.current.addNode({
          type: 'text',
          x: 200,
          y: 0,
          z: 0,
          title: 'Node from turn 2',
          createdByTurnId: 2,
        });
        result.current.addNode({
          type: 'text',
          x: 300,
          y: 0,
          z: 0,
          title: 'Node without attribution',
        });
      });

      const turn1Nodes = result.current.getNodesByTurnId(1);
      expect(turn1Nodes).toHaveLength(2);
      expect(turn1Nodes.every((n) => n.createdByTurnId === 1)).toBe(true);

      const turn2Nodes = result.current.getNodesByTurnId(2);
      expect(turn2Nodes).toHaveLength(1);

      const noNodes = result.current.getNodesByTurnId(99999);
      expect(noNodes).toHaveLength(0);
    });

    it('should remove nodes by turn ID', () => {
      const { result } = renderHook(() => useCanvasStore());

      act(() => {
        result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node from turn 5',
          createdByTurnId: 5,
        });
        result.current.addNode({
          type: 'text',
          x: 100,
          y: 0,
          z: 0,
          title: 'Another node from turn 5',
          createdByTurnId: 5,
        });
        result.current.addNode({
          type: 'text',
          x: 200,
          y: 0,
          z: 0,
          title: 'Node from turn 6',
          createdByTurnId: 6,
        });
      });

      expect(result.current.nodes).toHaveLength(3);

      let removedIds: string[] = [];
      act(() => {
        removedIds = result.current.removeNodesByTurnId(5);
      });

      expect(removedIds).toHaveLength(2);
      expect(result.current.nodes).toHaveLength(1);
      expect(result.current.nodes[0].createdByTurnId).toBe(6);
    });

    it('should return empty array when removing nodes for non-existent turn', () => {
      const { result } = renderHook(() => useCanvasStore());

      act(() => {
        result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node with attribution',
          createdByTurnId: 1,
        });
      });

      let removedIds: string[] = [];
      act(() => {
        removedIds = result.current.removeNodesByTurnId(99999);
      });

      expect(removedIds).toEqual([]);
      expect(result.current.nodes).toHaveLength(1);
    });
  });

  describe('applyLayout', () => {
    it('applies a grid layout and stores layout metadata', () => {
      const { result } = renderHook(() => useCanvasStore());

      let id1 = '';
      let id2 = '';

      act(() => {
        id1 = result.current.addNode({
          type: 'text',
          x: 100,
          y: 200,
          z: 0,
          title: 'Node A',
        });
        id2 = result.current.addNode({
          type: 'text',
          x: 140,
          y: 240,
          z: 0,
          title: 'Node B',
        });
      });

      act(() => {
        result.current.applyLayout({ layout: 'grid', nodeIds: [id1, id2], lock: true });
      });

      const node1 = result.current.nodes.find((node) => node.id === id1);
      const node2 = result.current.nodes.find((node) => node.id === id2);
      expect(node1).toBeDefined();
      expect(node2).toBeDefined();
      expect(node1?.y).toBe(node2?.y);
      expect(node1?.x).not.toBe(node2?.x);

      const layoutMeta = node1?.metadata?.layout as { regionId?: string; layout?: string; locked?: boolean } | undefined;
      expect(layoutMeta?.layout).toBe('grid');
      expect(layoutMeta?.locked).toBe(true);
      expect(typeof layoutMeta?.regionId).toBe('string');
    });

    it('produces deterministic positions for the same layout input', () => {
      const { result } = renderHook(() => useCanvasStore());

      let id1 = '';
      let id2 = '';

      act(() => {
        id1 = result.current.addNode({
          type: 'text',
          x: 0,
          y: 0,
          z: 0,
          title: 'Node A',
        });
        id2 = result.current.addNode({
          type: 'text',
          x: 50,
          y: 0,
          z: 0,
          title: 'Node B',
        });
      });

      act(() => {
        result.current.applyLayout({ layout: 'grid', nodeIds: [id1, id2] });
      });

      const firstPositions = result.current.nodes.reduce<Record<string, { x: number; y: number }>>(
        (acc, node) => {
          acc[node.id] = { x: node.x, y: node.y };
          return acc;
        },
        {}
      );

      act(() => {
        result.current.applyLayout({ layout: 'grid', nodeIds: [id1, id2] });
      });

      const secondPositions = result.current.nodes.reduce<Record<string, { x: number; y: number }>>(
        (acc, node) => {
          acc[node.id] = { x: node.x, y: node.y };
          return acc;
        },
        {}
      );

      expect(secondPositions).toEqual(firstPositions);
    });
  });
});
