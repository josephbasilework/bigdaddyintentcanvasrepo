/**
 * Unit tests for useWebSocket hook.
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useWebSocket, WebSocketMessage } from "./useWebSocket";

/**
 * Mock WebSocket class for testing.
 */
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: MessageEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  sentMessages: string[] = [];
  private connected: boolean = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    // Auto-connect - use queueMicrotask for test compatibility
    queueMicrotask(() => {
      if (!this.connected) {
        this.connected = true;
        this.readyState = MockWebSocket.OPEN;
        this.triggerOpen();
      }
    });
  }

  send(data: string): void {
    this.sentMessages.push(data);
  }

  close(code?: number, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    this.triggerClose(code || 1000, reason || "");
  }

  triggerOpen(): void {
    if (this.onopen) {
      this.onopen(new MessageEvent("open"));
    }
  }

  triggerMessage(data: string): void {
    if (this.onmessage) {
      this.onmessage(new MessageEvent("message", { data }));
    }
  }

  triggerClose(code: number, reason: string): void {
    if (this.onclose) {
      this.onclose(
        new CloseEvent("close", { code, reason, wasClean: code === 1000 })
      );
    }
  }

  triggerError(): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onerror) {
      this.onerror(new Event("error"));
    }
  }

  static reset(): void {
    MockWebSocket.instances.forEach((ws) => {
      ws.onopen = null;
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
    });
    MockWebSocket.instances = [];
  }

  static instances: MockWebSocket[] = [];
}

const OriginalWebSocket = global.WebSocket;

