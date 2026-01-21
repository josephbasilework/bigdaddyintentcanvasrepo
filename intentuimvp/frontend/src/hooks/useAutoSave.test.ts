/**
 * Tests for useAutoSave hook
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, vi, describe, it, expect } from "vitest";
import { useAutoSave } from "./useAutoSave";

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock the canvas store
const mockNodes = [{ id: "1", type: "text" as const, x: 0, y: 0, z: 0, title: "Test" }];
const mockEdges: never[] = [];
const mockDocuments: never[] = [];

vi.mock("../state/canvasStore", () => ({
  useCanvasStore: vi.fn((selector) => {
    const state = {
      nodes: mockNodes,
      edges: mockEdges,
      documents: mockDocuments,
    };
    return selector ? selector(state) : state;
  }),
}));

describe("useAutoSave", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
  });

  describe("basic functionality", () => {
    it("should start with idle status", () => {
      const { result } = renderHook(() => useAutoSave());

      expect(result.current.saveStatus).toBe("idle");
      expect(result.current.saveError).toBeNull();
      expect(result.current.hasUnsavedChanges).toBe(false);
    });

    it("should expose saveNow function", () => {
      const { result } = renderHook(() => useAutoSave());

      expect(typeof result.current.saveNow).toBe("function");
    });
  });

  describe("save status tracking", () => {
    it("should update status to saved after successful save", async () => {
      const { result } = renderHook(() => useAutoSave({ debounceMs: 100 }));

      await act(async () => {
        await result.current.saveNow();
      });

      await waitFor(() => {
        expect(result.current.saveStatus).toBe("saved");
      });
    });

    it("should update status to error on failed save", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Network error"));

      const { result } = renderHook(() =>
        useAutoSave({ debounceMs: 100, maxRetries: 0 })
      );

      await act(async () => {
        await result.current.saveNow();
      });

      await waitFor(() => {
        expect(result.current.saveStatus).toBe("error");
        expect(result.current.saveError).toBe("Network error");
      });
    });
  });

  describe("manual save", () => {
    it("should call fetch with correct options", async () => {
      const { result } = renderHook(() => useAutoSave());

      await act(async () => {
        await result.current.saveNow();
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/workspace"),
        expect.objectContaining({
          method: "PUT",
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
        })
      );
    });

    it("should include nodes, edges, and documents in payload", async () => {
      const { result } = renderHook(() => useAutoSave());

      await act(async () => {
        await result.current.saveNow();
      });

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      expect(body).toHaveProperty("nodes");
      expect(body).toHaveProperty("edges");
      expect(body).toHaveProperty("documents");
    });
  });

  describe("retry logic", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.runOnlyPendingTimers();
      vi.useRealTimers();
    });

    it("should retry on failure when maxRetries > 0", async () => {
      let attemptCount = 0;
      mockFetch.mockImplementation(() => {
        attemptCount++;
        if (attemptCount === 1) {
          return Promise.reject(new Error("First attempt fails"));
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({}),
        });
      });

      const { result } = renderHook(() =>
        useAutoSave({ debounceMs: 100, maxRetries: 2, retryDelayMs: 50 })
      );

      await act(async () => {
        const savePromise = result.current.saveNow();
        await vi.runAllTimersAsync();
        await savePromise;
      });

      expect(attemptCount).toBeGreaterThanOrEqual(2);
    });

    it("should stop retrying after maxRetries is reached", async () => {
      let attemptCount = 0;
      mockFetch.mockImplementation(() => {
        attemptCount++;
        return Promise.reject(new Error("Always fails"));
      });

      const { result } = renderHook(() =>
        useAutoSave({ debounceMs: 100, maxRetries: 1, retryDelayMs: 10 })
      );

      await act(async () => {
        const savePromise = result.current.saveNow();
        await vi.runAllTimersAsync();
        await savePromise;
      });

      // Should have attempted at least once and ended in error state
      expect(attemptCount).toBeGreaterThanOrEqual(1);
      expect(result.current.saveStatus).toBe("error");
    });
  });

  describe("document persistence", () => {
    it("should include documents array in save payload", async () => {
      const { result } = renderHook(() => useAutoSave());

      await act(async () => {
        await result.current.saveNow();
      });

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      expect(body).toHaveProperty("documents");
      expect(Array.isArray(body.documents)).toBe(true);
    });
  });
});
