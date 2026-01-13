/**
 * React hook for fetching PRD §5.2 success metrics from the backend API.
 *
 * Provides:
 * - All 7 success metrics with targets
 * - Loading and error states
 * - Last-updated timestamp
 * - Window selection (24h, 7d)
 */

import { useState, useEffect, useCallback } from "react";

export interface MetricResult {
  metric_name: string;
  value: number;
  target: number;
  window: string;
  sample_size: number;
  meets_target: boolean;
  success_count?: number;
  accepted_count?: number;
  unit?: string;
  resuming_count?: number;
  completed_count?: number;
  command_count?: number;
  chat_count?: number;
  users_with_mcp?: number;
}

export interface MetricsResponse {
  metrics: Record<string, MetricResult>;
  window: string;
  generated_at: string;
}

export interface SuccessMetricsData {
  taskCompletionRate: MetricResult | null;
  assumptionAccuracy: MetricResult | null;
  timeToValue: MetricResult | null;
  sessionContinuity: MetricResult | null;
  researchJobCompletion: MetricResult | null;
  commandVsChatRatio: MetricResult | null;
  mcpAdoption: MetricResult | null;
  lastUpdated: Date | null;
  window: string;
}

export interface UseSuccessMetricsOptions {
  window?: "24h" | "7d";
  userId?: string;
  workspaceId?: string;
  pollInterval?: number; // milliseconds
  enabled?: boolean;
}

export interface UseSuccessMetricsResult extends SuccessMetricsData {
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  setWindow: (window: "24h" | "7d") => void;
}

// Metric display configuration
export const METRIC_CONFIG: Record<
  string,
  {
    label: string;
    description: string;
    targetDisplay: string;
    formatValue: (value: number, unit?: string) => string;
    color: string;
    higherIsBetter: boolean;
  }
> = {
  task_completion_rate: {
    label: "Task Completion Rate",
    description: "% of intents executed successfully",
    targetDisplay: "> 80%",
    formatValue: (v) => `${v.toFixed(1)}%`,
    color: "#34d399",
    higherIsBetter: true,
  },
  assumption_accuracy: {
    label: "Assumption Accuracy",
    description: "% of assumptions accepted without modification",
    targetDisplay: "> 70%",
    formatValue: (v) => `${v.toFixed(1)}%`,
    color: "#38bdf8",
    higherIsBetter: true,
  },
  time_to_value: {
    label: "Time-to-Value",
    description: "Avg time from command to useful output",
    targetDisplay: "< 30s",
    formatValue: (v) => `${(v / 1000).toFixed(1)}s`,
    color: "#fbbf24",
    higherIsBetter: false, // lower is better
  },
  session_continuity: {
    label: "Session Continuity",
    description: "% of users resuming previous workspace",
    targetDisplay: "> 60%",
    formatValue: (v) => `${v.toFixed(1)}%`,
    color: "#a78bfa",
    higherIsBetter: true,
  },
  research_job_completion: {
    label: "Research Job Completion",
    description: "% of deep research jobs completed",
    targetDisplay: "> 75%",
    formatValue: (v) => `${v.toFixed(1)}%`,
    color: "#f97316",
    higherIsBetter: true,
  },
  command_vs_chat_ratio: {
    label: "Command vs. Chat Ratio",
    description: "Ratio of command to chat interactions",
    targetDisplay: "> 3:1",
    formatValue: (v) => `${v.toFixed(1)}:1`,
    color: "#22d3ee",
    higherIsBetter: true,
  },
  mcp_adoption: {
    label: "MCP Adoption",
    description: "% of users with at least one MCP configured",
    targetDisplay: "> 30%",
    formatValue: (v) => `${v.toFixed(1)}%`,
    color: "#f472b6",
    higherIsBetter: true,
  },
};

/**
 * Fetch success metrics from the backend API
 */
async function fetchSuccessMetrics(
  window: "24h" | "7d",
  userId?: string,
  workspaceId?: string
): Promise<MetricsResponse> {
  const params = new URLSearchParams({ window });
  if (userId) params.set("user_id", userId);
  if (workspaceId) params.set("workspace_id", workspaceId);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const response = await fetch(
    `${API_BASE_URL}/api/v1/metrics/success?${params.toString()}`
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch metrics: ${response.status} ${text}`);
  }

  return response.json();
}

/**
 * React hook for fetching and managing success metrics
 */
export function useSuccessMetrics({
  window: initialWindow = "24h",
  userId,
  workspaceId,
  pollInterval,
  enabled = true,
}: UseSuccessMetricsOptions = {}): UseSuccessMetricsResult {
  const [window, setWindow] = useState<"24h" | "7d">(initialWindow);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<SuccessMetricsData>({
    taskCompletionRate: null,
    assumptionAccuracy: null,
    timeToValue: null,
    sessionContinuity: null,
    researchJobCompletion: null,
    commandVsChatRatio: null,
    mcpAdoption: null,
    lastUpdated: null,
    window,
  });

  const fetch = useCallback(async () => {
    if (!enabled) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetchSuccessMetrics(window, userId, workspaceId);

      setData({
        taskCompletionRate: response.metrics.task_completion_rate ?? null,
        assumptionAccuracy: response.metrics.assumption_accuracy ?? null,
        timeToValue: response.metrics.time_to_value ?? null,
        sessionContinuity: response.metrics.session_continuity ?? null,
        researchJobCompletion: response.metrics.research_job_completion ?? null,
        commandVsChatRatio: response.metrics.command_vs_chat_ratio ?? null,
        mcpAdoption: response.metrics.mcp_adoption ?? null,
        lastUpdated: new Date(response.generated_at),
        window: response.window,
      });
    } catch (err) {
      const errorObj =
        err instanceof Error ? err : new Error("Unknown error fetching metrics");
      setError(errorObj);
    } finally {
      setIsLoading(false);
    }
  }, [enabled, window, userId, workspaceId]);

  useEffect(() => {
    fetch();

    if (pollInterval && pollInterval > 0) {
      const intervalId = setInterval(fetch, pollInterval);
      return () => clearInterval(intervalId);
    }
  }, [fetch, pollInterval]);

  return {
    ...data,
    isLoading,
    error,
    refetch: fetch,
    setWindow,
  };
}
