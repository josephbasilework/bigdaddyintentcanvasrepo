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
});
