import { beforeEach, describe, expect, it } from "vitest";
import { useOfflineQueueStore, type OfflineRequestData } from "./offlineQueueStore";

describe("offlineQueueStore", () => {
  const initialState = {
    activeSessionId: null,
    connectionState: "closed" as const,
    queue: [],
    isFlushingQueue: false,
    lastFlushedEventCount: 0,
    lastFlushTimestamp: null,
  };

  const baseRequest: OfflineRequestData = {
    url: "http://localhost:8000/api/commands",
    method: "POST",
    body: { command: "hello" },
    kind: "command",
    sessionId: "session-1",
  };

  beforeEach(() => {
    localStorage.clear();
    useOfflineQueueStore.setState(initialState);
  });

  it("persists queue per session", () => {
    useOfflineQueueStore.getState().setSessionId("session-1");
    useOfflineQueueStore.getState().enqueue(baseRequest, { id: "req-1" });

    expect(useOfflineQueueStore.getState().queue).toHaveLength(1);
    expect(
      localStorage.getItem("intentui_offline_queue_v1:session-1")
    ).toContain("req-1");

    useOfflineQueueStore.getState().setSessionId("session-2");
    expect(useOfflineQueueStore.getState().queue).toHaveLength(0);

    useOfflineQueueStore.getState().setSessionId("session-1");
    expect(useOfflineQueueStore.getState().queue).toHaveLength(1);
  });

  it("updates and deletes queued events", () => {
    useOfflineQueueStore.getState().setSessionId("session-1");
    useOfflineQueueStore.getState().enqueue(baseRequest, { id: "req-1" });

    useOfflineQueueStore.getState().updateQueuedEvent("req-1", {
      ...baseRequest,
      body: { command: "updated" },
    });

    const updated = useOfflineQueueStore.getState().queue[0];
    expect(updated.data).toMatchObject({ body: { command: "updated" } });

    useOfflineQueueStore.getState().deleteQueuedEvent("req-1");
    expect(useOfflineQueueStore.getState().queue).toHaveLength(0);
  });
});
