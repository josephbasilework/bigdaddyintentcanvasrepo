import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { MutableRefObject, ReactNode } from 'react';
import { useCanvasStore } from '../state/canvasStore';
import Home from '../app/page';

const mockTransformRef = vi.hoisted(() => ({
  state: { scale: 1, positionX: 0, positionY: 0 },
  setTransform: vi.fn(),
  zoomIn: vi.fn(),
  zoomOut: vi.fn(),
  resetTransform: vi.fn(),
  centerView: vi.fn(),
  zoomToElement: vi.fn(),
  instance: {} as unknown,
}));

const draggableProps = { current: null as null | Record<string, unknown> };
const createRect = (left: number, top: number, width: number, height: number): DOMRect => ({
  left,
  top,
  width,
  height,
  right: left + width,
  bottom: top + height,
  x: left,
  y: top,
  toJSON: () => '',
});

vi.mock('react-zoom-pan-pinch', async () => {
  const React = await vi.importActual<typeof import('react')>('react');
  const { forwardRef, useEffect } = React;

  const TransformWrapper = forwardRef(function MockTransformWrapper(
    { children }: { children: ReactNode },
    ref
  ) {
    useEffect(() => {
      if (typeof ref === 'function') {
        ref(mockTransformRef as never);
      } else if (ref) {
        (ref as MutableRefObject<typeof mockTransformRef>).current = mockTransformRef;
      }
    }, [ref]);

    return <div data-testid="transform-wrapper">{children}</div>;
  });

  const TransformComponent = ({ children }: { children: ReactNode }) => (
    <div data-testid="transform-component">{children}</div>
  );

  const useTransformComponent = <T,>(
    callback: (state: { state: { scale: number; positionX: number; positionY: number } }) => T
  ) => callback({ state: mockTransformRef.state });

  return { TransformWrapper, TransformComponent, useTransformComponent };
});

vi.mock('react-draggable', () => ({
  __esModule: true,
  default: (props: { children: ReactNode }) => {
    draggableProps.current = props;
    return <div data-testid="draggable">{props.children}</div>;
  },
}));

