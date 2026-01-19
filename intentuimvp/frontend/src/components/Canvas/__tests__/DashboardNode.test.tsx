import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act, fireEvent, within } from "@testing-library/react";
import { DashboardNode } from "../DashboardNode";
import { useDashboardStream } from "../../../hooks/useDashboardStream";
import { useCanvasStore } from "../../../state/canvasStore";

vi.mock("../../../hooks/useDashboardStream", () => ({
  useDashboardStream: vi.fn(),
}));

const mockUseDashboardStream = useDashboardStream as unknown as ReturnType<typeof vi.fn>;

const emptyStream = {
  stats: {
    entityCounts: {
      workspace_state: 0,
      node: 0,
      edge: 0,
      job: 0,
      artifact: 0,
      tool_output: 0,
      external_state: 0,
    },
    recentChanges: [],
    isSubscribed: false,
    lastUpdateTime: null,
    activeSubscriptions: [],
  },
  isConnected: false,
  lastUpdate: null,
  recentChanges: [],
  externalState: {
    data: null,
    status: "idle",
    error: null,
    lastUpdated: null,
  },
};

describe("DashboardNode", () => {
  beforeEach(() => {
    mockUseDashboardStream.mockReturnValue(emptyStream);
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
          relationType: "dependency",
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

  it("shows connection status when identifiers are numeric", () => {
    useCanvasStore.setState({
      canvasId: 7,
      nodes: [{ id: "42", type: "dashboard", x: 0, y: 0, z: 0, title: "Dashboard" }],
    });

    render(<DashboardNode nodeId="42" />);

    expect(screen.getByText("Connecting")).toBeInTheDocument();
    expect(screen.getByText("Awaiting subscription confirmation.")).toBeInTheDocument();
    expect(screen.getByText("Last update: No updates yet")).toBeInTheDocument();
  });

  it("prompts to sync when dashboard id is not persisted", () => {
    useCanvasStore.setState({
      canvasId: 7,
      nodes: [{ id: "dash", type: "dashboard", x: 0, y: 0, z: 0, title: "Dashboard" }],
    });

    render(<DashboardNode nodeId="dash" />);

    expect(screen.getByText("Sync the dashboard to the backend to enable streaming.")).toBeInTheDocument();
  });

  it("renders streaming metrics when data is available", () => {
    const now = new Date("2026-01-13T00:00:00Z");
    const streamPayload = {
      stats: {
        entityCounts: {
          workspace_state: 2,
          node: 4,
          edge: 1,
          job: 3,
          artifact: 2,
          tool_output: 5,
          external_state: 1,
        },
        recentChanges: [
          {
            target: "job",
            sourceId: "job-9",
            changeType: "created",
            timestamp: now,
            data: {},
          },
        ],
        isSubscribed: true,
        lastUpdateTime: now,
        activeSubscriptions: [
          { id: 1, subscriptionTarget: "job", sourceId: "job-9" },
          { id: 2, subscriptionTarget: "node" },
        ],
      },
      isConnected: true,
      lastUpdate: now,
      recentChanges: [
        {
          target: "job",
          sourceId: "job-9",
          changeType: "created",
          timestamp: now,
          data: {},
        },
      ],
      externalState: {
        data: { status: "ok" },
        status: "connected",
        error: null,
        lastUpdated: now,
      },
    };

    mockUseDashboardStream.mockReturnValue(streamPayload);

    useCanvasStore.setState({
      canvasId: 7,
      nodes: [{ id: "42", type: "dashboard", x: 0, y: 0, z: 0, title: "Dashboard" }],
    });

    render(<DashboardNode nodeId="42" />);

    expect(screen.getByText("Streaming Signals")).toBeInTheDocument();
    expect(screen.getByText("Node Events")).toBeInTheDocument();
    expect(screen.getByText("Jobs")).toBeInTheDocument();
    expect(screen.getByText("Active Subscriptions")).toBeInTheDocument();
    expect(screen.getByText("Job · job-9")).toBeInTheDocument();
    expect(screen.getByText("Job · Created")).toBeInTheDocument();
  });

  it("shows external state configuration details", () => {
    useCanvasStore.setState({
      nodes: [
        {
          id: "dash",
          type: "dashboard",
          x: 0,
          y: 0,
          z: 0,
          title: "Dashboard",
          metadata: {
            dashboardConfig: { type: "api", pollIntervalMs: 5000 },
          },
        },
      ],
    });

    render(<DashboardNode nodeId="dash" />);

    const configToggle = screen.getByRole("button", { name: /configure/i });
    const header = configToggle.parentElement;
    if (!header) {
      throw new Error("External state header not found");
    }
    expect(within(header).getByText("External State")).toBeInTheDocument();
    expect(screen.getByText("API endpoint not set")).toBeInTheDocument();

    fireEvent.click(configToggle);
    expect(screen.getByText("Source type")).toBeInTheDocument();
    expect(screen.getByText("Poll interval (ms)")).toBeInTheDocument();
  });
});