describe("useWebSocket", () => {
  beforeEach(() => {
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
    MockWebSocket.reset();
  });

  afterEach(() => {
    MockWebSocket.reset();
    global.WebSocket = OriginalWebSocket;
  });

  describe("Connection", () => {
    it("should connect to WebSocket on mount", async () => {
      const { result } = renderHook(() =>
        useWebSocket({ url: "ws://localhost:8000/ws" })
      );

      expect(result.current.connectionState).toBe("connecting");

      await waitFor(() => expect(result.current.connectionState).toBe("open"));
    });

    it("should call onOpen callback when connected", async () => {
      const onOpen = vi.fn();

      renderHook(() =>
        useWebSocket({
          url: "ws://localhost:8000/ws",
          onOpen,
        })
      );

      await waitFor(() => expect(onOpen).toHaveBeenCalled());
    });

    it("should use custom URL when provided", async () => {
      const customUrl = "ws://custom-server:9000/custom-path";

      renderHook(() => useWebSocket({ url: customUrl }));

      await waitFor(() => expect(MockWebSocket.instances.length).toBeGreaterThan(0));

      const ws = MockWebSocket.instances[0];
      expect(ws.url).toBe(customUrl);
    });

    it("should default to ws:// protocol in http context", async () => {
      Object.defineProperty(window, "location", {
        value: { protocol: "http:", host: "localhost:3000" },
        writable: true,
      });

      renderHook(() => useWebSocket());

      await waitFor(() => expect(MockWebSocket.instances.length).toBeGreaterThan(0));

      const ws = MockWebSocket.instances[0];
      expect(ws.url).toContain("ws://");
    });

    it("should use wss:// protocol in https context", async () => {
      Object.defineProperty(window, "location", {
        value: { protocol: "https:", host: "example.com" },
        writable: true,
      });

      renderHook(() => useWebSocket());

      await waitFor(() => expect(MockWebSocket.instances.length).toBeGreaterThan(0));

      const ws = MockWebSocket.instances[0];
      expect(ws.url).toContain("wss://");
    });
  });

  describe("Message Handling", () => {
    it("should receive and parse JSON messages", async () => {
      const onMessage = vi.fn();
      const testMessage: WebSocketMessage = {
        type: "echo",
        message: "Hello, World!",
      };

      const { result } = renderHook(() =>
        useWebSocket({
          url: "ws://localhost:8000/ws",
          onMessage,
        })
      );

      await waitFor(() => expect(result.current.connectionState).toBe("open"));

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.triggerMessage(JSON.stringify(testMessage));
      });

      expect(onMessage).toHaveBeenCalledWith(testMessage);
    });

    it("should handle non-JSON messages gracefully", async () => {
      const onMessage = vi.fn();

      const { result } = renderHook(() =>
        useWebSocket({
          url: "ws://localhost:8000/ws",
          onMessage,
        })
      );

      await waitFor(() => expect(result.current.connectionState).toBe("open"));

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.triggerMessage("plain text message");
      });

      expect(onMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "raw",
          message: "plain text message",
        })
      );
    });

    it("should send string messages through WebSocket", async () => {
      const { result } = renderHook(() =>
        useWebSocket({ url: "ws://localhost:8000/ws" })
      );

      await waitFor(() => expect(result.current.connectionState).toBe("open"));

      const ws = MockWebSocket.instances[0];

      act(() => {
        result.current.send("test message");
      });

      expect(ws.sentMessages).toContain("test message");
    });

    it("should send object messages as JSON", async () => {
      const { result } = renderHook(() =>
        useWebSocket({ url: "ws://localhost:8000/ws" })
      );

      await waitFor(() => expect(result.current.connectionState).toBe("open"));

      const ws = MockWebSocket.instances[0];
      const testObject = { type: "greeting", text: "Hello" };

      act(() => {
        result.current.send(testObject);
      });

      expect(ws.sentMessages).toContain(JSON.stringify(testObject));
    });

    it("should not send messages when disconnected", async () => {
      const consoleWarnSpy = vi
        .spyOn(console, "warn")
        .mockImplementation(() => {});

      const { result } = renderHook(() =>
        useWebSocket({ url: "ws://localhost:8000/ws" })
      );

      act(() => {
        result.current.disconnect();
      });

      act(() => {
        result.current.send("test");
      });

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining("connection not open")
      );

      consoleWarnSpy.mockRestore();
    });
  });

  describe("Disconnection", () => {
    it("should call onClose callback when disconnected", async () => {
      const onClose = vi.fn();

      const { result } = renderHook(() =>
        useWebSocket({
          url: "ws://localhost:8000/ws",
          onClose,
        })
      );

      await waitFor(() => expect(result.current.connectionState).toBe("open"));

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.triggerClose(1000, "Normal closure");
      });

      expect(onClose).toHaveBeenCalled();
      expect(result.current.connectionState).toBe("closed");
    });

    it("should cleanup connection on unmount", async () => {
      const { unmount } = renderHook(() =>
        useWebSocket({ url: "ws://localhost:8000/ws" })
      );

      await waitFor(() => expect(MockWebSocket.instances.length).toBeGreaterThan(0));

      const ws = MockWebSocket.instances[0];

      unmount();

      expect(ws.readyState).toBe(MockWebSocket.CLOSED);
    });
  });

  describe("Reconnection", () => {
    it("should automatically reconnect on disconnect", async () => {
      const onOpen = vi.fn();

      const { result } = renderHook(() =>
        useWebSocket({
          url: "ws://localhost:8000/ws",
          onOpen,
          reconnect: true,
          reconnectDelayMs: 100,
        })
      );

      await waitFor(() => expect(onOpen).toHaveBeenCalled());

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.triggerClose(1006, "Abnormal closure");
      });

      expect(result.current.connectionState).toBe("closed");

      // Wait for reconnection (using real timers with short delay)
      await waitFor(
        () => expect(onOpen).toHaveBeenCalledTimes(2),
        { timeout: 5000 }
      );
    });

    it("should not reconnect when manually disconnected", async () => {
      const onOpen = vi.fn();

      const { result } = renderHook(() =>
        useWebSocket({
          url: "ws://localhost:8000/ws",
          onOpen,
          reconnect: true,
        })
      );

      await waitFor(() => expect(onOpen).toHaveBeenCalled());

      act(() => {
        result.current.disconnect();
      });

      expect(result.current.connectionState).toBe("closed");

      // Wait a bit to ensure no reconnection
      await new Promise(resolve => setTimeout(resolve, 500));

      expect(onOpen).toHaveBeenCalledTimes(1);
    });

    it("should allow manual reconnection after disconnect", async () => {
      const onOpen = vi.fn();

      const { result } = renderHook(() =>
        useWebSocket({
          url: "ws://localhost:8000/ws",
          onOpen,
        })
      );

      await waitFor(() => expect(onOpen).toHaveBeenCalled());

      act(() => {
        result.current.disconnect();
      });

      expect(onOpen).toHaveBeenCalledTimes(1);

      act(() => {
        result.current.reconnect();
      });

      await waitFor(() => expect(onOpen).toHaveBeenCalledTimes(2));
      expect(result.current.connectionState).toBe("open");
    });
  });

  describe("Error Handling", () => {
    it("should handle connection errors", async () => {
      const onError = vi.fn();

      renderHook(() =>
        useWebSocket({
          url: "ws://localhost:8000/ws",
          onError,
        })
      );

      await waitFor(() => expect(MockWebSocket.instances.length).toBeGreaterThan(0));

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.triggerError();
      });

      expect(onError).toHaveBeenCalled();
    });
  });
});