describe('workspace canvas', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  const createResponse = (payload: unknown) => ({
    ok: true,
    json: async () => payload,
  });

  beforeEach(() => {
    mockTransformRef.state = { scale: 1, positionX: 0, positionY: 0 };
    mockTransformRef.setTransform.mockClear();
    mockTransformRef.zoomIn.mockClear();
    mockTransformRef.zoomOut.mockClear();
    mockTransformRef.resetTransform.mockClear();
    draggableProps.current = null;

    useCanvasStore.setState({
      canvasId: null,
      canvasName: null,
      nodes: [],
      edges: [],
      documents: [],
      selectedNodeId: null,
      selectedNodeIds: [],
      past: [],
      future: [],
    });

    fetchMock = vi.fn().mockResolvedValue(createResponse({ nodes: [], edges: [] }));

    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders the canvas container on initial load', async () => {
    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    expect(screen.getByTestId('canvas-container')).toBeInTheDocument();
  });

  it('shows an empty state message for first-time users', async () => {
    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    expect(screen.getByTestId('empty-canvas-state')).toBeInTheDocument();
    expect(screen.getByText('Your canvas is empty')).toBeInTheDocument();
  });

  it('renders the floating command input', async () => {
    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    expect(screen.getByRole('textbox', { name: /command input/i })).toBeInTheDocument();
  });

  it('creates a node when a command is submitted', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/workspace')) {
        return Promise.resolve(createResponse({ nodes: [], edges: [] }));
      }
      if (url.includes('/api/context/assumptions')) {
        return Promise.resolve(createResponse({
          intent: 'capture',
          confidence: 0.9,
          alternatives: [],
          assumptions: [],
          reasoning: '',
          should_auto_execute: true,
        }));
      }
      if (url.includes('/api/commands')) {
        return Promise.resolve(createResponse({ correlation_id: 'cmd-1', status: 'queued' }));
      }
      return Promise.resolve(createResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const commandInput = screen.getByRole('textbox', { name: /command input/i });
    fireEvent.change(commandInput, { target: { value: 'Outline next sprint' } });
    fireEvent.keyDown(commandInput, { key: 'Enter' });

    await waitFor(() => expect(useCanvasStore.getState().nodes).toHaveLength(1));

    const [node] = useCanvasStore.getState().nodes;
    expect(node.title).toBe('Outline next sprint');
    expect(node.type).toBe('text');
    expect(node.content).toBeUndefined();
    expect(node.metadata).toBeUndefined();
    expect(useCanvasStore.getState().selectedNodeId).toBe(node.id);
  });

  it('uses slash commands to shape the new node', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/workspace')) {
        return Promise.resolve(createResponse({ nodes: [], edges: [] }));
      }
      if (url.includes('/api/context/assumptions')) {
        return Promise.resolve(createResponse({
          intent: 'plan',
          confidence: 0.9,
          alternatives: [],
          assumptions: [],
          reasoning: '',
          should_auto_execute: true,
        }));
      }
      if (url.includes('/api/commands')) {
        return Promise.resolve(createResponse({ correlation_id: 'cmd-2', status: 'queued' }));
      }
      return Promise.resolve(createResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const commandInput = screen.getByRole('textbox', { name: /command input/i });
    fireEvent.change(commandInput, { target: { value: '/plan Build Q1 roadmap' } });
    fireEvent.keyDown(commandInput, { key: 'Enter' });

    await waitFor(() => expect(useCanvasStore.getState().nodes).toHaveLength(1));

    const [node] = useCanvasStore.getState().nodes;
    expect(node.title).toBe('Plan: Build Q1 roadmap');
    expect(node.type).toBe('plan');
    expect(node.content).toBe('Build Q1 roadmap');
    expect(node.metadata).toMatchObject({ command: '/plan' });
  });

  it('creates dashboard nodes for dashboard commands', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/workspace')) {
        return Promise.resolve(createResponse({ nodes: [], edges: [] }));
      }
      if (url.includes('/api/context/assumptions')) {
        return Promise.resolve(createResponse({
          intent: 'dashboard',
          confidence: 0.9,
          alternatives: [],
          assumptions: [],
          reasoning: '',
          should_auto_execute: true,
        }));
      }
      if (url.includes('/api/commands')) {
        return Promise.resolve(createResponse({ correlation_id: 'cmd-3', status: 'queued' }));
      }
      return Promise.resolve(createResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const commandInput = screen.getByRole('textbox', { name: /command input/i });
    fireEvent.change(commandInput, { target: { value: '/dashboard Sales KPIs' } });
    fireEvent.keyDown(commandInput, { key: 'Enter' });

    await waitFor(() => expect(useCanvasStore.getState().nodes).toHaveLength(1));

    const [node] = useCanvasStore.getState().nodes;
    expect(node.title).toBe('Dashboard: Sales KPIs');
    expect(node.type).toBe('dashboard');
    expect(node.metadata).toMatchObject({ command: '/dashboard' });
  });

  it('persists assumption resolutions before executing commands', async () => {
    let batchPayload: Record<string, unknown> | null = null;

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/workspace')) {
        return Promise.resolve(createResponse({ nodes: [], edges: [] }));
      }
      if (url.includes('/api/context/assumptions/batch-resolve')) {
        const rawBody = init?.body ? String(init.body) : '';
        batchPayload = rawBody ? JSON.parse(rawBody) : null;
        return Promise.resolve(createResponse({ resolved_count: 1 }));
      }
      if (url.includes('/api/context/assumptions')) {
        return Promise.resolve(createResponse({
          intent: 'capture',
          confidence: 0.4,
          alternatives: [],
          assumptions: [
            {
              id: 'assumption-1',
              text: 'Use last quarter data',
              confidence: 0.4,
              category: 'parameter',
              explanation: null,
            },
          ],
          reasoning: '',
          should_auto_execute: false,
          session_id: 'session-123',
        }));
      }
      if (url.includes('/api/commands')) {
        return Promise.resolve(createResponse({ correlation_id: 'cmd-3', status: 'queued' }));
      }
      return Promise.resolve(createResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const commandInput = screen.getByRole('textbox', { name: /command input/i });
    fireEvent.change(commandInput, { target: { value: 'Capture metrics' } });
    fireEvent.keyDown(commandInput, { key: 'Enter' });

    const confirmAssumptionButton = await screen.findByRole('button', { name: 'Confirm' });
    fireEvent.click(confirmAssumptionButton);

    const continueButton = await screen.findByRole('button', {
      name: /continue with execution/i,
    });
    fireEvent.click(continueButton);

    await waitFor(() => expect(batchPayload).not.toBeNull());
    expect(batchPayload).toMatchObject({
      session_id: 'session-123',
      resolutions: [
        {
          assumption_id: 'assumption-1',
          action: 'accept',
          original_text: 'Use last quarter data',
          category: 'parameter',
        },
      ],
    });
  });

  it('uses the current zoom scale for draggable nodes', async () => {
    mockTransformRef.state = { scale: 1.6, positionX: 0, positionY: 0 };
    fetchMock.mockResolvedValueOnce(createResponse({
      nodes: [{
        id: 'node-1',
        type: 'text',
        x: 120,
        y: 80,
        z: 1,
        title: 'Draggable node',
      }],
      edges: [],
    }));

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await waitFor(() => expect(draggableProps.current).not.toBeNull());

    expect(draggableProps.current?.scale).toBe(1.6);
  });

  it('falls back to an empty state when workspace data is corrupted', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        nodes: 'not-an-array',
        edges: { bad: true },
      }),
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    expect(screen.getByTestId('empty-canvas-state')).toBeInTheDocument();
  });

  it('does not show empty state when nodes exist', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        nodes: [
          {
            id: 'node-1',
            type: 'text',
            x: 0,
            y: 0,
            z: 1,
            title: 'First node',
            content: 'Hello',
          },
        ],
        edges: [],
      }),
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    expect(screen.queryByTestId('empty-canvas-state')).not.toBeInTheDocument();
  });

  it('pans the canvas with arrow keys when the workspace is focused', async () => {
    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const workspace = screen.getByRole('region', { name: /canvas workspace/i });
    workspace.focus();

    fireEvent.keyDown(workspace, { key: 'ArrowRight' });

    expect(mockTransformRef.setTransform).toHaveBeenCalledWith(-40, 0, 1, 0);
  });

  it('zooms the canvas with keyboard shortcuts', async () => {
    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const workspace = screen.getByRole('region', { name: /canvas workspace/i });
    workspace.focus();

    fireEvent.keyDown(workspace, { key: '=', ctrlKey: true });

    expect(mockTransformRef.zoomIn).toHaveBeenCalled();
  });

  it('selects and edits a node with the keyboard', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        nodes: [
          {
            id: 'node-1',
            type: 'text',
            x: 0,
            y: 0,
            z: 1,
            title: 'First node',
            content: 'Hello',
          },
        ],
        edges: [],
      }),
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const node = screen.getByRole('button', { name: /first node/i });
    fireEvent.focus(node);

    expect(useCanvasStore.getState().selectedNodeId).toBe('node-1');

    fireEvent.keyDown(node, { key: 'Enter' });

    expect(screen.getByDisplayValue('First node')).toBeInTheDocument();
  });

  it('supports additive and toggle multi-selection via clicks', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        nodes: [
          {
            id: 'node-1',
            type: 'text',
            x: 0,
            y: 0,
            z: 1,
            title: 'First node',
          },
          {
            id: 'node-2',
            type: 'text',
            x: 240,
            y: 0,
            z: 2,
            title: 'Second node',
          },
        ],
        edges: [],
      }),
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const firstNode = screen.getByRole('button', { name: /first node/i });
    const secondNode = screen.getByRole('button', { name: /second node/i });

    fireEvent.click(firstNode);
    expect(useCanvasStore.getState().selectedNodeIds).toEqual(['node-1']);
    expect(useCanvasStore.getState().selectedNodeId).toBe('node-1');

    fireEvent.click(secondNode, { shiftKey: true });
    expect(useCanvasStore.getState().selectedNodeIds).toEqual(['node-1', 'node-2']);
    expect(useCanvasStore.getState().selectedNodeId).toBe('node-2');

    fireEvent.click(secondNode, { ctrlKey: true });
    expect(useCanvasStore.getState().selectedNodeIds).toEqual(['node-1']);
    expect(useCanvasStore.getState().selectedNodeId).toBe('node-1');
  });

  it('selects nodes within a shift-drag region', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        nodes: [
          {
            id: 'node-1',
            type: 'text',
            x: 0,
            y: 0,
            z: 1,
            title: 'First node',
          },
          {
            id: 'node-2',
            type: 'text',
            x: 240,
            y: 0,
            z: 2,
            title: 'Second node',
          },
        ],
        edges: [],
      }),
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const workspace = screen.getByTestId('canvas-workspace');
    const firstNode = screen.getByRole('button', { name: /first node/i });
    const secondNode = screen.getByRole('button', { name: /second node/i });

    Object.defineProperty(firstNode, 'getBoundingClientRect', {
      value: () => createRect(120, 120, 200, 100),
    });
    Object.defineProperty(secondNode, 'getBoundingClientRect', {
      value: () => createRect(360, 120, 200, 100),
    });

    fireEvent.mouseDown(workspace, { clientX: 80, clientY: 80, shiftKey: true });
    fireEvent.mouseMove(window, { clientX: 620, clientY: 260 });
    fireEvent.mouseUp(window, { clientX: 620, clientY: 260 });

    await waitFor(() =>
      expect(useCanvasStore.getState().selectedNodeIds).toEqual(['node-1', 'node-2'])
    );
  });

  it('toggles selection state with ctrl-drag region selection', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        nodes: [
          {
            id: 'node-1',
            type: 'text',
            x: 0,
            y: 0,
            z: 1,
            title: 'First node',
          },
          {
            id: 'node-2',
            type: 'text',
            x: 240,
            y: 0,
            z: 2,
            title: 'Second node',
          },
          {
            id: 'node-3',
            type: 'text',
            x: 480,
            y: 0,
            z: 3,
            title: 'Third node',
          },
        ],
        edges: [],
      }),
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const workspace = screen.getByTestId('canvas-workspace');
    const firstNode = screen.getByRole('button', { name: /first node/i });
    const secondNode = screen.getByRole('button', { name: /second node/i });
    const thirdNode = screen.getByRole('button', { name: /third node/i });

    Object.defineProperty(firstNode, 'getBoundingClientRect', {
      value: () => createRect(120, 120, 200, 100),
    });
    Object.defineProperty(secondNode, 'getBoundingClientRect', {
      value: () => createRect(360, 120, 200, 100),
    });
    Object.defineProperty(thirdNode, 'getBoundingClientRect', {
      value: () => createRect(760, 120, 200, 100),
    });

    act(() => {
      useCanvasStore.setState({
        selectedNodeId: 'node-3',
        selectedNodeIds: ['node-1', 'node-3'],
      });
    });

    act(() => {
      fireEvent.mouseDown(workspace, { clientX: 80, clientY: 80, ctrlKey: true });
      fireEvent.mouseMove(window, { clientX: 620, clientY: 260 });
      fireEvent.mouseUp(window, { clientX: 620, clientY: 260 });
    });

    await waitFor(() => {
      expect(useCanvasStore.getState().selectedNodeIds).toEqual(['node-3', 'node-2']);
      expect(useCanvasStore.getState().selectedNodeId).toBe('node-2');
    });
  });

  it('preserves multi-selection when focus follows pointer interactions', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        nodes: [
          {
            id: 'node-1',
            type: 'text',
            x: 0,
            y: 0,
            z: 1,
            title: 'First node',
          },
          {
            id: 'node-2',
            type: 'text',
            x: 240,
            y: 0,
            z: 2,
            title: 'Second node',
          },
        ],
        edges: [],
      }),
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const firstNode = screen.getByRole('button', { name: /first node/i });
    const secondNode = screen.getByRole('button', { name: /second node/i });

    fireEvent.click(firstNode);
    expect(useCanvasStore.getState().selectedNodeIds).toEqual(['node-1']);

    fireEvent.mouseDown(secondNode);
    fireEvent.focus(secondNode);
    fireEvent.click(secondNode, { shiftKey: true });

    expect(useCanvasStore.getState().selectedNodeIds).toEqual(['node-1', 'node-2']);
    expect(useCanvasStore.getState().selectedNodeId).toBe('node-2');
  });

  it('connects nodes from the context menu', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        nodes: [
          {
            id: 'node-1',
            type: 'text',
            x: 0,
            y: 0,
            z: 1,
            title: 'First node',
          },
          {
            id: 'node-2',
            type: 'text',
            x: 240,
            y: 0,
            z: 2,
            title: 'Second node',
          },
        ],
        edges: [],
      }),
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const sourceNode = screen.getByRole('button', { name: /first node/i });
    fireEvent.contextMenu(sourceNode);

    const connectItem = screen.getByRole('menuitem', { name: /connect node/i });
    fireEvent.click(connectItem);

    await waitFor(() => expect(screen.getByTestId('connect-mode-banner')).toBeInTheDocument());

    const relationSelect = screen.getByLabelText(/relation/i);
    const labelInput = screen.getByLabelText(/edge label/i);
    expect(labelInput).toHaveValue('Depends on');
    fireEvent.change(relationSelect, { target: { value: 'references' } });
    expect(labelInput).toHaveValue('References');
    fireEvent.change(labelInput, { target: { value: 'Cites' } });

    const targetNode = screen.getByRole('button', { name: /second node/i });
    fireEvent.click(targetNode);

    await waitFor(() => expect(useCanvasStore.getState().edges).toHaveLength(1));

    const [edge] = useCanvasStore.getState().edges;
    expect(edge.sourceNodeId).toBe('node-1');
    expect(edge.targetNodeId).toBe('node-2');
    expect(edge.relationType).toBe('references');
    expect(edge.label).toBe('Cites');
    await waitFor(() =>
      expect(screen.queryByTestId('connect-mode-banner')).not.toBeInTheDocument()
    );
  });

  it('requires confirmation when deleting a node with linked artifacts', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        nodes: [
          {
            id: 'node-1',
            type: 'text',
            x: 0,
            y: 0,
            z: 1,
            title: 'First node',
          },
          {
            id: 'node-2',
            type: 'text',
            x: 240,
            y: 0,
            z: 2,
            title: 'Second node',
          },
        ],
        edges: [
          {
            id: 'edge-1',
            sourceNodeId: 'node-1',
            targetNodeId: 'node-2',
          },
        ],
      }),
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await waitFor(() => expect(useCanvasStore.getState().edges).toHaveLength(1));

    const sourceNode = screen.getByRole('button', { name: /first node/i });
    fireEvent.contextMenu(sourceNode);

    const deleteItem = screen.getByRole('menuitem', { name: /delete node/i });
    fireEvent.click(deleteItem);

    const dialog = await screen.findByRole('dialog', { name: /delete 1 node/i });

    expect(dialog).toHaveTextContent(/linked edges:/i);
    expect(dialog).toHaveTextContent(/1 edge/i);
  });
});
