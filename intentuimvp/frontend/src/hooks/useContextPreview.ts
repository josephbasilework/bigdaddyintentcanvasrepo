"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ContextPreview, SelectionScope } from "@/types/contextPreview";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type UseContextPreviewOptions = {
  enabled?: boolean;
  text: string;
  attachments: string[];
  selection?: SelectionScope | null;
  sessionId?: string | null;
  workspaceId?: number | string | null;
  debounceMs?: number;
};

type UseContextPreviewState = {
  preview: ContextPreview | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
};

export const useContextPreview = ({
  enabled = true,
  text,
  attachments,
  selection,
  sessionId,
  workspaceId,
  debounceMs = 300,
}: UseContextPreviewOptions): UseContextPreviewState => {
  const [preview, setPreview] = useState<ContextPreview | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<number | null>(null);

  const payload = useMemo(
    () => ({
      text,
      attachments,
      selection,
      session_id: sessionId ?? undefined,
      workspace_id: workspaceId ?? undefined,
    }),
    [text, attachments, selection, sessionId, workspaceId]
  );

  const fetchPreview = useCallback(() => {
    if (!enabled) {
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);

    void fetch(`${API_BASE_URL}/api/context/preview`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Preview error: ${response.status} ${response.statusText}`);
        }
        return (await response.json()) as ContextPreview;
      })
      .then((data) => {
        setPreview(data);
      })
      .catch((err) => {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load preview.");
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [enabled, payload]);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = window.setTimeout(() => {
      fetchPreview();
    }, debounceMs);

    return () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      abortRef.current?.abort();
    };
  }, [enabled, debounceMs, fetchPreview]);

  return {
    preview,
    isLoading,
    error,
    refresh: fetchPreview,
  };
};
