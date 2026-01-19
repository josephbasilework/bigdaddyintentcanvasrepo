import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { MutableRefObject, ReactNode } from 'react';
import { useCanvasStore } from '../state/canvasStore';
import { useOfflineQueueStore } from '../state/offlineQueueStore';
import Home from '../app/page';

const wsMessageHandler = vi.hoisted(() => ({
  current: undefined as undefined | ((message: { type: string; payload?: unknown }) => void),
}));

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

vi.mock('@/hooks/useWebSocketEnhanced', () => ({
  useWebSocketEnhanced: ({ onMessage }: { onMessage?: (message: { type: string; payload?: unknown }) => void } = {}) => {
    wsMessageHandler.current = onMessage;
    return { sessionId: 'session-123', connectionState: 'open' };
  },
}));

describe('workspace canvas', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  const createResponse = (payload: unknown) => ({
    ok: true,
    json: async () => payload,
  });

  const mockWorkspaceFetch = (payload: unknown) => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/intent-memory/entries')) {
        return Promise.resolve(createResponse({ entries: [] }));
      }
      if (url.includes('/api/workspace')) {
        return Promise.resolve(createResponse(payload));
      }
      return Promise.resolve(createResponse({}));
    });
  };

  beforeEach(() => {
    mockTransformRef.state = { scale: 1, positionX: 0, positionY: 0 };
    mockTransformRef.setTransform.mockClear();
    mockTransformRef.zoomIn.mockClear();
    mockTransformRef.zoomOut.mockClear();
    mockTransformRef.resetTransform.mockClear();
    draggableProps.current = null;
    wsMessageHandler.current = undefined;

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
    useOfflineQueueStore.setState({
      activeSessionId: null,
      connectionState: 'closed',
      queue: [],
      isFlushingQueue: false,
      lastFlushedEventCount: 0,
      lastFlushTimestamp: null,
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

  it('closes view panels when the close-all command is submitted', async () => {
    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const chatToggle = screen.getByRole('button', { name: 'Chat' });
    fireEvent.click(chatToggle);

    await waitFor(() => expect(screen.getByText('Chat View')).toBeInTheDocument());

    const commandInput = screen.getByRole('textbox', { name: /command input/i });
    fireEvent.change(commandInput, { target: { value: 'close all panels' } });
    fireEvent.keyDown(commandInput, { key: 'Enter' });

    await waitFor(() => {
      expect(screen.queryByText('Chat View')).not.toBeInTheDocument();
    });
  });

  it('opens the chat panel from a show chat command without routing', async () => {
    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const commandInput = screen.getByRole('textbox', { name: /command input/i });
    fireEvent.change(commandInput, { target: { value: 'show chat' } });
    fireEvent.keyDown(commandInput, { key: 'Enter' });

    await waitFor(() => expect(screen.getByText('Chat View')).toBeInTheDocument());

    const calledAssumptions = fetchMock.mock.calls.some(([input]) =>
      String(input).includes('/api/context/assumptions')
    );
    expect(calledAssumptions).toBe(false);
  });

  it('clears selection when the clear selection command is submitted', async () => {
    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    useCanvasStore.setState({
      nodes: [
        {
          id: 'node-1',
          type: 'text',
          x: 120,
          y: 160,
          z: 1,
          title: 'Selected node',
        },
      ],
      selectedNodeId: 'node-1',
      selectedNodeIds: [],
    });

    const commandInput = screen.getByRole('textbox', { name: /command input/i });
    fireEvent.change(commandInput, { target: { value: 'clear selection' } });
    fireEvent.keyDown(commandInput, { key: 'Enter' });

    await waitFor(() => {
      expect(useCanvasStore.getState().selectedNodeId).toBeNull();
    });
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

    act(() => {
      wsMessageHandler.current?.({
        type: 'node.created',
        payload: {
          id: 'node-1',
          type: 'text',
          title: 'Outline next sprint',
          x: 120,
          y: 160,
          z: 1,
        },
      });
    });

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

    act(() => {
      wsMessageHandler.current?.({
        type: 'node.created',
        payload: {
          id: 'node-2',
          type: 'plan',
          title: 'Plan: Build Q1 roadmap',
          content: 'Build Q1 roadmap',
          metadata: { command: '/plan' },
          x: 140,
          y: 180,
          z: 1,
        },
      });
    });

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

    act(() => {
      wsMessageHandler.current?.({
        type: 'node.created',
        payload: {
          id: 'node-3',
          type: 'dashboard',
          title: 'Dashboard: Sales KPIs',
          metadata: { command: '/dashboard' },
          x: 160,
          y: 200,
          z: 1,
        },
      });
    });

    await waitFor(() => expect(useCanvasStore.getState().nodes).toHaveLength(1));

    const [node] = useCanvasStore.getState().nodes;
    expect(node.title).toBe('Dashboard: Sales KPIs');
    expect(node.type).toBe('dashboard');
    expect(node.metadata).toMatchObject({ command: '/dashboard' });
  });

  it('persists assumption resolutions before executing commands', async () => {
    let batchPayload: Record<string, unknown> | null = null;
    let completionSessionId: string | null = null;

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
      if (url.includes('/api/context/sessions/') && url.endsWith('/complete')) {
        const parts = url.split('/api/context/sessions/');
        const sessionPart = parts[1] ?? '';
        completionSessionId = sessionPart.split('/')[0] || null;
        return Promise.resolve(createResponse({
          status: 'completed',
          session_id: completionSessionId,
        }));
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
    await waitFor(() => expect(completionSessionId).toBe('session-123'));
  });

  it('treats edited assumptions as accepted', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/workspace')) {
        return Promise.resolve(createResponse({ nodes: [], edges: [] }));
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
      return Promise.resolve(createResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const commandInput = screen.getByRole('textbox', { name: /command input/i });
    fireEvent.change(commandInput, { target: { value: 'Capture metrics' } });
    fireEvent.keyDown(commandInput, { key: 'Enter' });

    const editButton = await screen.findByRole('button', { name: 'Edit' });
    fireEvent.click(editButton);

    const editor = screen.getByLabelText('Edit assumption');
    fireEvent.change(editor, { target: { value: 'Use year-to-date data' } });

    const saveButton = screen.getByRole('button', { name: 'Save' });
    fireEvent.click(saveButton);

    expect(await screen.findByText(/Accepted/)).toBeInTheDocument();
    expect(
      await screen.findByRole('button', { name: /continue with execution/i })
    ).toBeInTheDocument();
  });

  it('uses the current zoom scale for draggable nodes', async () => {
    mockTransformRef.state = { scale: 1.6, positionX: 0, positionY: 0 };
    mockWorkspaceFetch({
      nodes: [
        {
          id: 'node-1',
          type: 'text',
          x: 120,
          y: 80,
          z: 1,
          title: 'Draggable node',
        },
      ],
      edges: [],
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await waitFor(() => expect(draggableProps.current).not.toBeNull());

    expect(draggableProps.current?.scale).toBe(1.6);
  });

  it('falls back to an empty state when workspace data is corrupted', async () => {
    mockWorkspaceFetch({
      nodes: 'not-an-array',
      edges: { bad: true },
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    expect(screen.getByTestId('empty-canvas-state')).toBeInTheDocument();
  });

  it('does not show empty state when nodes exist', async () => {
    mockWorkspaceFetch({
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
    mockWorkspaceFetch({
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
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const node = screen.getByRole('button', { name: /first node text node/i });
    fireEvent.focus(node);

    expect(useCanvasStore.getState().selectedNodeId).toBe('node-1');

    fireEvent.keyDown(node, { key: 'Enter' });

    expect(screen.getByDisplayValue('First node')).toBeInTheDocument();
  });

  it('expands text nodes to edit content inline', async () => {
    mockWorkspaceFetch({
      nodes: [
        {
          id: 'node-1',
          type: 'text',
          x: 0,
          y: 0,
          z: 1,
          title: 'First node',
          content: 'Hello world',
        },
      ],
      edges: [],
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const node = screen.getByRole('button', { name: /first node text node/i });
    expect(screen.queryByText('Hello world')).not.toBeInTheDocument();

    const expandButton = within(node).getByRole('button', { name: /expand first node content/i });
    fireEvent.click(expandButton);

    const contentBox = within(node).getByRole('textbox', { name: 'Content' });
    expect(contentBox).toHaveValue('Hello world');

    fireEvent.change(contentBox, { target: { value: 'Updated notes' } });
    const saveButton = within(node).getByRole('button', { name: 'Save' });
    fireEvent.click(saveButton);

    expect(useCanvasStore.getState().nodes[0].content).toBe('Updated notes');
  });

  it('edits text node titles inline', async () => {
    mockWorkspaceFetch({
      nodes: [
        {
          id: 'node-1',
          type: 'text',
          x: 0,
          y: 0,
          z: 1,
          title: 'First node',
        },
      ],
      edges: [],
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    fireEvent.doubleClick(screen.getByText('First node'));

    const titleInput = screen.getByRole('textbox', { name: /edit node title/i });
    fireEvent.change(titleInput, { target: { value: 'Renamed node' } });
    fireEvent.keyDown(titleInput, { key: 'Enter' });

    expect(useCanvasStore.getState().nodes[0].title).toBe('Renamed node');
  });

  it('supports additive and toggle multi-selection via clicks', async () => {
    mockWorkspaceFetch({
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
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const firstNode = screen.getByRole('button', { name: /first node text node/i });
    const secondNode = screen.getByRole('button', { name: /second node text node/i });

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
    mockWorkspaceFetch({
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
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const workspace = screen.getByTestId('canvas-workspace');
    const firstNode = screen.getByRole('button', { name: /first node text node/i });
    const secondNode = screen.getByRole('button', { name: /second node text node/i });

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
    mockWorkspaceFetch({
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
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const workspace = screen.getByTestId('canvas-workspace');
    const firstNode = screen.getByRole('button', { name: /first node text node/i });
    const secondNode = screen.getByRole('button', { name: /second node text node/i });
    const thirdNode = screen.getByRole('button', { name: /third node text node/i });

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
    mockWorkspaceFetch({
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
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const firstNode = screen.getByRole('button', { name: /first node text node/i });
    const secondNode = screen.getByRole('button', { name: /second node text node/i });

    fireEvent.click(firstNode);
    expect(useCanvasStore.getState().selectedNodeIds).toEqual(['node-1']);

    fireEvent.mouseDown(secondNode);
    fireEvent.focus(secondNode);
    fireEvent.click(secondNode, { shiftKey: true });

    expect(useCanvasStore.getState().selectedNodeIds).toEqual(['node-1', 'node-2']);
    expect(useCanvasStore.getState().selectedNodeId).toBe('node-2');
  });

  it('connects nodes from the context menu', async () => {
    mockWorkspaceFetch({
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
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const sourceNode = screen.getByRole('button', { name: /first node text node/i });
    fireEvent.contextMenu(sourceNode);

    const connectItem = screen.getByRole('menuitem', { name: /connect node/i });
    fireEvent.click(connectItem);

    await waitFor(() => expect(screen.getByTestId('connect-mode-banner')).toBeInTheDocument());

    const relationSelect = screen.getByLabelText(/edge type/i);
    const labelInput = screen.getByLabelText(/edge label/i);
    expect(labelInput).toHaveValue('Dependency');
    fireEvent.change(relationSelect, { target: { value: 'relates_to' } });
    expect(labelInput).toHaveValue('Relates to');
    fireEvent.change(labelInput, { target: { value: 'Cites' } });

    const targetNode = screen.getByRole('button', { name: /second node text node/i });
    fireEvent.click(targetNode);

    await waitFor(() => expect(useCanvasStore.getState().edges).toHaveLength(1));

    const [edge] = useCanvasStore.getState().edges;
    expect(edge.sourceNodeId).toBe('node-1');
    expect(edge.targetNodeId).toBe('node-2');
    expect(edge.relationType).toBe('relates_to');
    expect(edge.label).toBe('Cites');
    await waitFor(() =>
      expect(screen.queryByTestId('connect-mode-banner')).not.toBeInTheDocument()
    );
  });

  it('connects nodes with a custom edge type', async () => {
    mockWorkspaceFetch({
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
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const sourceNode = screen.getByRole('button', { name: /first node text node/i });
    fireEvent.contextMenu(sourceNode);

    const connectItem = screen.getByRole('menuitem', { name: /connect node/i });
    fireEvent.click(connectItem);

    await waitFor(() => expect(screen.getByTestId('connect-mode-banner')).toBeInTheDocument());

    const relationSelect = screen.getByLabelText(/edge type/i);
    const labelInput = screen.getByLabelText(/edge label/i);
    fireEvent.change(relationSelect, { target: { value: '__custom__' } });

    const customTypeInput = screen.getByLabelText(/custom type/i);
    fireEvent.change(customTypeInput, { target: { value: 'blocks' } });

    expect(labelInput).toHaveValue('Blocks');

    const targetNode = screen.getByRole('button', { name: /second node text node/i });
    fireEvent.click(targetNode);

    await waitFor(() => expect(useCanvasStore.getState().edges).toHaveLength(1));

    const [edge] = useCanvasStore.getState().edges;
    expect(edge.relationType).toBe('blocks');
  });

  it('requires confirmation when deleting a node with linked artifacts', async () => {
    mockWorkspaceFetch({
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
    });

    render(<Home />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await waitFor(() => expect(useCanvasStore.getState().edges).toHaveLength(1));

    const sourceNode = screen.getByRole('button', { name: /first node text node/i });
    fireEvent.contextMenu(sourceNode);

    const deleteItem = screen.getByRole('menuitem', { name: /delete node/i });
    fireEvent.click(deleteItem);

    const dialog = await screen.findByRole('dialog', { name: /delete 1 node/i });

    expect(dialog).toHaveTextContent(/linked edges:/i);
    expect(dialog).toHaveTextContent(/1 edge/i);
  });
});
