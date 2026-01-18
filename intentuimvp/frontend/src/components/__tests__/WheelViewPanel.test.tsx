import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { WheelViewPanel } from "../WheelView/WheelViewPanel";
import type { TurnResponse } from "@/hooks/turnTypes";
import { useCanvasStore } from "@/state/canvasStore";

describe("WheelViewPanel", () => {
  afterEach(() => {
    useCanvasStore.setState({ nodes: [] });
  });

  const turns: TurnResponse[] = [
    {
      id: 1,
      sessionId: "session-1",
      sequenceNumber: 1,
      timestamp: "2024-01-01T00:00:01Z",
      actor: "user",
      type: "user_input",
      summary: "User input submitted",
      payload: { command: "Create a node" },
      originSequenceNumber: null,
      relatedNodeId: null,
      relatedEdgeId: null,
    },
    {
      id: 2,
      sessionId: "session-1",
      sequenceNumber: 2,
      timestamp: "2024-01-01T00:00:05Z",
      actor: "system",
      type: "node_created",
      summary: "Node created",
      payload: { node_id: 42 },
      originSequenceNumber: null,
      relatedNodeId: 42,
      relatedEdgeId: null,
    },
  ];

  it("renders turn summaries and shows details on expand", () => {
    render(<WheelViewPanel turns={turns} />);

    expect(screen.getByText("Create a node")).toBeInTheDocument();
    expect(screen.getByText("Node created")).toBeInTheDocument();

    const nodeSummary = screen.getByText("Node created");
    const turnCard = nodeSummary.closest(".wheel-turn");
    expect(turnCard).not.toBeNull();
    if (!turnCard) {
      return;
    }

    fireEvent.click(within(turnCard).getByRole("button", { name: "Details" }));

    expect(within(turnCard).getByText("Payload")).toBeInTheDocument();
    expect(within(turnCard).getByText("Related node")).toBeInTheDocument();
    expect(within(turnCard).getByText("42")).toBeInTheDocument();
  });

  it("filters turns by type selection", () => {
    render(<WheelViewPanel turns={turns} />);

    fireEvent.change(screen.getByLabelText("Type filter"), {
      target: { value: "crud" },
    });

    expect(screen.queryByText("Create a node")).not.toBeInTheDocument();
    expect(screen.getByText("Node created")).toBeInTheDocument();
  });

  it("shows response type tags for response turns", () => {
    const responseTurns: TurnResponse[] = [
      {
        id: 9,
        sessionId: "session-1",
        sequenceNumber: 9,
        timestamp: "2024-01-01T00:00:09Z",
        actor: "agent",
        type: "agent_response",
        summary: "Need clarification",
        payload: { prompt: "Which metric should I use?" },
        responseType: "clarification",
        originSequenceNumber: null,
        relatedNodeId: null,
        relatedEdgeId: null,
      },
    ];

    render(<WheelViewPanel turns={responseTurns} />);

    expect(screen.getByText("Clarification")).toBeInTheDocument();
  });

  it("linkifies references in turn summaries", () => {
    useCanvasStore.setState({
      nodes: [{ id: "7", type: "text", x: 0, y: 0, z: 0, title: "Project Plan" }],
    });

    const linkedTurns: TurnResponse[] = [
      {
        id: 1,
        sessionId: "session-1",
        sequenceNumber: 1,
        timestamp: "2024-01-01T00:00:01Z",
        actor: "user",
        type: "user_input",
        summary: "User input submitted",
        payload: { command: "Reference turn 2 and Project Plan." },
        originSequenceNumber: null,
        relatedNodeId: null,
        relatedEdgeId: null,
      },
      {
        id: 2,
        sessionId: "session-1",
        sequenceNumber: 2,
        timestamp: "2024-01-01T00:00:05Z",
        actor: "system",
        type: "system_message",
        summary: "Acknowledged",
        payload: { message: "Noted." },
        originSequenceNumber: null,
        relatedNodeId: null,
        relatedEdgeId: null,
      },
    ];

    render(<WheelViewPanel turns={linkedTurns} />);

    expect(screen.getByRole("link", { name: "turn 2" })).toHaveAttribute(
      "href",
      "#turn-2"
    );
    expect(screen.getByRole("link", { name: "Project Plan" })).toHaveAttribute(
      "href",
      "#node-7"
    );
  });
});
