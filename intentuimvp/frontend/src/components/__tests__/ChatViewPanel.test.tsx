import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatViewPanel } from "../ChatView/ChatViewPanel";
import type { TurnResponse } from "@/hooks/turnTypes";

describe("ChatViewPanel", () => {
  it("renders markdown and clarification tags", () => {
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
        relatedNodeId: null,
        relatedEdgeId: null,
      },
      {
        id: 2,
        sessionId: "session-1",
        sequenceNumber: 2,
        timestamp: "2024-01-01T00:00:05Z",
        actor: "system",
        type: "assumption_modified",
        summary: "Assumption modified",
        payload: { final_text: "Use UTC" },
        relatedNodeId: null,
        relatedEdgeId: null,
      },
    ];

    render(<ChatViewPanel turns={turns} />);

    const strongText = screen.getByText("world");
    expect(strongText.tagName).toBe("STRONG");
    expect(screen.getByText("Clarification")).toBeInTheDocument();
    expect(
      screen.getByText("Clarification updated: Use UTC")
    ).toBeInTheDocument();
  });
});
