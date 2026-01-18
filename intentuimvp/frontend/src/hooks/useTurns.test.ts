import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useTurns } from "./useTurns";
import type { TurnResponse } from "./turnTypes";

const mockFetch = vi.fn();

global.fetch = mockFetch as unknown as typeof fetch;

describe("useTurns", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("returns all turns in chronological order", async () => {
    const sessionIds = ["session-1"];
    const turns: TurnResponse[] = [
      {
        id: 2,
        sessionId: "session-1",
        sequenceNumber: 2,
        timestamp: "2024-01-01T00:00:05Z",
        actor: "system",
        type: "node_created",
        summary: "Node created",
        payload: {},
        originSequenceNumber: null,
        relatedNodeId: 1,
        relatedEdgeId: null,
      },
      {
        id: 1,
        sessionId: "session-1",
        sequenceNumber: 1,
        timestamp: "2024-01-01T00:00:01Z",
        actor: "user",
        type: "user_input",
        summary: "User input submitted",
        payload: { command: "Hello" },
        originSequenceNumber: null,
        relatedNodeId: null,
        relatedEdgeId: null,
      },
    ];

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ turns, count: turns.length }),
    });

    const { result, unmount } = renderHook(() =>
      useTurns({
        sessionIds,
        enabled: true,
        pollIntervalMs: 60000,
      })
    );

    await waitFor(() => {
      expect(result.current.turns).toHaveLength(2);
    });

    expect(result.current.turns.map((turn) => turn.id)).toEqual([1, 2]);
    unmount();
  });

  it("includes filters in the turns query", async () => {
    const sessionIds = ["session-1"];
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ turns: [], count: 0 }),
    });

    const { unmount } = renderHook(() =>
      useTurns({
        sessionIds,
        enabled: true,
        pollIntervalMs: 60000,
        filters: {
          actorGroups: ["User", "job"],
          categories: ["crud"],
          eventTypes: ["node.created"],
          relatedNodeId: 42,
        },
      })
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });

    const url = String(mockFetch.mock.calls[0][0]);
    const params = new URL(url).searchParams;
    expect(params.getAll("actor_group").sort()).toEqual(["job", "user"]);
    expect(params.getAll("category")).toEqual(["crud"]);
    expect(params.getAll("event_type")).toEqual(["node.created"]);
    expect(params.get("related_node_id")).toBe("42");

    unmount();
  });
});
