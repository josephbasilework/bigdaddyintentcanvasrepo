import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useJobProgress } from "./useJobProgress";
import { getAGUIClient } from "../agui/client";

// Mock the AG-UI client
vi.mock("../agui/client", () => ({
  getAGUIClient: vi.fn(),
}));

// Mock fetch
global.fetch = vi.fn();

describe("useJobProgress", () => {
  const mockJobId = "test-job-123";
  let messageHandler:
    | ((message: { type: string; payload?: Record<string, unknown> }) => void)
    | null = null;

  beforeEach(() => {
    vi.clearAllMocks();
    messageHandler = null;

    // Mock AG-UI client
    (getAGUIClient as ReturnType<typeof vi.fn>).mockReturnValue({
      onMessage: vi.fn(
        (handler: (message: { type: string; payload?: Record<string, unknown> }) => void) => {
          messageHandler = handler;
          return () => {
            messageHandler = null;
          };
        }
      ),
    });
  });

  it("should return null jobData when jobId is null", () => {
    (getAGUIClient as ReturnType<typeof vi.fn>).mockReturnValue(null);

    const { result } = renderHook(() => useJobProgress(null));

    expect(result.current.jobData).toBeNull();
    expect(result.current.isConnected).toBe(false);
  });

  it("should set error when AG-UI client is not available", () => {
    (getAGUIClient as ReturnType<typeof vi.fn>).mockReturnValue(null);

    const { result } = renderHook(() => useJobProgress(mockJobId));

    expect(result.current.error).toBe("AG-UI client not available");
    expect(result.current.jobData).toBeNull();
  });

  it("should fetch initial job state on mount", async () => {
    const mockJobResponse = {
      job_id: mockJobId,
      job_type: "deep_research",
      status: "in_progress",
      progress_percent: 50,
      current_step: "Researching",
      updated_at: "2024-01-01T00:00:00Z",
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => mockJobResponse,
    });

    const { result } = renderHook(() => useJobProgress(mockJobId));

    await waitFor(() => {
      expect(result.current.jobData).toEqual({
        job_id: mockJobId,
        job_type: "deep_research",
        status: "in_progress",
        progress_percent: 50,
        current_step: "Researching",
        step_number: null,
        steps_total: null,
        data: null,
        timestamp: "2024-01-01T00:00:00Z",
      });
    });
  });

  it("should set isConnected to true when client is available", () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });

    const { result } = renderHook(() => useJobProgress(mockJobId));

    expect(result.current.isConnected).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("should update from job progress messages", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });

    const { result } = renderHook(() => useJobProgress(mockJobId));

    await waitFor(() => {
      expect(messageHandler).not.toBeNull();
    });

    messageHandler?.({
      type: "job.progress",
      payload: {
        job_id: mockJobId,
        job_type: "deep_research",
        status: "in_progress",
        progress_percent: 35,
        current_step: "Streaming",
        timestamp: "2024-01-02T00:00:00Z",
      },
    });

    await waitFor(() => {
      expect(result.current.jobData).toEqual({
        job_id: mockJobId,
        job_type: "deep_research",
        status: "in_progress",
        progress_percent: 35,
        current_step: "Streaming",
        step_number: null,
        steps_total: null,
        data: null,
        timestamp: "2024-01-02T00:00:00Z",
      });
    });
  });

  it("should reset handler when jobId changes", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });

    const { rerender } = renderHook(({ jobId }) => useJobProgress(jobId), {
      initialProps: { jobId: mockJobId },
    });

    await waitFor(() => {
      expect(messageHandler).not.toBeNull();
    });

    rerender({ jobId: "different-job-456" });

    await waitFor(() => {
      expect(messageHandler).not.toBeNull();
    });
  });

  it("should handle fetch errors gracefully", () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useJobProgress(mockJobId));

    // Should not throw, just handle the error silently
    expect(result.current.isConnected).toBe(true);
  });

  it("should handle non-ok responses", () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 404,
    });

    const { result } = renderHook(() => useJobProgress(mockJobId));

    expect(result.current.isConnected).toBe(true);
    // jobData should remain null if fetch fails
    expect(result.current.jobData).toBeNull();
  });

  it("should cleanup message handler on unmount", () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });

    const { unmount } = renderHook(() => useJobProgress(mockJobId));

    expect(messageHandler).not.toBeNull();
    unmount();
    expect(messageHandler).toBeNull();
  });
});
