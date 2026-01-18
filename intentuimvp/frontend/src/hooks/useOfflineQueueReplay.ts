"use client";

import { useCallback, useEffect, useRef } from "react";
import type { ConnectionState, OfflineRequestData } from "@/state/offlineQueueStore";
import { useOfflineQueueStore } from "@/state/offlineQueueStore";
import { useCanvasStore } from "@/state/canvasStore";
import { normalizeWorkspaceState, resolveCanvasMeta } from "@/components/Canvas/CanvasWorkspace";
import { getLastSyncedTurnSequence, setLastSyncedTurnSequence } from "@/utils/turnSequence";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type UseOfflineQueueReplayOptions = {
  sessionId: string | null;
  connectionState: ConnectionState;
};

const parseRequestData = (data: string | object): OfflineRequestData | null => {
  let candidate: unknown = data;
  if (typeof data === "string") {
    try {
      candidate = JSON.parse(data);
    } catch {
      return null;
    }
  }
  if (!candidate || typeof candidate !== "object") {
    return null;
  }
  const record = candidate as {
    url?: unknown;
    method?: unknown;
    body?: unknown;
    headers?: unknown;
    kind?: unknown;
    sessionId?: unknown;
  };
  if (typeof record.url !== "string" || typeof record.method !== "string") {
    return null;
  }
  if (typeof record.sessionId !== "string" || record.sessionId.length === 0) {
    return null;
  }
  return {
    url: record.url,
    method: record.method,
    body: record.body,
    headers:
      record.headers && typeof record.headers === "object"
        ? (record.headers as Record<string, string>)
        : undefined,
    kind:
      record.kind === "command" || record.kind === "canvas_action"
        ? record.kind
        : "canvas_action",
    sessionId: record.sessionId,
  };
};

const extractSequenceNumber = (payload: unknown): number | null => {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const candidate = payload as { sequenceNumber?: unknown; sequence_number?: unknown };
  if (typeof candidate.sequenceNumber === "number") {
    return candidate.sequenceNumber;
  }
  if (typeof candidate.sequence_number === "number") {
    return candidate.sequence_number;
  }
  return null;
};

const checkForServerDivergence = async (sessionId: string): Promise<boolean> => {
  const lastSequence = getLastSyncedTurnSequence(sessionId);
  if (lastSequence === null) {
    return false;
  }
  const params = new URLSearchParams({
    session_id: sessionId,
    after_sequence: String(lastSequence),
    limit: "1",
  });
  const response = await fetch(`${API_BASE_URL}/api/turns?${params.toString()}`);
  if (!response.ok) {
    return false;
  }
  const data = (await response.json()) as { turns?: Array<{ sequenceNumber?: number }> };
  return Array.isArray(data.turns) && data.turns.length > 0;
};

export const useOfflineQueueReplay = ({
  sessionId,
  connectionState,
}: UseOfflineQueueReplayOptions) => {
  const queueLength = useOfflineQueueStore((state) => state.queue.length);
  const isFlushing = useOfflineQueueStore((state) => state.isFlushingQueue);
  const setNodes = useCanvasStore((state) => state.setNodes);
  const setEdges = useCanvasStore((state) => state.setEdges);
  const setCanvasMeta = useCanvasStore((state) => state.setCanvasMeta);
  const flushRef = useRef(false);

  const refreshWorkspace = useCallback(async () => {
    const response = await fetch(`${API_BASE_URL}/api/workspace`);
    if (!response.ok) {
      throw new Error(`Workspace sync failed: ${response.status}`);
    }
    const data = await response.json();
    const normalized = normalizeWorkspaceState(data);
    const meta = resolveCanvasMeta(data);
    setCanvasMeta(meta);
    setNodes(normalized.nodes);
    setEdges(normalized.edges);
  }, [setCanvasMeta, setEdges, setNodes]);

  const flushQueue = useCallback(async () => {
    if (!sessionId) {
      return;
    }
    if (flushRef.current) {
      return;
    }

    const store = useOfflineQueueStore.getState();
    if (store.queue.length === 0 || store.isFlushingQueue) {
      return;
    }

    flushRef.current = true;
    store.markFlushStart(store.queue.length);

    let flushedCount = 0;

    try {
      try {
        const diverged = await checkForServerDivergence(sessionId);
        if (diverged) {
          await refreshWorkspace();
        }
      } catch (error) {
        console.warn("Offline replay: Failed to reconcile workspace", error);
      }

      while (true) {
        const currentState = useOfflineQueueStore.getState();
        const nextItem = currentState.queue[0];
        if (!nextItem) {
          break;
        }

        const request = parseRequestData(nextItem.data);
        if (!request) {
          console.warn("Offline replay: Invalid queued payload", nextItem);
          break;
        }

        try {
          const headers = { ...(request.headers ?? {}) };
          let body: string | undefined;
          if (request.body !== undefined) {
            if (!headers["Content-Type"] && !headers["content-type"]) {
              headers["Content-Type"] = "application/json";
            }
            body =
              typeof request.body === "string"
                ? request.body
                : JSON.stringify(request.body);
          }

          const response = await fetch(request.url, {
            method: request.method,
            headers,
            body,
          });

          if (!response.ok) {
            console.warn(
              `Offline replay: Request failed (${response.status})`,
              nextItem
            );
            break;
          }

          let responsePayload: unknown = null;
          try {
            responsePayload = await response.json();
          } catch {
            // ignore non-JSON responses
          }

          const sequenceNumber = extractSequenceNumber(responsePayload);
          if (sequenceNumber !== null) {
            setLastSyncedTurnSequence(sessionId, sequenceNumber);
          }

          useOfflineQueueStore.getState().deleteQueuedEvent(nextItem.id);
          flushedCount += 1;
        } catch (error) {
          console.warn("Offline replay: Failed to send queued request", error);
          break;
        }
      }
    } finally {
      useOfflineQueueStore.getState().markFlushComplete(flushedCount);
      flushRef.current = false;
    }
  }, [refreshWorkspace, sessionId]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    if (connectionState !== "open") {
      return;
    }
    if (queueLength === 0 || isFlushing) {
      return;
    }
    void flushQueue();
  }, [connectionState, flushQueue, isFlushing, queueLength, sessionId]);
};
