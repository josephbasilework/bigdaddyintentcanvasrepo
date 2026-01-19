import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IntentMemoryPanel } from "../IntentMemory/IntentMemoryPanel";

const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

describe("IntentMemoryPanel", () => {
  const now = new Date().toISOString();

  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = input.toString();
      if (url.includes("/api/intent-memory/entries")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            count: 2,
            entries: [
              {
                entry_id: "mem-1",
                scope: "user",
                kind: "explicit",
                usage: "routing",
                trigger: "Launch prep",
                trigger_type: "contains",
                response: { handler: "plan_handler" },
                confidence: 0.92,
                enabled: true,
                workspace_id: null,
                session_id: null,
                created_at: now,
                updated_at: now,
                stats: {
                  total: 3,
                  accepted: 2,
                  rejected: 1,
                  last_used_at: now,
                },
                description: null,
              },
              {
                entry_id: "mem-2",
                scope: "workspace",
                kind: "explicit",
                usage: "routing",
                trigger: "Launch prep",
                trigger_type: "contains",
                response: { handler: "export_handler" },
                confidence: 0.88,
                enabled: true,
                workspace_id: "42",
                session_id: null,
                created_at: now,
                updated_at: now,
                stats: {
                  total: 4,
                  accepted: 4,
                  rejected: 0,
                  last_used_at: now,
                },
                description: null,
              },
            ],
          }),
        } as Response);
      }
      if (url.includes("/api/intent-memory/settings")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            enabled: true,
            auto_classify_enabled: true,
            auto_confirm_enabled: true,
            suggestions_enabled: true,
            auto_classify_threshold: 0.7,
            auto_confirm_threshold: 0.8,
            auto_confirm_min_samples: 3,
            auto_confirm_similarity_threshold: 0.85,
            note_suggestion_threshold: 0.6,
          }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      } as Response);
    });
  });

  it("renders entries and settings", async () => {
    render(<IntentMemoryPanel />);

    expect(screen.getByText("Intent Memory")).toBeInTheDocument();
    expect(
      await screen.findByText("Auto-confirm trusted patterns")
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/intent-memory/entries")
      );
    });

    expect((await screen.findAllByText("Launch prep")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Conflict")).length).toBeGreaterThan(0);
  });
});
