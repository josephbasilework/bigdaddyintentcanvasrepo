import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { useCanvasStore } from '../state/canvasStore';
import Home from '../app/page';

vi.mock('react-zoom-pan-pinch', () => ({
  TransformWrapper: ({ children }: { children: ReactNode }) => (
    <div data-testid="transform-wrapper">{children}</div>
  ),
  TransformComponent: ({ children }: { children: ReactNode }) => (
    <div data-testid="transform-component">{children}</div>
  ),
}));

vi.mock('react-draggable', () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => (
    <div data-testid="draggable">{children}</div>
  ),
}));

describe('workspace canvas', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    useCanvasStore.setState({
      nodes: [],
      edges: [],
      documents: [],
      selectedNodeId: null,
      past: [],
      future: [],
    });

    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ nodes: [], edges: [] }),
    });

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
});
