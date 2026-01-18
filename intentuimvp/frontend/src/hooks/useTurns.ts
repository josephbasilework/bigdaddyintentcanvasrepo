"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TurnListResponse, TurnResponse } from "./turnTypes";
import { getAGUIClient } from "../agui/client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export type UseTurnsOptions = {
  sessionIds: string[];
  enabled?: boolean;
  pollIntervalMs?: number;
  limit?: number;
  filters?: TurnFilters;
};

export type TurnFilters = {
  actorGroups?: string[];
  categories?: string[];
  eventTypes?: string[];
  relatedNodeId?: number | null;
  relatedEdgeId?: number | null;
};

export const useTurns = ({
  sessionIds,
  enabled = true,
  pollIntervalMs = 5000,
  limit = 200,
  filters,
}: UseTurnsOptions) => {
  const normalizedSessionIds = useMemo(
    () => Array.from(new Set(sessionIds.filter(Boolean))).sort(),
    [sessionIds]
  );
  const normalizedFilters = useMemo(() => {
    const normalizeList = (values?: string[]) =>
      Array.from(
        new Set(
          (values ?? [])
            .map((value) => value.trim().toLowerCase())
            .filter(Boolean)
        )
      ).sort();
    return {
      actorGroups: normalizeList(filters?.actorGroups),
      categories: normalizeList(filters?.categories),
      eventTypes: normalizeList(filters?.eventTypes),
      relatedNodeId:
        typeof filters?.relatedNodeId === "number" && Number.isFinite(filters.relatedNodeId)
          ? filters.relatedNodeId
          : null,
      relatedEdgeId:
        typeof filters?.relatedEdgeId === "number" && Number.isFinite(filters.relatedEdgeId)
          ? filters.relatedEdgeId
          : null,
    };
  }, [filters]);
  const filtersKey = useMemo(
    () => JSON.stringify(normalizedFilters),
    [normalizedFilters]
  );
  const sessionKey = `${normalizedSessionIds.join("|")}::${filtersKey}`;
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
      normalizedFilters.actorGroups.forEach((group) =>
        params.append("actor_group", group)
      );
      normalizedFilters.categories.forEach((category) =>
        params.append("category", category)
      );
      normalizedFilters.eventTypes.forEach((eventType) =>
        params.append("event_type", eventType)
      );
      if (normalizedFilters.relatedNodeId !== null) {
        params.set("related_node_id", String(normalizedFilters.relatedNodeId));
      }
      if (normalizedFilters.relatedEdgeId !== null) {
        params.set("related_edge_id", String(normalizedFilters.relatedEdgeId));
      }
      const response = await fetch(`${API_BASE_URL}/api/turns?${params.toString()}`, {
        signal,
      });
      if (!response.ok) {
        throw new Error(`Failed to load turns (${response.status})`);
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
      return allTurns;
    },
    [limit, normalizedFilters]
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
              : "Failed to load turns.";
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

  useEffect(() => {
    if (!enabled || normalizedSessionIds.length === 0) {
      return undefined;
    }

    const client = getAGUIClient();
    if (!client) {
      return undefined;
    }

    const unsubscribe = client.onMessage((message) => {
      if (message.type !== "turn.created") {
        return;
      }
      const payload = message.payload as TurnResponse;
      if (!normalizedSessionIds.includes(payload.sessionId)) {
        return;
      }
      lastSequenceBySession.current.set(payload.sessionId, payload.sequenceNumber);
      setTurns((current) => mergeTurns(current, [payload]));
    });

    return () => {
      unsubscribe();
    };
  }, [enabled, normalizedSessionIds]);

  return {
    turns,
    isLoading,
    error,
  };
};
