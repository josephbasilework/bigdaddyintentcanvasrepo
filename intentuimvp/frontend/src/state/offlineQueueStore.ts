"use client";

import { create } from "zustand";

export type ConnectionState = "connecting" | "open" | "closed" | "error";

export type OfflineRequestKind = "canvas_action" | "command";

export type OfflineRequestData = {
  url: string;
  method: string;
  body?: unknown;
  headers?: Record<string, string>;
  kind: OfflineRequestKind;
  sessionId: string;
};

export type OfflineQueuedEvent = {
  id: string;
  data: string | object;
  timestamp: number;
  sequence?: number;
};

type OfflineQueueState = {
  activeSessionId: string | null;
  connectionState: ConnectionState;
  queue: OfflineQueuedEvent[];
  isFlushingQueue: boolean;
  lastFlushedEventCount: number;
  lastFlushTimestamp: number | null;
  setSessionId: (sessionId: string | null) => void;
  setConnectionState: (state: ConnectionState) => void;
  enqueue: (
    request: OfflineRequestData,
    options?: { id?: string; timestamp?: number }
  ) => OfflineQueuedEvent | null;
  updateQueuedEvent: (id: string, data: string | object) => void;
  deleteQueuedEvent: (id: string) => void;
  markFlushStart: (count: number) => void;
  markFlushComplete: (flushedCount: number) => void;
  reset: () => void;
};

const QUEUE_STORAGE_PREFIX = "intentui_offline_queue_v1";
const MAX_QUEUE_SIZE = 100;

export const createOfflineQueueId = (): string => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `offline-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const getQueueStorageKey = (sessionId: string): string =>
  `${QUEUE_STORAGE_PREFIX}:${sessionId}`;

const coerceQueuedEvent = (value: unknown): OfflineQueuedEvent | null => {
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

  const id = typeof candidate.id === "string" ? candidate.id : createOfflineQueueId();
  const timestamp =
    typeof candidate.timestamp === "number" ? candidate.timestamp : Date.now();
  const sequence =
    typeof candidate.sequence === "number" ? candidate.sequence : undefined;

  let data: string | object;
  if (typeof candidate.data === "string") {
    data = candidate.data;
  } else if (candidate.data && typeof candidate.data === "object") {
    data = candidate.data as object;
  } else {
    data = String(candidate.data ?? "");
  }

  return { id, data, timestamp, sequence };
};

const loadPersistedQueue = (sessionId: string): OfflineQueuedEvent[] => {
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
      .filter((event): event is OfflineQueuedEvent => Boolean(event));
    const trimmed = normalized.slice(0, MAX_QUEUE_SIZE);
    return trimmed.sort((a, b) => {
      const aSeq = a.sequence ?? 0;
      const bSeq = b.sequence ?? 0;
      if (aSeq !== bSeq) {
        return aSeq - bSeq;
      }
      return a.timestamp - b.timestamp;
    });
  } catch (error) {
    console.warn("Offline queue: Failed to restore queued events", error);
    return [];
  }
};

const persistQueue = (sessionId: string, queue: OfflineQueuedEvent[]) => {
  if (typeof window === "undefined") {
    return;
  }
  try {
    localStorage.setItem(getQueueStorageKey(sessionId), JSON.stringify(queue));
  } catch (error) {
    console.warn("Offline queue: Failed to persist queued events", error);
  }
};

const getNextSequence = (queue: OfflineQueuedEvent[]): number => {
  const maxSequence = queue.reduce((max, item) => {
    const seq = typeof item.sequence === "number" ? item.sequence : 0;
    return Math.max(max, seq);
  }, 0);
  return maxSequence + 1;
};

const initialState = {
  activeSessionId: null,
  connectionState: "closed" as ConnectionState,
  queue: [] as OfflineQueuedEvent[],
  isFlushingQueue: false,
  lastFlushedEventCount: 0,
  lastFlushTimestamp: null as number | null,
};

export const useOfflineQueueStore = create<OfflineQueueState>((set, get) => ({
  ...initialState,
  setSessionId: (sessionId) => {
    const current = get().activeSessionId;
    if (current === sessionId) {
      return;
    }
    if (!sessionId) {
      set({ activeSessionId: null, queue: [] });
      return;
    }
    const restored = loadPersistedQueue(sessionId);
    set({ activeSessionId: sessionId, queue: restored });
  },
  setConnectionState: (state) => {
    set({ connectionState: state });
  },
  enqueue: (request, options) => {
    const sessionId = request.sessionId;
    if (!sessionId) {
      return null;
    }

    if (get().activeSessionId !== sessionId) {
      const restored = loadPersistedQueue(sessionId);
      set({ activeSessionId: sessionId, queue: restored });
    }

    const queue = get().queue;
    if (queue.length >= MAX_QUEUE_SIZE) {
      console.warn(
        `Offline queue: Queue full (${MAX_QUEUE_SIZE}), dropping event`
      );
      return null;
    }

    const nextEvent: OfflineQueuedEvent = {
      id: options?.id ?? createOfflineQueueId(),
      data: request,
      timestamp: options?.timestamp ?? Date.now(),
      sequence: getNextSequence(queue),
    };

    const nextQueue = [...queue, nextEvent];
    set({ queue: nextQueue });
    persistQueue(sessionId, nextQueue);
    return nextEvent;
  },
  updateQueuedEvent: (id, data) => {
    const sessionId = get().activeSessionId;
    if (!sessionId) {
      return;
    }
    const nextQueue = get().queue.map((event) => {
      if (event.id !== id) {
        return event;
      }
      return {
        ...event,
        data,
      };
    });
    set({ queue: nextQueue });
    persistQueue(sessionId, nextQueue);
  },
  deleteQueuedEvent: (id) => {
    const sessionId = get().activeSessionId;
    if (!sessionId) {
      return;
    }
    const nextQueue = get().queue.filter((event) => event.id !== id);
    if (nextQueue.length === get().queue.length) {
      return;
    }
    set({ queue: nextQueue });
    persistQueue(sessionId, nextQueue);
  },
  markFlushStart: (count) => {
    set({ isFlushingQueue: true, lastFlushedEventCount: count });
  },
  markFlushComplete: (flushedCount) => {
    set({
      isFlushingQueue: false,
      lastFlushedEventCount: flushedCount,
      lastFlushTimestamp: flushedCount > 0 ? Date.now() : get().lastFlushTimestamp,
    });
  },
  reset: () => {
    const sessionId = get().activeSessionId;
    set({ ...initialState });
    if (sessionId && typeof window !== "undefined") {
      try {
        localStorage.removeItem(getQueueStorageKey(sessionId));
      } catch {
        // ignore
      }
    }
  },
}));

export const shouldQueueOfflineRequest = (state: OfflineQueueState): boolean => {
  return (
    state.connectionState !== "open" ||
    state.isFlushingQueue ||
    state.queue.length > 0
  );
};
