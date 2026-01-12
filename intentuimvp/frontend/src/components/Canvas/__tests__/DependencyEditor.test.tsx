import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DependencyEditor, DependencyDisplay } from "../DependencyEditor";
import { useCanvasStore } from "../../../state/canvasStore";
import type { CanvasNode, CanvasEdge } from "../../../state/canvasStore";

// Mock the canvas store
vi.mock("../../../state/canvasStore", () => ({
  useCanvasStore: vi.fn(),
}));

const mockUseCanvasStore = useCanvasStore as unknown as ReturnType<typeof vi.fn>;

const createMockStore = (overrides: Partial<ReturnType<typeof useCanvasStore>> = {}) => {
  const defaultNodes: CanvasNode[] = [
    { id: "node-1", type: "text", x: 0, y: 0, z: 0, title: "Node 1" },
    { id: "node-2", type: "text", x: 100, y: 0, z: 0, title: "Node 2" },
    { id: "node-3", type: "graph", x: 200, y: 0, z: 0, title: "Node 3" },
  ];

  const defaultEdges: CanvasEdge[] = [];

  return {
    nodes: defaultNodes,
    edges: defaultEdges,
    addEdge: vi.fn(),
    removeEdge: vi.fn(),
    updateEdge: vi.fn(),
    ...overrides,
  };
};

