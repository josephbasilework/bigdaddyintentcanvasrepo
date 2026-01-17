"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type TurnResponse = {
  id: number;
  sessionId: string;
  sequenceNumber: number;
  timestamp: string;
  actor: string;
  type: string;
  summary: string;
  payload: Record<string, unknown>;
  relatedNodeId: number | null;
  relatedEdgeId: number | null;
};

type TurnListResponse = {
  turns: TurnResponse[];
  count: number;
};

const CHAT_TURN_TYPES = new Set([
  "user_input",
  "agent_response",
  "system_message",
  "assumption_presented",
  "assumption_confirmed",
  "assumption_rejected",
  "assumption_modified",
]);

const isChatTurn = (turn: TurnResponse): boolean => CHAT_TURN_TYPES.has(turn.type);

const mergeTurns = (current: TurnResponse[], incoming: TurnResponse[]): TurnResponse[] => {
  if (incoming.length === 0) {
    return current;
  }
  const merged = new Map<number, TurnResponse>();
  for (const turn of current) {
    merged.set(turn.id, turn);
  }
  for (const turn of incoming) {
    merged.set(turn.id, turn);
  }
  return Array.from(merged.values()).sort((a, b) => {
    const aTime = Date.parse(a.timestamp) || 0;
    const bTime = Date.parse(b.timestamp) || 0;
    return aTime - bTime;
  });
};

export type UseChatTurnsOptions = {
  sessionIds: string[];
  enabled?: boolean;
  pollIntervalMs?: number;
  limit?: number;
};

export const useChatTurns = ({
  sessionIds,
  enabled = true,
  pollIntervalMs = 5000,
  limit = 200,
}: UseChatTurnsOptions) => {
  const normalizedSessionIds = useMemo(
    () => Array.from(new Set(sessionIds.filter(Boolean))).sort(),
    [sessionIds]
  );
  const sessionKey = normalizedSessionIds.join("|");
  const [turns, setTurns] = useState<TurnResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastSequenceBySession = useRef<Map<string, number>>(new Map());
  const sessionKeyRef = useRef(sessionKey);
  const abortRef = useRef<AbortController | null>(null);

  const fetchTurnsForSession = useCallback(
    async (sessionId: string, afterSequence: number | null, signal: AbortSignal) => {
      const params = new URLSearchParams({
        session_id: sessionId,
        limit: String(limit),
      });
      if (afterSequence !== null) {
        params.set("after_sequence", String(afterSequence));
      }
      const response = await fetch(`${API_BASE_URL}/api/turns?${params.toString()}`, {
        signal,
      });
      if (!response.ok) {
        throw new Error(`Failed to load chat turns (${response.status})`);
      }
      const data = (await response.json()) as TurnListResponse;
      const allTurns = data.turns ?? [];
      if (allTurns.length > 0) {
        const maxSequence = allTurns.reduce(
          (max, turn) => Math.max(max, turn.sequenceNumber),
          afterSequence ?? -1
        );
        lastSequenceBySession.current.set(sessionId, maxSequence);
      }
      return allTurns.filter(isChatTurn);
    },
    [limit]
  );

  useEffect(() => {
    if (!enabled || normalizedSessionIds.length === 0) {
      return undefined;
    }

    let isCancelled = false;
    if (sessionKeyRef.current !== sessionKey) {
      sessionKeyRef.current = sessionKey;
      lastSequenceBySession.current = new Map();
    }

    const fetchAll = async (isInitial: boolean) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      if (isInitial) {
        setIsLoading(true);
      }
      setError(null);

      const results = await Promise.allSettled(
        normalizedSessionIds.map((sessionId) => {
          const afterSequence = isInitial
            ? null
            : lastSequenceBySession.current.get(sessionId) ?? null;
          return fetchTurnsForSession(sessionId, afterSequence, controller.signal);
        })
      );

      if (isCancelled) {
        return;
      }

      const nextTurns: TurnResponse[] = [];
      for (const result of results) {
        if (result.status === "fulfilled") {
          nextTurns.push(...result.value);
        } else if (result.reason) {
          const reason = result.reason as { name?: string };
          if (reason?.name === "AbortError") {
            continue;
          }
          const message =
            result.reason instanceof Error
              ? result.reason.message
              : "Failed to load chat turns.";
          setError(message);
        }
      }

      if (nextTurns.length > 0 || isInitial) {
        setTurns((current) => mergeTurns(isInitial ? [] : current, nextTurns));
      }

      if (isInitial) {
        setIsLoading(false);
      }
    };

    void fetchAll(true);

    const intervalId = window.setInterval(() => {
      void fetchAll(false);
    }, pollIntervalMs);

    return () => {
      isCancelled = true;
      window.clearInterval(intervalId);
      abortRef.current?.abort();
    };
  }, [enabled, fetchTurnsForSession, normalizedSessionIds, pollIntervalMs, sessionKey]);

  return {
    turns,
    isLoading,
    error,
  };
};
