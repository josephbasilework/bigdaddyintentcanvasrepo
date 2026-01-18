import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HooksPanel } from "../Hooks/HooksPanel";

const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

describe("HooksPanel", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ hooks: [], count: 0 }),
    } as Response);
  });

  it("renders and loads hooks", async () => {
    render(<HooksPanel />);

    expect(screen.getByText("Hooks")).toBeInTheDocument();
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/hooks")
      );
    });
  });
});
