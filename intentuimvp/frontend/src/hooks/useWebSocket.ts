"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { recordWsReconnect } from "@/lib/performance";

/**
 * WebSocket message types supported by the backend.
 */
export interface WebSocketMessage {
  type:
    | "heartbeat"
    | "echo"
    | "update"
    | "error"
    | "state.update"
    | "state.snapshot"
    | "node.created"
    | "node.updated"
    | "edge.created"
    | "edge.updated"
    | "edge.deleted";
  message?: string;
  sequence?: number;
  payload?: unknown;
  [key: string]: unknown;
}

/**
 * Event queue entry for messages sent during disconnection.
 */
export interface QueuedEvent {
  /** The event data to send */
  data: string | object;
  /** Timestamp when the event was queued */
  timestamp: number;
}

/**
 * Configuration options for the useWebSocket hook.
 */
export interface UseWebSocketOptions {
  /**
   * WebSocket URL to connect to.
   * Defaults to ws://localhost:8000/ws in development,
   * wss:// in production based on the current origin.
   */
  url?: string;

  /**
   * Callback invoked when a new message is received.
   */
  onMessage?: (message: WebSocketMessage) => void;

  /**
   * Callback invoked when the connection is established.
   */
  onOpen?: (event: WebSocketEventMap["open"]) => void;

  /**
   * Callback invoked when the connection is closed.
   */
  onClose?: (event: WebSocketEventMap["close"]) => void;

  /**
   * Callback invoked when an error occurs.
   */
  onError?: (event: WebSocketEventMap["error"]) => void;

  /**
   * Whether to automatically reconnect on disconnect.
   * @default true
   */
  reconnect?: boolean;

  /**
   * Maximum number of reconnection attempts before giving up.
   * @default 10
   */
  maxReconnectAttempts?: number;

  /**
   * Initial reconnection delay in milliseconds.
   * Subsequent attempts use exponential backoff.
   * @default 1000
   */
  reconnectDelayMs?: number;

  /**
   * Callback invoked when queued events are flushed after reconnect.
   */
  onEventsFlushed?: (events: QueuedEvent[]) => void;

  /**
   * Callback to fetch REST snapshot when sequence gap is detected.
   * Should return a promise that resolves with the full state.
   */
  onSyncSnapshot?: () => Promise<unknown>;

  /**
   * Whether to enable sequence tracking for gap detection.
   * @default true
   */
  enableSequenceTracking?: boolean;

  /**
   * Maximum number of events to queue during disconnection.
   * @default 100
   */
  maxQueueSize?: number;
}

/**
 * Return value of the useWebSocket hook.
 */
export interface UseWebSocketReturn {
  /**
   * The current WebSocket connection state.
   */
  connectionState: "connecting" | "open" | "closed" | "error";

  /**
   * Send a message through the WebSocket connection.
   * Queues the event if disconnected.
   *
   * @param data - The data to send (object will be JSON stringified).
   */
  send: (data: string | object) => void;

  /**
   * Manually close the WebSocket connection.
   * Automatic reconnection will be disabled.
   */
  disconnect: () => void;

  /**
   * Manually attempt to reconnect.
   */
  reconnect: () => void;

  /**
   * Number of events currently queued (waiting for reconnection).
   */
  queuedEventCount: number;

  /**
   * Last received sequence number.
   */
  lastSequence: number | null;

  /**
   * Whether a sequence gap has been detected (triggering snapshot sync).
   */
  hasSequenceGap: boolean;
}

/**
 * Default WebSocket URL based on environment.
 */
const getDefaultWebSocketUrl = (): string => {
  if (typeof window === "undefined") return "";

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = process.env.NEXT_PUBLIC_WS_URL || window.location.host;
  return `${protocol}//${host}/ws`;
};

/**
 * Custom React hook for managing WebSocket connections.
 *
 * Features:
 * - Automatic connection on mount
 * - Auto-reconnect with exponential backoff (1s, 2s, 4s, ..., 30s cap, max 10 attempts)
 * - Event queuing during disconnection with flushing on reconnect
 * - Sequence gap detection with REST snapshot sync fallback
 * - JSON message serialization/deserialization
 * - Type-safe message handling
 * - Manual send/reconnect/disconnect methods
 *
 * @example
 * ```tsx
 * const { connectionState, send, queuedEventCount, lastSequence } = useWebSocket({
 *   onMessage: (msg) => console.log("Received:", msg),
 *   onEventsFlushed: (events) => console.log(`Flushed ${events.length} events`),
 *   onSyncSnapshot: async () => await fetch('/api/snapshot').then(r => r.json()),
 * });
 *
 * send({ type: "greeting", text: "Hello" });
 * ```
 */
