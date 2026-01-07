"use client";

import { useEffect, useRef, useState, useCallback } from "react";

/**
 * WebSocket message types supported by the backend.
 */
export interface WebSocketMessage {
  type: "heartbeat" | "echo" | "update" | "error";
  message?: string;
  [key: string]: unknown;
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
   * Does nothing if the connection is not open.
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
 * - Auto-reconnect with exponential backoff (1s, 2s, 4s, ...)
 * - JSON message serialization/deserialization
 * - Type-safe message handling
 * - Manual send/reconnect/disconnect methods
 *
 * @example
 * ```tsx
 * const { connectionState, send, disconnect } = useWebSocket({
 *   onMessage: (msg) => console.log("Received:", msg),
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
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isManualCloseRef = useRef(false);

  const [connectionState, setConnectionState] = useState<
    "connecting" | "open" | "closed" | "error"
  >("connecting");

  /**
   * Calculate reconnection delay with exponential backoff.
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
      return;
    }

    const delay = getReconnectDelay(reconnectAttemptsRef.current);
    console.log(
      `WebSocket: Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`
    );

    clearReconnectTimeout();

    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectAttemptsRef.current++;
      connect();
    }, delay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        setConnectionState("open");
        onOpen?.(event);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketMessage;
          onMessage?.(data);
        } catch {
          // If not JSON, pass as-is
          onMessage?.({
            type: "raw",
            message: event.data,
          } as unknown as WebSocketMessage);
        }
      };

      ws.onclose = (event) => {
        console.log(`WebSocket: Closed (code: ${event.code}, reason: ${event.reason})`);
        setConnectionState("closed");
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
  }, [urlProp, onOpen, onMessage, onClose, onError, scheduleReconnect, clearReconnectTimeout]);

  /**
   * Send data through the WebSocket connection.
   */
  const send = useCallback(
    (data: string | object) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.warn("WebSocket: Cannot send message, connection not open");
        return;
      }

      try {
        const message = typeof data === "string" ? data : JSON.stringify(data);
        ws.send(message);
      } catch (error) {
        console.error("WebSocket: Failed to send message", error);
      }
    },
    []
  );

  /**
   * Manually close the WebSocket connection.
   * Disables automatic reconnection.
   */
  const disconnect = useCallback(() => {
    isManualCloseRef.current = true;
    clearReconnectTimeout();

    if (wsRef.current) {
      wsRef.current.close(1000, "User disconnected");
      wsRef.current = null;
    }

    setConnectionState("closed");
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
  };
}
