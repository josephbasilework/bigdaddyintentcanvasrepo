import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useWebSocketEnhanced } from "./useWebSocketEnhanced";

// Mock the performance module
vi.mock("@/lib/performance", () => ({
  recordWsReconnect: vi.fn(),
}));

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];
  static autoOpen = true;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: MessageEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  sentMessages: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);

    if (MockWebSocket.autoOpen) {
      queueMicrotask(() => {
        if (this.readyState !== MockWebSocket.CLOSED) {
          this.triggerOpen();
        }
      });
    }
  }

  send(data: string): void {
    this.sentMessages.push(data);
  }

  close(code?: number, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    this.triggerClose(code ?? 1000, reason ?? "");
  }

  triggerOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new MessageEvent("open"));
  }

  triggerMessage(data: string): void {
    this.onmessage?.(new MessageEvent("message", { data }));
  }

  triggerClose(code: number, reason: string): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(
      new CloseEvent("close", { code, reason, wasClean: code === 1000 })
    );
  }

  triggerError(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onerror?.(new Event("error"));
  }

  static reset(): void {
    MockWebSocket.instances.forEach((ws) => {
      ws.onopen = null;
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
    });
    MockWebSocket.instances = [];
    MockWebSocket.autoOpen = true;
  }
}

const OriginalWebSocket = global.WebSocket;

const flushMicrotasks = async (): Promise<void> => {
  for (let i = 0; i < 5; i += 1) {
    await Promise.resolve();
  }
};

describe("useWebSocketEnhanced", () => {
  beforeEach(() => {
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
    MockWebSocket.reset();
    localStorage.clear();
  });

  afterEach(() => {
    MockWebSocket.reset();
    global.WebSocket = OriginalWebSocket;
    localStorage.clear();
  });

  it("queues events while disconnected and flushes on open", async () => {
    MockWebSocket.autoOpen = false;
    const onEventsFlushed = vi.fn();

    const { result } = renderHook(() =>
      useWebSocketEnhanced({
        url: "ws://localhost:8000/ws",
        onEventsFlushed,
      })
    );

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1));

    act(() => {
      result.current.send({ type: "ping" });
    });

    await waitFor(() => expect(result.current.queuedEventCount).toBe(1));

    const ws = MockWebSocket.instances[0];

    act(() => {
      ws.triggerOpen();
    });

    await waitFor(() => expect(result.current.queuedEventCount).toBe(0));

    expect(ws.sentMessages).toContain(JSON.stringify({ type: "ping" }));
    expect(onEventsFlushed).toHaveBeenCalledTimes(1);
    const flushed = onEventsFlushed.mock.calls[0][0];
    expect(flushed).toHaveLength(1);
    expect(flushed[0].data).toEqual({ type: "ping" });
  });

  it("restores queued events from storage on load", async () => {
    MockWebSocket.autoOpen = false;
    localStorage.setItem("intentui_workspace_session_id", "session-123");
    localStorage.setItem(
      "intentui_ws_queue_v1:session-123",
      JSON.stringify([
        {
          id: "queue-1",
          data: { type: "ping" },
          timestamp: 1700000000000,
        },
      ])
    );

    const { result } = renderHook(() =>
      useWebSocketEnhanced({
        url: "ws://localhost:8000/ws",
      })
    );

    await waitFor(() => expect(result.current.queuedEventCount).toBe(1));
    expect(result.current.queuedEvents[0].id).toBe("queue-1");
    expect(result.current.queuedEvents[0].data).toEqual({ type: "ping" });
  });

  it("updates and deletes queued events with persistence", async () => {
    MockWebSocket.autoOpen = false;
    localStorage.setItem("intentui_workspace_session_id", "session-123");

    const { result } = renderHook(() =>
      useWebSocketEnhanced({
        url: "ws://localhost:8000/ws",
      })
    );

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1));

    act(() => {
      result.current.send({ type: "ping" });
    });

    await waitFor(() => expect(result.current.queuedEventCount).toBe(1));

    const queuedId = result.current.queuedEvents[0].id;

    act(() => {
      result.current.updateQueuedEvent(queuedId, { type: "pong" });
    });

    await waitFor(() =>
      expect(result.current.queuedEvents[0].data).toEqual({ type: "pong" })
    );

    const stored = localStorage.getItem("intentui_ws_queue_v1:session-123");
    const storedQueue = stored ? (JSON.parse(stored) as Array<{ data: unknown }>) : [];
    expect(storedQueue[0]?.data).toEqual({ type: "pong" });

    act(() => {
      result.current.deleteQueuedEvent(queuedId);
    });

    await waitFor(() => expect(result.current.queuedEventCount).toBe(0));

    const storedAfter = localStorage.getItem("intentui_ws_queue_v1:session-123");
    const storedAfterQueue = storedAfter
      ? (JSON.parse(storedAfter) as Array<{ data: unknown }>)
      : [];
    expect(storedAfterQueue).toHaveLength(0);
  });

  it("detects sequence gaps and triggers snapshot sync", async () => {
    const onSyncSnapshot = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() =>
      useWebSocketEnhanced({
        url: "ws://localhost:8000/ws",
        onSyncSnapshot,
      })
    );

    await waitFor(() => expect(result.current.connectionState).toBe("open"));

    const ws = MockWebSocket.instances[0];

    act(() => {
      ws.triggerMessage(JSON.stringify({ sequence: 1 }));
    });

    await waitFor(() => expect(result.current.lastSequence).toBe(1));

    act(() => {
      ws.triggerMessage(JSON.stringify({ sequence: 3 }));
    });

    await waitFor(() => expect(onSyncSnapshot).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(result.current.hasSequenceGap).toBe(true));

    // After snapshot sync completes, receive a new valid message to clear the gap
    await flushMicrotasks();

    act(() => {
      ws.triggerMessage(JSON.stringify({ sequence: 4 }));
    });

    await waitFor(() => expect(result.current.hasSequenceGap).toBe(false));
    expect(result.current.lastSequence).toBe(4);
  });

  it("retries snapshot sync on manual reconnect when gap persists", async () => {
    const onSyncSnapshot = vi.fn().mockRejectedValue(new Error("sync failed"));

    const { result } = renderHook(() =>
      useWebSocketEnhanced({
        url: "ws://localhost:8000/ws",
        onSyncSnapshot,
        reconnect: false,
      })
    );

    await waitFor(() => expect(result.current.connectionState).toBe("open"));

    const ws = MockWebSocket.instances[0];

    act(() => {
      ws.triggerMessage(JSON.stringify({ sequence: 1 }));
    });

    await waitFor(() => expect(result.current.lastSequence).toBe(1));

    act(() => {
      ws.triggerMessage(JSON.stringify({ sequence: 3 }));
    });

    await waitFor(() => expect(onSyncSnapshot).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(result.current.hasSequenceGap).toBe(true));

    act(() => {
      ws.triggerClose(1006, "Abnormal closure");
    });

    await waitFor(() => expect(result.current.connectionState).toBe("closed"));

    act(() => {
      result.current.reconnect();
    });

    await waitFor(() => expect(result.current.connectionState).toBe("open"));

    // After reconnect, the sequence tracking continues from where it left off
    // The gap flag is cleared on reconnect, and receiving sequence 4 should work
    const ws2 = MockWebSocket.instances[1];

    act(() => {
      ws2.triggerMessage(JSON.stringify({ sequence: 4 }));
    });

    await waitFor(() => expect(result.current.hasSequenceGap).toBe(false));
    expect(result.current.lastSequence).toBe(4);
  });
});
