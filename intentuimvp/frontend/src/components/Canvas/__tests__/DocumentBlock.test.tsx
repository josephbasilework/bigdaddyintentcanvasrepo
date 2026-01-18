import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DocumentBlock } from "../DocumentBlock";

describe("DocumentBlock", () => {
  it("applies formatting and saves content", async () => {
    const handleSave = vi.fn();
    const handleCancel = vi.fn();

    render(
      <DocumentBlock
        nodeId="node-1"
        title="Spec"
        content="Hello world"
        onSave={handleSave}
        onCancel={handleCancel}
      />
    );

    const textarea = screen.getByLabelText(/document content/i) as HTMLTextAreaElement;
    textarea.setSelectionRange(0, 5);
    fireEvent.click(screen.getByRole("button", { name: /bold/i }));

    await waitFor(() => {
      expect(textarea.value).toBe("**Hello** world");
    });

    fireEvent.click(screen.getByRole("button", { name: /save document/i }));

    expect(handleSave).toHaveBeenCalledWith("node-1", "Spec", "**Hello** world");
  });

  it("renders markdown preview", () => {
    render(
      <DocumentBlock
        nodeId="node-2"
        title="Preview"
        content="# Title\n\nSome text"
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const preview = screen.getByLabelText(/document preview/i);
    expect(within(preview).getByText(/title/i)).toBeInTheDocument();
    expect(within(preview).getByText(/some text/i)).toBeInTheDocument();
  });
});
