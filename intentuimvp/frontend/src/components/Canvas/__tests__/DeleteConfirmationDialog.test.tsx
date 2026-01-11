import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DeleteConfirmationDialog } from "../DeleteConfirmationDialog";

describe("DeleteConfirmationDialog", () => {
  it("shows node and linked artifact counts", () => {
    render(
      <DeleteConfirmationDialog
        isOpen
        nodeCount={3}
        edgeCount={2}
        documentCount={1}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByText(/delete 3 nodes\?/i)).toBeInTheDocument();
    expect(screen.getByText(/nodes:/i)).toBeInTheDocument();
    expect(screen.getByText(/linked edges:/i)).toBeInTheDocument();
    expect(screen.getByText(/linked documents:/i)).toBeInTheDocument();
  });

  it("invokes confirm and cancel actions", () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();

    render(
      <DeleteConfirmationDialog
        isOpen
        nodeCount={2}
        edgeCount={0}
        documentCount={0}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /confirm delete/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
