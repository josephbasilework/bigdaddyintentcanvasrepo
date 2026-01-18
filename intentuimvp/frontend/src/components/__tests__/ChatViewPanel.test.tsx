import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ChatViewPanel } from "../ChatView/ChatViewPanel";
import type { TurnResponse } from "@/hooks/turnTypes";
import { useCanvasStore } from "@/state/canvasStore";

describe("ChatViewPanel", () => {
  afterEach(() => {
    useCanvasStore.setState({ nodes: [] });
  });

  it("renders markdown and response tags", () => {
    const turns: TurnResponse[] = [
      {
        id: 1,
        sessionId: "session-1",
        sequenceNumber: 1,
        timestamp: "2024-01-01T00:00:00Z",
        actor: "user",
        type: "user_input",
        summary: "User input submitted",
        payload: { command: "Hello **world**" },
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
        payload: { message: "Got it, noted." },
        responseType: "acknowledgment",
        originSequenceNumber: null,
        relatedNodeId: null,
        relatedEdgeId: null,
      },
    ];

    render(<ChatViewPanel turns={turns} />);

    const strongText = screen.getByText("world");
    expect(strongText.tagName).toBe("STRONG");
    expect(screen.getByText("Acknowledgment")).toBeInTheDocument();
    expect(screen.getByText("Got it, noted.")).toBeInTheDocument();
  });

  it("linkifies explicit references in chat content", () => {
    useCanvasStore.setState({
      nodes: [
        { id: "7", type: "text", x: 0, y: 0, z: 0, title: "Project Plan" },
        { id: "9", type: "text", x: 0, y: 0, z: 0, title: "Alpha" },
      ],
    });

    const turns: TurnResponse[] = [
      {
        id: 1,
        sessionId: "session-1",
        sequenceNumber: 1,
        timestamp: "2024-01-01T00:00:00Z",
        actor: "user",
        type: "user_input",
        summary: "User input submitted",
        payload: {
          command: "Review turn 2 with node 7, @Alpha, and Project Plan.",
        },
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

    render(<ChatViewPanel turns={turns} />);

    expect(screen.getByRole("link", { name: "turn 2" })).toHaveAttribute(
      "href",
      "#turn-2"
    );
    expect(screen.getByRole("link", { name: "node 7" })).toHaveAttribute(
      "href",
      "#node-7"
    );
    expect(screen.getByRole("link", { name: "@Alpha" })).toHaveAttribute(
      "href",
      "#node-9"
    );
    expect(screen.getByRole("link", { name: "Project Plan" })).toHaveAttribute(
      "href",
      "#node-7"
    );
  });
});