export function useWebSocket(
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const {
    url: urlProp = getDefaultWebSocketUrl(),
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnect: shouldReconnect = true,
    maxReconnectAttempts = 10,
    reconnectDelayMs = 1000,
    onEventsFlushed,
    onSyncSnapshot,
    enableSequenceTracking = true,
    maxQueueSize = 100,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isManualCloseRef = useRef(false);
  const disconnectTimeRef = useRef<number | null>(null);
  const connectRef = useRef<(() => void) | null>(null);

  // Event queue for messages sent during disconnection
  const eventQueueRef = useRef<QueuedEvent[]>([]);

  // Sequence tracking for gap detection
  const lastSequenceRef = useRef<number | null>(null);
  const hasSequenceGapRef = useRef(false);
  const isSyncingSnapshotRef = useRef(false);

  const [connectionState, setConnectionState] = useState<
    "connecting" | "open" | "closed" | "error"
  >("connecting");

  const [queuedEventCount, setQueuedEventCount] = useState(0);
  const [lastSequence, setLastSequence] = useState<number | null>(null);
  const [hasSequenceGap, setHasSequenceGap] = useState(false);

  /**
   * Calculate reconnection delay with exponential backoff.
   * 1s base, 30s cap.
   */
  const getReconnectDelay = useCallback(
    (attempt: number): number => {
      return Math.min(reconnectDelayMs * Math.pow(2, attempt), 30000);
    },
    [reconnectDelayMs]
  );

  /**
   * Clear any pending reconnection timeout.
   */
  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  /**
   * Queue an event to be sent after reconnect.
   */
  const queueEvent = useCallback((data: string | object): boolean => {
    if (eventQueueRef.current.length >= maxQueueSize) {
      console.warn(
        `WebSocket: Event queue full (${maxQueueSize}), dropping event`
      );
      return false;
    }

    eventQueueRef.current.push({
      data,
      timestamp: Date.now(),
    });
    setQueuedEventCount(eventQueueRef.current.length);
    return true;
  }, [maxQueueSize]);

  /**
   * Flush all queued events after reconnect.
   */
  const flushQueuedEvents = useCallback(async () => {
    if (hasSequenceGapRef.current || isSyncingSnapshotRef.current) {
      return;
    }

    const queuedEvents = [...eventQueueRef.current];
    eventQueueRef.current = [];
    setQueuedEventCount(0);

    if (queuedEvents.length === 0) {
      return;
    }

    console.log(`WebSocket: Flushing ${queuedEvents.length} queued events`);

    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      // Re-queue if not connected
      eventQueueRef.current = [...queuedEvents, ...eventQueueRef.current];
      setQueuedEventCount(eventQueueRef.current.length);
      return;
    }

    // Send all queued events
    const flushed: QueuedEvent[] = [];
    for (const event of queuedEvents) {
      try {
        const message = typeof event.data === "string" ? event.data : JSON.stringify(event.data);
        ws.send(message);
        flushed.push(event);
      } catch (error) {
        console.error("WebSocket: Failed to send queued event", error);
      }
    }

    onEventsFlushed?.(flushed);
  }, [onEventsFlushed]);

  /**
   * Request REST snapshot sync when sequence gap detected.
   */
  const requestSnapshotSync = useCallback(async () => {
    if (!onSyncSnapshot || isSyncingSnapshotRef.current) {
      return;
    }

    isSyncingSnapshotRef.current = true;
    setHasSequenceGap(true);
    hasSequenceGapRef.current = true;
    let snapshotApplied = false;

    try {
      console.info("WebSocket: Requesting REST snapshot sync due to sequence gap");
      await onSyncSnapshot();
      console.info("WebSocket: Snapshot sync completed");
      snapshotApplied = true;
    } catch (error) {
      console.error("WebSocket: Snapshot sync failed", error);
    } finally {
      isSyncingSnapshotRef.current = false;
      if (snapshotApplied) {
        hasSequenceGapRef.current = false;
        setHasSequenceGap(false);
        void flushQueuedEvents();
      }
    }
  }, [flushQueuedEvents, onSyncSnapshot]);

  /**
   * Process incoming message and check for sequence gaps.
   */
  const processMessage = useCallback((message: WebSocketMessage) => {
    if (!enableSequenceTracking) {
      onMessage?.(message);
      return;
    }

    const msgSequence = message.sequence;
    if (msgSequence !== undefined) {
      const lastSeq = lastSequenceRef.current;

      // Check for duplicate or out-of-order
      if (lastSeq !== null && msgSequence <= lastSeq) {
        console.warn(
          `WebSocket: Duplicate/out-of-order sequence: expected > ${lastSeq}, got ${msgSequence}`
        );
        return;
      }

      // Check for sequence gap
      if (lastSeq !== null && msgSequence !== lastSeq + 1) {
        console.warn(
          `WebSocket: Sequence gap detected: expected ${lastSeq + 1}, got ${msgSequence}`
        );
        void requestSnapshotSync();
        return;
      }

      // Update last sequence
      lastSequenceRef.current = msgSequence;
      setLastSequence(msgSequence);

      // Clear gap flag if we're now in sync
      if (hasSequenceGapRef.current && !isSyncingSnapshotRef.current) {
        hasSequenceGapRef.current = false;
        setHasSequenceGap(false);
      }
    }

    onMessage?.(message);
  }, [enableSequenceTracking, onMessage, requestSnapshotSync]);

  /**
   * Attempt to reconnect to the WebSocket server.
   */
  const scheduleReconnect = useCallback(() => {
    if (!shouldReconnect || isManualCloseRef.current) {
      return;
    }

    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      console.warn(
        `WebSocket: Max reconnection attempts (${maxReconnectAttempts}) reached`
      );
      setConnectionState("error");

      // Record failed reconnection for NFR-PERF-005
      if (disconnectTimeRef.current !== null) {
        const duration = performance.now() - disconnectTimeRef.current;
        recordWsReconnect(duration, false);
        disconnectTimeRef.current = null;
      }

      return;
    }

    const delay = getReconnectDelay(reconnectAttemptsRef.current);
    console.log(
      `WebSocket: Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`
    );

    clearReconnectTimeout();

    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectAttemptsRef.current++;
      connectRef.current?.();
    }, delay);
  }, [
    shouldReconnect,
    maxReconnectAttempts,
    getReconnectDelay,
    clearReconnectTimeout,
  ]);

  /**
   * Establish a WebSocket connection.
   */
  const connect = useCallback(() => {
    if (!urlProp) return;

    // Close existing connection if any
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    clearReconnectTimeout();
    setConnectionState("connecting");

    try {
      const ws = new WebSocket(urlProp);
      wsRef.current = ws;

      ws.onopen = (event) => {
        console.log("WebSocket: Connected");
        reconnectAttemptsRef.current = 0;

        // Track reconnection time for NFR-PERF-005 (target: < 5000ms)
        if (disconnectTimeRef.current !== null) {
          const duration = performance.now() - disconnectTimeRef.current;
          recordWsReconnect(duration, true);
          disconnectTimeRef.current = null;
        }

        setConnectionState("open");
        onOpen?.(event);

        if (hasSequenceGapRef.current) {
          void requestSnapshotSync();
        }

        // Flush queued events after reconnect
        void flushQueuedEvents();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketMessage;
          processMessage(data);
        } catch {
          // If not JSON, pass as-is
          processMessage({
            type: "raw",
            message: event.data,
          } as unknown as WebSocketMessage);
        }
      };

      ws.onclose = (event) => {
        console.log(`WebSocket: Closed (code: ${event.code}, reason: ${event.reason})`);
        setConnectionState("closed");

        // Track disconnect time for NFR-PERF-005
        if (!isManualCloseRef.current) {
          disconnectTimeRef.current = performance.now();
        }

        onClose?.(event);

        // Attempt to reconnect if not manually closed
        if (!isManualCloseRef.current) {
          scheduleReconnect();
        }
      };

      ws.onerror = (event) => {
        console.error("WebSocket: Error occurred", event);
        setConnectionState("error");
        onError?.(event);
      };
    } catch (error) {
      console.error("WebSocket: Failed to create connection", error);
      setConnectionState("error");
      scheduleReconnect();
    }
  }, [urlProp, onOpen, onClose, onError, flushQueuedEvents, processMessage, requestSnapshotSync, scheduleReconnect, clearReconnectTimeout]);

  /**
   * Send data through the WebSocket connection.
   * Queues the event if disconnected.
   */
  const send = useCallback(
    (data: string | object) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.warn("WebSocket: Cannot send message, connection not open. Queuing for reconnect.");
        queueEvent(data);
        return;
      }

      if (hasSequenceGapRef.current || isSyncingSnapshotRef.current) {
        console.warn("WebSocket: Queueing message until snapshot sync completes.");
        queueEvent(data);
        return;
      }

      try {
        const message = typeof data === "string" ? data : JSON.stringify(data);
        ws.send(message);
      } catch (error) {
        console.error("WebSocket: Failed to send message", error);
        // Queue for retry
        queueEvent(data);
      }
    },
    [queueEvent]
  );

  /**
   * Manually close the WebSocket connection.
   * Disables automatic reconnection.
   */
  const disconnect = useCallback(() => {
    isManualCloseRef.current = true;
    clearReconnectTimeout();

    // Clear disconnect time tracking on manual disconnect
    disconnectTimeRef.current = null;

    if (wsRef.current) {
      wsRef.current.close(1000, "User disconnected");
      wsRef.current = null;
    }

    setConnectionState("closed");

    // Clear event queue on manual disconnect
    eventQueueRef.current = [];
    setQueuedEventCount(0);
  }, [clearReconnectTimeout]);

  /**
   * Manually trigger a reconnection.
   */
  const reconnect = useCallback(() => {
    isManualCloseRef.current = false;
    reconnectAttemptsRef.current = 0;
    clearReconnectTimeout();
    connect();
  }, [connect, clearReconnectTimeout]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  // Establish connection on mount
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connectionState,
    send,
    disconnect,
    reconnect,
    queuedEventCount,
    lastSequence,
    hasSequenceGap,
  };
}
