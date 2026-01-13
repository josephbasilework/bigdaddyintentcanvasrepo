import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { DashboardNode } from "../DashboardNode";
import { useCanvasStore } from "../../../state/canvasStore";

describe("DashboardNode", () => {
  beforeEach(() => {
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

  it("renders live workspace stats", () => {
    useCanvasStore.setState({
      nodes: [
        { id: "dash", type: "dashboard", x: 0, y: 0, z: 0, title: "Dashboard" },
        { id: "n1", type: "text", x: 10, y: 20, z: 0, title: "Note 1" },
        { id: "n2", type: "plan", x: 40, y: 30, z: 0, title: "Plan 1" },
      ],
      edges: [
        {
          id: "edge-1",
          sourceNodeId: "n1",
          targetNodeId: "n2",
          relationType: "depends_on",
        },
      ],
      documents: [
        {
          id: "doc-1",
          nodeId: "n1",
          title: "Doc 1",
          content: "Body",
          createdAt: new Date(),
          updatedAt: new Date(),
        },
      ],
      selectedNodeId: "n1",
    });

    render(<DashboardNode nodeId="dash" />);

    expect(screen.getByRole("region", { name: /live dashboard/i })).toBeInTheDocument();
    expect(screen.getByText("Nodes")).toBeInTheDocument();
    expect(screen.getByText("Edges")).toBeInTheDocument();
    expect(screen.getByText("Docs")).toBeInTheDocument();
    expect(screen.getByText("Selected")).toBeInTheDocument();
    expect(screen.getByText("Depends On · 1")).toBeInTheDocument();
    expect(screen.getByText("Text · 1")).toBeInTheDocument();
    expect(screen.getByText("Plan · 1")).toBeInTheDocument();
  });

  it("updates counts when the store changes", () => {
    useCanvasStore.setState({
      nodes: [{ id: "dash", type: "dashboard", x: 0, y: 0, z: 0, title: "Dashboard" }],
    });

    render(<DashboardNode nodeId="dash" />);

    expect(screen.getByText("No nodes yet")).toBeInTheDocument();

    act(() => {
      useCanvasStore.setState({
        nodes: [
          { id: "dash", type: "dashboard", x: 0, y: 0, z: 0, title: "Dashboard" },
          { id: "n1", type: "document", x: 10, y: 10, z: 0, title: "Doc" },
        ],
      });
    });

    expect(screen.getByText("Document · 1")).toBeInTheDocument();
  });
});
