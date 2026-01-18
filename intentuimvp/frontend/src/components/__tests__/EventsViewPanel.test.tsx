import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EventsViewPanel } from "../EventsView/EventsViewPanel";
import type { TurnResponse } from "@/hooks/turnTypes";

const baseTurns: TurnResponse[] = [
  {
    id: 1,
    sessionId: "session-1",
    sequenceNumber: 1,
    timestamp: "2024-01-01T00:00:01Z",
    actor: "user",
    type: "user_input",
    summary: "User input submitted",
    payload: { command: "Plan sprint" },
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
  {
    id: 3,
    sessionId: "session-1",
    sequenceNumber: 3,
    timestamp: "2024-01-01T00:00:10Z",
    actor: "system",
    type: "job_failed",
    summary: "Job failed",
    payload: { job_id: "job-9" },
    originSequenceNumber: null,
    relatedNodeId: null,
    relatedEdgeId: null,
  },
];

describe("EventsViewPanel", () => {
  it("expands to show payload details", () => {
    render(<EventsViewPanel turns={baseTurns} />);

    expect(screen.getByText("Plan sprint")).toBeInTheDocument();
    expect(screen.getByText("Node created")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /node\.created/i })
    );

    expect(screen.getByText("Payload")).toBeInTheDocument();
    expect(screen.getByText(/node_id/)).toBeInTheDocument();
  });

  it("filters by event type selection", () => {
    render(<EventsViewPanel turns={baseTurns} />);

    const select = screen.getByLabelText("Event type filter") as HTMLSelectElement;
    for (const option of Array.from(select.options)) {
      option.selected = option.value === "node.created";
    }
    fireEvent.change(select);

    expect(screen.getByText("Node created")).toBeInTheDocument();
    expect(screen.queryByText("Plan sprint")).not.toBeInTheDocument();
    expect(screen.queryByText("Job failed")).not.toBeInTheDocument();
  });

  it("filters by actor and node scope", () => {
    render(<EventsViewPanel turns={baseTurns} />);

    fireEvent.change(screen.getByPlaceholderText("Node ID"), {
      target: { value: "42" },
    });

    expect(screen.getByText("Node created")).toBeInTheDocument();
    expect(screen.queryByText("Job failed")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Node ID"), {
      target: { value: "" },
    });

    fireEvent.click(screen.getByRole("button", { name: "User" }));
    fireEvent.click(screen.getByRole("button", { name: "System" }));
    fireEvent.click(screen.getByRole("button", { name: "External" }));

    expect(screen.getByText("Job failed")).toBeInTheDocument();
    expect(screen.queryByText("Node created")).not.toBeInTheDocument();
    expect(screen.queryByText("Plan sprint")).not.toBeInTheDocument();
  });

  it("labels response types in event badges", () => {
    const responseTurns: TurnResponse[] = [
      {
        id: 10,
        sessionId: "session-2",
        sequenceNumber: 1,
        timestamp: "2024-01-02T00:00:01Z",
        actor: "agent",
        type: "agent_response",
        summary: "Proposal ready",
        payload: { message: "I can draft the outline." },
        responseType: "proposal",
        originSequenceNumber: null,
        relatedNodeId: null,
        relatedEdgeId: null,
      },
    ];

    render(<EventsViewPanel turns={responseTurns} />);

    const matches = screen.getAllByText("response.proposal");
    expect(
      matches.some((element) => element.classList.contains("events-badge"))
    ).toBe(true);
  });
});
