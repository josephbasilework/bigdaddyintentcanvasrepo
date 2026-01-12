/**
 * Tests for SaveStatusIndicator component
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SaveStatusIndicator } from "../SaveStatusIndicator";
import type { SaveStatus } from "../../../hooks/useAutoSave";

describe("SaveStatusIndicator", () => {
  describe("rendering", () => {
    it("should not render when status is idle", () => {
      const { container } = render(
        <SaveStatusIndicator saveStatus="idle" saveError={null} />
      );

      expect(container.firstChild).toBe(null);
    });

    it("should render saving indicator", () => {
      render(<SaveStatusIndicator saveStatus="saving" saveError={null} />);

      expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Saving workspace");
      expect(screen.getByText("Saving...")).toBeInTheDocument();
    });

    it("should render saved indicator", () => {
      render(<SaveStatusIndicator saveStatus="saved" saveError={null} />);

      expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Workspace saved");
      expect(screen.getByText("Saved")).toBeInTheDocument();
    });

    it("should render error indicator", () => {
      render(<SaveStatusIndicator saveStatus="error" saveError="Network error" />);

      expect(screen.getByRole("status")).toHaveAttribute(
        "aria-label",
        "Failed to save workspace"
      );
      expect(screen.getByText("Save failed")).toBeInTheDocument();
    });

    it("should display error message when save fails", () => {
      render(<SaveStatusIndicator saveStatus="error" saveError="Network error" />);

      const errorMessage = screen.getByText("Network error");
      expect(errorMessage).toBeInTheDocument();
      expect(errorMessage).toHaveAttribute("title", "Network error");
    });
  });

  describe("accessibility", () => {
    it("should have proper aria-live attribute", () => {
      render(<SaveStatusIndicator saveStatus="saving" saveError={null} />);

      const status = screen.getByRole("status");
      expect(status).toHaveAttribute("aria-live", "polite");
      expect(status).toHaveAttribute("aria-atomic", "true");
    });

    it("should have appropriate aria-label for each status", () => {
      const statuses: SaveStatus[] = ["saving", "saved", "error"];
      const labels = {
        saving: "Saving workspace",
        saved: "Workspace saved",
        error: "Failed to save workspace",
      };

      for (const status of statuses) {
        const { unmount } = render(
          <SaveStatusIndicator saveStatus={status} saveError={null} />
        );
        expect(screen.getByRole("status")).toHaveAttribute("aria-label", labels[status]);
        unmount();
      }
    });
  });
});