describe("DependencyEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the dependency editor dialog", () => {
    const store = createMockStore();
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    expect(screen.getByText(/edit dependencies/i)).toBeInTheDocument();
    // Node name appears in the header
    expect(screen.getByText("Node 1")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("shows available nodes in the add dependency dropdown", () => {
    const store = createMockStore();
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    const select = screen.getByRole("combobox", { name: /add dependency/i });
    expect(select).toBeInTheDocument();

    // Should show Node 2 and Node 3 as options (not Node 1 since that's the current node)
    expect(screen.getByRole("option", { name: "Node 2" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Node 3" })).toBeInTheDocument();
  });

  it("excludes already connected nodes from available targets", () => {
    const edges: CanvasEdge[] = [
      { id: "edge-1", sourceNodeId: "node-1", targetNodeId: "node-2", relationType: "depends_on" },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    // Node 2 should not be available since it's already connected
    expect(screen.queryByRole("option", { name: "Node 2" })).not.toBeInTheDocument();
    // Node 3 should still be available
    expect(screen.getByRole("option", { name: "Node 3" })).toBeInTheDocument();
  });

  it("adds a new dependency when selecting a node and clicking add", () => {
    const store = createMockStore();
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    const select = screen.getByRole("combobox", { name: /add dependency/i });
    fireEvent.change(select, { target: { value: "node-2" } });

    const addButton = screen.getByRole("button", { name: /^add$/i });
    fireEvent.click(addButton);

    expect(store.addEdge).toHaveBeenCalledWith(
      expect.objectContaining({
        sourceNodeId: "node-1",
        targetNodeId: "node-2",
        relationType: "depends_on",
      })
    );
  });

  it("adds a new dependency with a custom label", () => {
    const store = createMockStore();
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    const select = screen.getByRole("combobox", { name: /add dependency/i });
    fireEvent.change(select, { target: { value: "node-2" } });

    const labelInput = screen.getByPlaceholderText(/label \(optional\)/i);
    fireEvent.change(labelInput, { target: { value: "Blocks" } });

    const addButton = screen.getByRole("button", { name: /^add$/i });
    fireEvent.click(addButton);

    expect(store.addEdge).toHaveBeenCalledWith(
      expect.objectContaining({
        sourceNodeId: "node-1",
        targetNodeId: "node-2",
        relationType: "depends_on",
        label: "Blocks",
      })
    );
  });

  it("displays outgoing dependencies", () => {
    const edges: CanvasEdge[] = [
      { id: "edge-1", sourceNodeId: "node-1", targetNodeId: "node-2", relationType: "depends_on" },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    expect(screen.getByText(/outgoing dependencies \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText("Node 2")).toBeInTheDocument();
  });

  it("displays incoming dependencies", () => {
    const edges: CanvasEdge[] = [
      { id: "edge-1", sourceNodeId: "node-2", targetNodeId: "node-1", relationType: "supports" },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    expect(screen.getByText(/incoming dependencies \(1\)/i)).toBeInTheDocument();
    // Node 2 appears in both the dropdown and in the incoming list
    expect(screen.getAllByText("Node 2").length).toBeGreaterThanOrEqual(1);
  });

  it("removes a dependency when clicking remove button", () => {
    const edges: CanvasEdge[] = [
      { id: "edge-1", sourceNodeId: "node-1", targetNodeId: "node-2", relationType: "depends_on" },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    const removeButton = screen.getByRole("button", { name: /remove dependency to node 2/i });
    fireEvent.click(removeButton);

    expect(store.removeEdge).toHaveBeenCalledWith("edge-1");
  });

  it("updates edge label when edited", () => {
    const edges: CanvasEdge[] = [
      {
        id: "edge-1",
        sourceNodeId: "node-1",
        targetNodeId: "node-2",
        relationType: "depends_on",
        label: "Depends on",
      },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    const labelInput = screen.getByLabelText(/dependency label to node 2/i);
    fireEvent.change(labelInput, { target: { value: "Custom label" } });
    fireEvent.blur(labelInput);

    expect(store.updateEdge).toHaveBeenCalledWith("edge-1", { label: "Custom label" });
  });

  it("updates edge relation type when changed", () => {
    const edges: CanvasEdge[] = [
      { id: "edge-1", sourceNodeId: "node-1", targetNodeId: "node-2", relationType: "depends_on" },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    // Find the select for the outgoing edge
    const relationSelects = screen.getAllByRole("combobox");
    // First is the "add dependency" select, others are for existing edges
    const edgeRelationSelect = relationSelects[relationSelects.length - 1];

    fireEvent.change(edgeRelationSelect, { target: { value: "supports" } });

    expect(store.updateEdge).toHaveBeenCalledWith("edge-1", expect.objectContaining({
      relationType: "supports",
    }));
  });

  it("keeps custom labels when changing relation type", () => {
    const edges: CanvasEdge[] = [
      {
        id: "edge-1",
        sourceNodeId: "node-1",
        targetNodeId: "node-2",
        relationType: "depends_on",
        label: "Custom label",
      },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    const relationSelects = screen.getAllByRole("combobox");
    const edgeRelationSelect = relationSelects[relationSelects.length - 1];

    fireEvent.change(edgeRelationSelect, { target: { value: "supports" } });

    expect(store.updateEdge).toHaveBeenCalledWith(
      "edge-1",
      expect.objectContaining({
        relationType: "supports",
        label: "Custom label",
      })
    );
  });

  it("updates to the new default label when relation type changes", () => {
    const edges: CanvasEdge[] = [
      {
        id: "edge-1",
        sourceNodeId: "node-1",
        targetNodeId: "node-2",
        relationType: "depends_on",
        label: "Depends on",
      },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    const relationSelects = screen.getAllByRole("combobox");
    const edgeRelationSelect = relationSelects[relationSelects.length - 1];

    fireEvent.change(edgeRelationSelect, { target: { value: "supports" } });

    expect(store.updateEdge).toHaveBeenCalledWith(
      "edge-1",
      expect.objectContaining({
        relationType: "supports",
        label: "Supports",
      })
    );
  });

  it("closes when clicking the Done button", () => {
    const store = createMockStore();
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    const doneButton = screen.getByRole("button", { name: /done/i });
    fireEvent.click(doneButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes when clicking the backdrop", () => {
    const store = createMockStore();
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    // Click the backdrop (the outer div with role="presentation")
    const backdrop = screen.getByRole("presentation");
    fireEvent.click(backdrop);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not close when clicking inside the dialog", () => {
    const store = createMockStore();
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    // Click inside the dialog
    const dialog = screen.getByRole("dialog");
    fireEvent.click(dialog);

    expect(onClose).not.toHaveBeenCalled();
  });

  it("shows 'No outgoing dependencies' when there are none", () => {
    const store = createMockStore();
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    expect(screen.getByText(/no outgoing dependencies/i)).toBeInTheDocument();
  });

  it("shows 'No incoming dependencies' when there are none", () => {
    const store = createMockStore();
    mockUseCanvasStore.mockReturnValue(store);

    const onClose = vi.fn();
    render(<DependencyEditor nodeId="node-1" onClose={onClose} />);

    expect(screen.getByText(/no incoming dependencies/i)).toBeInTheDocument();
  });
});

describe("DependencyDisplay", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when there are no dependencies", () => {
    const store = createMockStore();
    mockUseCanvasStore.mockReturnValue(store);

    const onEdit = vi.fn();
    const { container } = render(<DependencyDisplay nodeId="node-1" onEdit={onEdit} />);

    expect(container.firstChild).toBeNull();
  });

  it("shows outgoing dependency count", () => {
    const edges: CanvasEdge[] = [
      { id: "edge-1", sourceNodeId: "node-1", targetNodeId: "node-2", relationType: "depends_on" },
      { id: "edge-2", sourceNodeId: "node-1", targetNodeId: "node-3", relationType: "references" },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onEdit = vi.fn();
    render(<DependencyDisplay nodeId="node-1" onEdit={onEdit} />);

    expect(screen.getByText("2 out")).toBeInTheDocument();
  });

  it("shows incoming dependency count", () => {
    const edges: CanvasEdge[] = [
      { id: "edge-1", sourceNodeId: "node-2", targetNodeId: "node-1", relationType: "depends_on" },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onEdit = vi.fn();
    render(<DependencyDisplay nodeId="node-1" onEdit={onEdit} />);

    expect(screen.getByText("1 in")).toBeInTheDocument();
  });

  it("shows both incoming and outgoing counts", () => {
    const edges: CanvasEdge[] = [
      { id: "edge-1", sourceNodeId: "node-1", targetNodeId: "node-2", relationType: "depends_on" },
      { id: "edge-2", sourceNodeId: "node-3", targetNodeId: "node-1", relationType: "supports" },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onEdit = vi.fn();
    render(<DependencyDisplay nodeId="node-1" onEdit={onEdit} />);

    expect(screen.getByText("1 out")).toBeInTheDocument();
    expect(screen.getByText("1 in")).toBeInTheDocument();
  });

  it("calls onEdit when clicking Edit Dependencies button", () => {
    const edges: CanvasEdge[] = [
      { id: "edge-1", sourceNodeId: "node-1", targetNodeId: "node-2", relationType: "depends_on" },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onEdit = vi.fn();
    render(<DependencyDisplay nodeId="node-1" onEdit={onEdit} />);

    const editButton = screen.getByRole("button", { name: /edit dependencies/i });
    fireEvent.click(editButton);

    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it("shows Dependencies label", () => {
    const edges: CanvasEdge[] = [
      { id: "edge-1", sourceNodeId: "node-1", targetNodeId: "node-2", relationType: "depends_on" },
    ];
    const store = createMockStore({ edges });
    mockUseCanvasStore.mockReturnValue(store);

    const onEdit = vi.fn();
    render(<DependencyDisplay nodeId="node-1" onEdit={onEdit} />);

    // Multiple elements contain "dependencies" text (label and button)
    expect(screen.getAllByText(/dependencies/i).length).toBeGreaterThanOrEqual(1);
  });
});
