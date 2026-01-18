import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useChatTurns } from "./useChatTurns";
import type { TurnResponse } from "./turnTypes";

const mockFetch = vi.fn();

global.fetch = mockFetch as unknown as typeof fetch;

describe("useChatTurns", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("filters to conversational turns", async () => {
    const sessionIds = ["session-1"];
    const turns: TurnResponse[] = [
      {
        id: 1,
        sessionId: "session-1",
        sequenceNumber: 1,
        timestamp: "2024-01-01T00:00:00Z",
        actor: "user",
        type: "user_input",
        summary: "User input submitted",
        payload: { command: "Hello" },
        originSequenceNumber: null,
        relatedNodeId: null,
        relatedEdgeId: null,
      },
      {
        id: 2,
        sessionId: "session-1",
        sequenceNumber: 2,
        timestamp: "2024-01-01T00:00:02Z",
        actor: "system",
        type: "node_created",
        summary: "Node created",
        payload: {},
        originSequenceNumber: null,
        relatedNodeId: 1,
        relatedEdgeId: null,
      },
      {
        id: 3,
        sessionId: "session-1",
        sequenceNumber: 3,
        timestamp: "2024-01-01T00:00:03Z",
        actor: "system",
        type: "system_message",
        summary: "Status",
        payload: { message: "All set" },
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
      useChatTurns({
        sessionIds,
        enabled: true,
        pollIntervalMs: 60000,
      })
    );

    await waitFor(() => {
      expect(result.current.turns).toHaveLength(2);
    });

    expect(result.current.turns.map((turn) => turn.id)).toEqual([1, 3]);
    unmount();
  });

  it("advances after_sequence when only non-chat turns arrive", async () => {
    const sessionIds = ["session-1"];
    const turns: TurnResponse[] = [
      {
        id: 1,
        sessionId: "session-1",
        sequenceNumber: 5,
        timestamp: "2024-01-01T00:00:00Z",
        actor: "system",
        type: "node_created",
        summary: "Node created",
        payload: {},
        originSequenceNumber: null,
        relatedNodeId: 1,
        relatedEdgeId: null,
      },
    ];

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ turns, count: turns.length }),
      })
      .mockResolvedValue({
        ok: true,
        json: async () => ({ turns: [], count: 0 }),
      });

    const { unmount } = renderHook(() =>
      useChatTurns({
        sessionIds,
        enabled: true,
        pollIntervalMs: 500,
      })
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    await waitFor(
      () => {
        expect(mockFetch.mock.calls.length).toBeGreaterThanOrEqual(2);
      },
      { timeout: 2000 }
    );

    const secondUrl = String(mockFetch.mock.calls[1]?.[0]);
    expect(secondUrl).toContain("after_sequence=5");
    unmount();
  });
});
