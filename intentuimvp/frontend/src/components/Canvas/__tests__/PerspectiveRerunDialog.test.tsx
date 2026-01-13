import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PerspectiveRerunDialog } from "../PerspectiveRerunDialog";

// Mock fetch globally
global.fetch = vi.fn();

describe("PerspectiveRerunDialog (FR-012: Multi-Judge Compute)", () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    topic: "AI safety research",
    targetNodeId: "node-123",
    onJobCreated: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render dialog when open", () => {
    render(<PerspectiveRerunDialog {...defaultProps} />);

    expect(screen.getByText("Rerun with More Compute")).toBeInTheDocument();
    expect(screen.getByText("AI safety research")).toBeInTheDocument();
  });

  it("should show all available perspectives", () => {
    render(<PerspectiveRerunDialog {...defaultProps} />);

    // Check for some default perspectives
    expect(screen.getByText("Skeptic")).toBeInTheDocument();
    expect(screen.getByText("Advocate")).toBeInTheDocument();
    expect(screen.getByText("Synthesizer")).toBeInTheDocument();
    expect(screen.getByText("Technical")).toBeInTheDocument();
    expect(screen.getByText("Business")).toBeInTheDocument();
  });

  it("should call onClose when cancel button is clicked", () => {
    render(<PerspectiveRerunDialog {...defaultProps} />);

    const cancelButton = screen.getByRole("button", { name: "Cancel" });
    fireEvent.click(cancelButton);

    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });

  it("should call API and close on successful submit", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: "new-job-123" }),
    });

    render(<PerspectiveRerunDialog {...defaultProps} />);

    const submitButton = screen.getByRole("button", { name: /Run Analysis/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/jobs/perspective-analysis"),
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
        })
      );
    });

    await waitFor(() => {
      expect(defaultProps.onJobCreated).toHaveBeenCalledWith("new-job-123");
    });

    await waitFor(() => {
      expect(defaultProps.onClose).toHaveBeenCalled();
    });
  });

  it("should show error message on HTTP error", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: "Invalid request" }),
    });

    render(<PerspectiveRerunDialog {...defaultProps} />);

    const submitButton = screen.getByRole("button", { name: /Run Analysis/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText("Invalid request")).toBeInTheDocument();
    });
  });

  it("should not render when isOpen is false", () => {
    render(<PerspectiveRerunDialog {...defaultProps} isOpen={false} />);

    expect(screen.queryByText("Rerun with More Compute")).not.toBeInTheDocument();
  });
});
