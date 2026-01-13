/**
 * Tests for useSuccessMetrics hook
 */

import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { useSuccessMetrics, METRIC_CONFIG } from "./useSuccessMetrics";

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("useSuccessMetrics", () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.clearAllMocks();
  });

  it("should have correct metric configurations for all 7 PRD §5.2 metrics", () => {
    expect(Object.keys(METRIC_CONFIG)).toEqual([
      "task_completion_rate",
      "assumption_accuracy",
      "time_to_value",
      "session_continuity",
      "research_job_completion",
      "command_vs_chat_ratio",
      "mcp_adoption",
    ]);
  });

  it("should format task completion rate correctly", () => {
    const config = METRIC_CONFIG.task_completion_rate;
    expect(config.label).toBe("Task Completion Rate");
    expect(config.targetDisplay).toBe("> 80%");
    expect(config.formatValue(85.5)).toBe("85.5%");
    expect(config.higherIsBetter).toBe(true);
  });

  it("should format time-to-value correctly (in seconds)", () => {
    const config = METRIC_CONFIG.time_to_value;
    expect(config.label).toBe("Time-to-Value");
    expect(config.targetDisplay).toBe("< 30s");
    expect(config.formatValue(25000, "ms")).toBe("25.0s");
    expect(config.higherIsBetter).toBe(false); // lower is better
  });

  it("should fetch metrics on mount", async () => {
    const mockResponse = {
      metrics: {
        task_completion_rate: {
          metric_name: "task_completion_rate",
          value: 85.5,
          target: 80.0,
          window: "24h",
          sample_size: 100,
          meets_target: true,
        },
        assumption_accuracy: {
          metric_name: "assumption_accuracy",
          value: 75.0,
          target: 70.0,
          window: "24h",
          sample_size: 50,
          meets_target: true,
        },
        time_to_value: {
          metric_name: "time_to_value",
          value: 25000,
          target: 30000,
          window: "24h",
          sample_size: 80,
          meets_target: true,
          unit: "ms",
        },
        session_continuity: {
          metric_name: "session_continuity",
          value: 65.0,
          target: 60.0,
          window: "24h",
          sample_size: 200,
          meets_target: true,
        },
        research_job_completion: {
          metric_name: "research_job_completion",
          value: 80.0,
          target: 75.0,
          window: "24h",
          sample_size: 20,
          meets_target: true,
        },
        command_vs_chat_ratio: {
          metric_name: "command_vs_chat_ratio",
          value: 4.5,
          target: 3.0,
          window: "24h",
          sample_size: 300,
          meets_target: true,
        },
        mcp_adoption: {
          metric_name: "mcp_adoption",
          value: 35.0,
          target: 30.0,
          window: "24h",
          sample_size: 100,
          meets_target: true,
        },
      },
      window: "24h",
      generated_at: new Date().toISOString(),
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const { result } = renderHook(() => useSuccessMetrics({ enabled: true }));

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("http://localhost:8000/api/v1/metrics/success?window=24h")
    );
    expect(result.current.taskCompletionRate?.value).toBe(85.5);
    expect(result.current.error).toBeNull();
  });

  it("should handle fetch errors", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    const { result } = renderHook(() => useSuccessMetrics({ enabled: true }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe("Network error");
  });

  it("should allow window switching", async () => {
    const mockResponse = {
      metrics: {
        task_completion_rate: {
          metric_name: "task_completion_rate",
          value: 85.5,
          target: 80.0,
          window: "7d",
          sample_size: 500,
          meets_target: true,
        },
        assumption_accuracy: {
          metric_name: "assumption_accuracy",
          value: 75.0,
          target: 70.0,
          window: "7d",
          sample_size: 250,
          meets_target: true,
        },
        time_to_value: {
          metric_name: "time_to_value",
          value: 25000,
          target: 30000,
          window: "7d",
          sample_size: 400,
          meets_target: true,
          unit: "ms",
        },
        session_continuity: {
          metric_name: "session_continuity",
          value: 65.0,
          target: 60.0,
          window: "7d",
          sample_size: 1000,
          meets_target: true,
        },
        research_job_completion: {
          metric_name: "research_job_completion",
          value: 80.0,
          target: 75.0,
          window: "7d",
          sample_size: 100,
          meets_target: true,
        },
        command_vs_chat_ratio: {
          metric_name: "command_vs_chat_ratio",
          value: 4.5,
          target: 3.0,
          window: "7d",
          sample_size: 1500,
          meets_target: true,
        },
        mcp_adoption: {
          metric_name: "mcp_adoption",
          value: 35.0,
          target: 30.0,
          window: "7d",
          sample_size: 500,
          meets_target: true,
        },
      },
      window: "7d",
      generated_at: new Date().toISOString(),
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const { result } = renderHook(() => useSuccessMetrics({ enabled: true }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Switch to 7d window
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    act(() => {
      result.current.setWindow("7d");
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("window=7d")
    );
  });

  it("should not fetch when disabled", () => {
    renderHook(() => useSuccessMetrics({ enabled: false }));

    expect(mockFetch).not.toHaveBeenCalled();
  });
});
