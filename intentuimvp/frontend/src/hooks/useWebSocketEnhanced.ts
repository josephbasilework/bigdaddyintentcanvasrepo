"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { recordWsReconnect } from "@/lib/performance";

/**
 * Storage key for persisting session ID across browser refreshes.
 */
const SESSION_ID_STORAGE_KEY = "intentui_workspace_session_id";

/**
 * Storage key prefix for persisting queued events.
 */
const QUEUE_STORAGE_PREFIX = "intentui_ws_queue_v1";

/**
 * Generate a UUID v4 session ID.
 */
function generateSessionId(): string {
  // Use crypto.randomUUID if available, otherwise fall back to manual generation
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Get or create a session ID from storage.
 * Returns existing session ID if found, otherwise generates a new one.
 */
function getOrCreateSessionId(): string {
  if (typeof window === "undefined") {
    return generateSessionId();
  }

  // Try localStorage first (persists across tabs and browser sessions)
  const stored = localStorage.getItem(SESSION_ID_STORAGE_KEY);
  if (stored) {
    return stored;
  }

  // Generate new session ID
  const newSessionId = generateSessionId();
  localStorage.setItem(SESSION_ID_STORAGE_KEY, newSessionId);
  return newSessionId;
}

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
    | "node.deleted"
    | "edge.created"
    | "edge.updated"
    | "edge.deleted"
    | "job.progress"
    | "turn.created"
    | "event.created"
    | "dashboard.update"
    | "dashboard.subscribed"
    | "request"
    | "notification"
    | "raw";
  message?: string;
  sequence?: number;
  payload?: unknown;
  [key: string]: unknown;
}

/**
 * Event queue entry for messages sent during disconnection.
 */
export interface QueuedEvent {
  /** Stable identifier for editing/deleting queued events */
  id: string;
  /** The event data to send */
  data: string | object;
  /** Timestamp when the event was queued */
  timestamp: number;
  /** Sequence number (if available) */
  sequence?: number;
}

/**
 * Create a stable queue item ID.
 */
const createQueueId = (): string => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `queue-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const getQueueStorageKey = (sessionId: string): string =>
  `${QUEUE_STORAGE_PREFIX}:${sessionId}`;

const coerceQueuedEvent = (value: unknown): QueuedEvent | null => {
  if (!value || typeof value !== "object") {
    return null;
  }

  const candidate = value as {
    id?: unknown;
    data?: unknown;
    timestamp?: unknown;
    sequence?: unknown;
  };

  if (candidate.data === undefined) {
    return null;
  }

  let data: string | object;
  if (typeof candidate.data === "string") {
    data = candidate.data;
  } else if (candidate.data && typeof candidate.data === "object") {
    data = candidate.data as object;
  } else {
    data = String(candidate.data ?? "");
  }

  const timestamp =
    typeof candidate.timestamp === "number" ? candidate.timestamp : Date.now();

  const id = typeof candidate.id === "string" ? candidate.id : createQueueId();

  const sequence =
    typeof candidate.sequence === "number" ? candidate.sequence : undefined;

  return {
    id,
    data,
    timestamp,
    sequence,
  };
};

const loadPersistedQueue = (
  sessionId: string,
  maxQueueSize: number
): QueuedEvent[] => {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const stored = localStorage.getItem(getQueueStorageKey(sessionId));
    if (!stored) {
      return [];
    }
    const parsed = JSON.parse(stored);
    if (!Array.isArray(parsed)) {
      return [];
    }
    const normalized = parsed
      .map(coerceQueuedEvent)
      .filter((event): event is QueuedEvent => Boolean(event));
    if (normalized.length <= maxQueueSize) {
      return normalized;
    }
    return normalized.slice(0, maxQueueSize);
  } catch (error) {
    console.warn("WebSocket: Failed to restore queued events", error);
    return [];
  }
};

const extractSequenceFromData = (data: string | object): number | undefined => {
  if (!data || typeof data !== "object") {
    return undefined;
  }

  const candidate = data as {
    sequence?: unknown;
    payload?: { sequence?: unknown } | null;
  };

  if (typeof candidate.sequence === "number") {
    return candidate.sequence;
  }

  if (candidate.payload && typeof candidate.payload.sequence === "number") {
    return candidate.payload.sequence;
  }

  return undefined;
};

/**
 * Enhanced WebSocket options with reconnection features.
 */
export interface UseWebSocketOptions {
  url?: string;
  onMessage?: (message: WebSocketMessage) => void;
  onOpen?: (event: WebSocketEventMap["open"]) => void;
  onClose?: (event: WebSocketEventMap["close"]) => void;
  onError?: (event: WebSocketEventMap["error"]) => void;
  reconnect?: boolean;
  maxReconnectAttempts?: number;
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
 * Enhanced return value with sequence and queue information.
 */
export interface UseWebSocketReturn {
  connectionState: "connecting" | "open" | "closed" | "error";
  send: (data: string | object) => void;
  disconnect: () => void;
  reconnect: () => void;

  /**
   * Number of events currently queued (waiting for reconnection).
   */
  queuedEventCount: number;

  /**
   * Full queue of events waiting for reconnection.
   */
  queuedEvents: QueuedEvent[];

  /**
   * Update a queued event payload before it is replayed.
   */
  updateQueuedEvent: (id: string, data: string | object) => void;

  /**
   * Remove a queued event before it is replayed.
   */
  deleteQueuedEvent: (id: string) => void;

  /**
   * Last received sequence number.
   */
  lastSequence: number | null;

  /**
   * Whether a sequence gap has been detected (triggering snapshot sync).
   */
  hasSequenceGap: boolean;

  /**
   * The session ID for this WebSocket connection.
   * Persists across reconnects and browser refreshes.
   */
  sessionId: string;

  /**
   * Clear the session ID and start a fresh session on next connect.
   */
  clearSession: () => void;

  /**
   * Whether queued events are currently being flushed on reconnect.
   */
  isFlushingQueue: boolean;

  /**
   * Count of the most recent flush batch.
   */
  lastFlushedEventCount: number;

  /**
   * Timestamp of the most recent flush, if any.
   */
  lastFlushTimestamp: number | null;
}

/**
 * Default WebSocket URL based on environment.
 * Includes session_id as a query parameter for Global Session Identity.
 */
const getDefaultWebSocketUrl = (sessionId: string): string => {
  if (typeof window === "undefined") return "";

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = process.env.NEXT_PUBLIC_WS_URL || window.location.host;
  return `${protocol}//${host}/ws?session_id=${encodeURIComponent(sessionId)}`;
};

const appendSessionId = (url: string, sessionId: string): string => {
  if (!url || url.includes("session_id=")) {
    return url;
  }
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}session_id=${encodeURIComponent(sessionId)}`;
};

/**
 * Enhanced WebSocket hook with:
 * - Exponential backoff reconnection (1s base, 30s cap, max 10 attempts)
 * - Event queuing during disconnection
 * - Queued event flushing after reconnect
 * - Sequence gap detection with REST snapshot sync
 * - Telemetry tracking for NFR-PERF-005
 * - Global Session Identity (persistent session_id across reconnects)
 *
 * Implements T2-F9.2: WebSocket reconnect + queued events
 */
export function useWebSocketEnhanced(
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  // Get or create session ID on first render (persisted across reconnects)
  const sessionIdRef = useRef<string>(getOrCreateSessionId());
  const [sessionId, setSessionId] = useState<string>(sessionIdRef.current);

  const {
    url: urlProp,
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

  // Compute the WebSocket URL with session ID
  const baseUrl = urlProp || getDefaultWebSocketUrl(sessionIdRef.current);
  const wsUrl = appendSessionId(baseUrl, sessionIdRef.current);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isManualCloseRef = useRef(false);
  const disconnectTimeRef = useRef<number | null>(null);

  // Ref to break circular dependency between connect and scheduleReconnect
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
  const [queuedEvents, setQueuedEvents] = useState<QueuedEvent[]>([]);
  const [lastSequence, setLastSequence] = useState<number | null>(null);
  const [hasSequenceGap, setHasSequenceGap] = useState(false);
  const [isFlushingQueue, setIsFlushingQueue] = useState(false);
  const [lastFlushedEventCount, setLastFlushedEventCount] = useState(0);
  const [lastFlushTimestamp, setLastFlushTimestamp] = useState<number | null>(null);

  const persistQueue = useCallback((queue: QueuedEvent[]) => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      localStorage.setItem(
        getQueueStorageKey(sessionIdRef.current),
        JSON.stringify(queue)
      );
    } catch (error) {
      console.warn("WebSocket: Failed to persist queued events", error);
    }
  }, []);

  const syncQueueState = useCallback(
    (queue: QueuedEvent[]) => {
      eventQueueRef.current = queue;
      setQueuedEventCount(queue.length);
      setQueuedEvents(queue);
      persistQueue(queue);
    },
    [persistQueue]
  );

  /**
   * Clear the session ID and create a fresh one.
   * Useful for "logout" or "new workspace" scenarios.
   */
  const clearSession = useCallback(() => {
    const previousSessionId = sessionIdRef.current;
    if (typeof window !== "undefined") {
      localStorage.removeItem(SESSION_ID_STORAGE_KEY);
      localStorage.removeItem(getQueueStorageKey(previousSessionId));
    }
    const newId = generateSessionId();
    sessionIdRef.current = newId;
    setSessionId(newId);
    if (typeof window !== "undefined") {
      localStorage.setItem(SESSION_ID_STORAGE_KEY, newId);
    }
    syncQueueState([]);
  }, [syncQueueState]);

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
  const queueEvent = useCallback(
    (data: string | object): boolean => {
      if (eventQueueRef.current.length >= maxQueueSize) {
        console.warn(
          `WebSocket: Event queue full (${maxQueueSize}), dropping event`
        );
        return false;
      }

      const nextEvent: QueuedEvent = {
        id: createQueueId(),
        data,
        timestamp: Date.now(),
        sequence: extractSequenceFromData(data),
      };

      const nextQueue = [...eventQueueRef.current, nextEvent];
      syncQueueState(nextQueue);
      return true;
    },
    [maxQueueSize, syncQueueState]
  );

  const updateQueuedEvent = useCallback(
    (id: string, data: string | object) => {
      const nextQueue = eventQueueRef.current.map((event) => {
        if (event.id !== id) {
          return event;
        }
        return {
          ...event,
          data,
          sequence: extractSequenceFromData(data),
        };
      });
      syncQueueState(nextQueue);
    },
    [syncQueueState]
  );

  const deleteQueuedEvent = useCallback(
    (id: string) => {
      if (eventQueueRef.current.length === 0) {
        return;
      }
      const nextQueue = eventQueueRef.current.filter((event) => event.id !== id);
      if (nextQueue.length === eventQueueRef.current.length) {
        return;
      }
      syncQueueState(nextQueue);
    },
    [syncQueueState]
  );

  /**
   * Flush all queued events after reconnect.
   */
  const flushQueuedEvents = useCallback(async () => {
    if (eventQueueRef.current.length === 0) {
      return;
    }

    const queuedEvents = [...eventQueueRef.current];
    syncQueueState([]);
    setIsFlushingQueue(true);
    setLastFlushedEventCount(queuedEvents.length);

    console.log(`WebSocket: Flushing ${queuedEvents.length} queued events`);

    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      // Re-queue if not connected
      syncQueueState([...queuedEvents, ...eventQueueRef.current]);
      setIsFlushingQueue(false);
      return;
    }

    // Send all queued events
    const flushed: QueuedEvent[] = [];
    const retryQueue: QueuedEvent[] = [];
    try {
      for (const event of queuedEvents) {
        try {
          const message =
            typeof event.data === "string"
              ? event.data
              : JSON.stringify(event.data);
          ws.send(message);
          flushed.push(event);
        } catch (error) {
          console.error("WebSocket: Failed to send queued event", error);
          retryQueue.push(event);
          if (!ws || ws.readyState !== WebSocket.OPEN) {
            break;
          }
        }
      }
    } finally {
      setIsFlushingQueue(false);
    }

    if (retryQueue.length > 0) {
      syncQueueState([...retryQueue, ...eventQueueRef.current]);
    }

    if (flushed.length > 0) {
      setLastFlushedEventCount(flushed.length);
      setLastFlushTimestamp(Date.now());
    }

    onEventsFlushed?.(flushed);
  }, [onEventsFlushed, syncQueueState]);

  const extractSequence = useCallback((message: WebSocketMessage): number | null => {
    if (typeof message.sequence === "number") {
      return message.sequence;
    }

    if (message.payload && typeof message.payload === "object") {
      const payload = message.payload as { sequence?: unknown };
      if (typeof payload.sequence === "number") {
        return payload.sequence;
      }
    }

    return null;
  }, []);

  const extractSnapshotSequence = useCallback((snapshot: unknown): number | null => {
    if (!snapshot || typeof snapshot !== "object") {
      return null;
    }

    const candidate = snapshot as {
      sequence?: unknown;
      payload?: { sequence?: unknown } | null;
    };

    if (typeof candidate.sequence === "number") {
      return candidate.sequence;
    }

    if (candidate.payload && typeof candidate.payload.sequence === "number") {
      return candidate.payload.sequence;
    }

    return null;
  }, []);

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

    try {
      console.info(
        "WebSocket: Requesting REST snapshot sync due to sequence gap"
      );
      const snapshot = await onSyncSnapshot();
      const snapshotSequence = extractSnapshotSequence(snapshot);
      if (snapshotSequence !== null) {
        lastSequenceRef.current = snapshotSequence;
        setLastSequence(snapshotSequence);
      } else {
        lastSequenceRef.current = null;
        setLastSequence(null);
      }

      console.info("WebSocket: Snapshot sync completed");
    } catch (error) {
      console.error("WebSocket: Snapshot sync failed", error);
    } finally {
      isSyncingSnapshotRef.current = false;
    }
  }, [extractSnapshotSequence, onSyncSnapshot]);

  /**
   * Process incoming message and check for sequence gaps.
   */
  const processMessage = useCallback(
    (message: WebSocketMessage) => {
      if (!enableSequenceTracking) {
        onMessage?.(message);
        return;
      }

      if (message.type === "state.snapshot") {
        const snapshotSequence = extractSequence(message);
        if (snapshotSequence !== null) {
          lastSequenceRef.current = snapshotSequence;
          setLastSequence(snapshotSequence);
        }
        if (hasSequenceGapRef.current) {
          hasSequenceGapRef.current = false;
          setHasSequenceGap(false);
        }
        onMessage?.(message);
        return;
      }

      const msgSequence = extractSequence(message);
      if (msgSequence !== null) {
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
    },
    [enableSequenceTracking, extractSequence, onMessage, requestSnapshotSync]
  );

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
   * URL includes session_id for Global Session Identity.
   */
  const connect = useCallback(() => {
    if (!wsUrl) return;

    // Close existing connection if any
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    clearReconnectTimeout();
    setConnectionState("connecting");

    try {
      console.log(`WebSocket: Connecting with session_id=${sessionIdRef.current.slice(0, 8)}...`);
      const ws = new WebSocket(wsUrl);
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
        console.log(
          `WebSocket: Closed (code: ${event.code}, reason: ${event.reason})`
        );
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
  }, [
    wsUrl,
    onOpen,
    onClose,
    onError,
    flushQueuedEvents,
    processMessage,
    requestSnapshotSync,
    scheduleReconnect,
    clearReconnectTimeout,
  ]);

  /**
   * Send data through the WebSocket connection.
   * Queues the event if disconnected.
   */
  const send = useCallback(
    (data: string | object) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.warn(
          "WebSocket: Cannot send message, connection not open. Queuing for reconnect."
        );
        queueEvent(data);
        return;
      }

      try {
        const message =
          typeof data === "string" ? data : JSON.stringify(data);
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
    syncQueueState([]);
  }, [clearReconnectTimeout, syncQueueState]);

  /**
   * Manually trigger a reconnection.
   */
  const reconnect = useCallback(() => {
    isManualCloseRef.current = false;
    reconnectAttemptsRef.current = 0;
    clearReconnectTimeout();
    if (hasSequenceGapRef.current) {
      hasSequenceGapRef.current = false;
      setHasSequenceGap(false);
      lastSequenceRef.current = null;
      setLastSequence(null);
    }
    connect();
  }, [connect, clearReconnectTimeout]);

  useEffect(() => {
    const restored = loadPersistedQueue(sessionIdRef.current, maxQueueSize);
    eventQueueRef.current = restored;
    setQueuedEventCount(restored.length);
    setQueuedEvents(restored);
  }, [maxQueueSize, sessionId]);

  // Update connectRef to break circular type dependency
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
    queuedEvents,
    updateQueuedEvent,
    deleteQueuedEvent,
    lastSequence,
    hasSequenceGap,
    sessionId,
    clearSession,
    isFlushingQueue,
    lastFlushedEventCount,
    lastFlushTimestamp,
  };
}
