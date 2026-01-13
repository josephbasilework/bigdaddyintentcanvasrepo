import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CalendarSyncDialog } from "../CalendarSyncDialog";
import type { DAGData } from "../../../state/canvasStore";

const buildDag = (): DAGData => ({
  tasks: [
    {
      id: "task-1",
      title: "Kickoff",
      status: "pending",
      calendarSuggestion: {
        summary: "Kickoff",
        start: "2026-01-13T10:00:00Z",
        end: "2026-01-13T11:00:00Z",
        description: "Project kickoff meeting",
      },
    },
    {
      id: "task-2",
      title: "Design review",
      status: "pending",
      calendarSuggestion: {
        summary: "Design review",
        start: "2026-01-14T09:00:00Z",
        end: "2026-01-14T10:00:00Z",
      },
    },
    {
      id: "task-3",
      title: "Missing details",
      status: "pending",
      calendarSuggestion: {
        summary: "Needs schedule",
        start: "2026-01-15T09:00:00Z",
      },
    },
  ],
});

describe("CalendarSyncDialog", () => {
  it("preselects eligible suggestions and disables incomplete ones", () => {
    render(
      <CalendarSyncDialog
        isOpen
        dag={buildDag()}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({ success: true })}
      />
    );

    const kickoffCheckbox = screen.getByRole("checkbox", {
      name: /select kickoff/i,
    });
    expect(kickoffCheckbox).toBeChecked();

    const missingCheckbox = screen.getByRole("checkbox", {
      name: /select missing details/i,
    });
    expect(missingCheckbox).toBeDisabled();
    expect(screen.getByText(/missing: end/i)).toBeInTheDocument();
  });

  it("submits selected candidates and closes on success", async () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn().mockResolvedValue({ success: true });

    render(
      <CalendarSyncDialog
        isOpen
        dag={buildDag()}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />
    );

    const designCheckbox = screen.getByRole("checkbox", {
      name: /select design review/i,
    });
    fireEvent.click(designCheckbox);

    fireEvent.click(screen.getByRole("button", { name: /sync selected/i }));

    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));

    expect(onConfirm).toHaveBeenCalledWith([
      {
        taskId: "task-1",
        taskTitle: "Kickoff",
        summary: "Kickoff",
        start: "2026-01-13T10:00:00Z",
        end: "2026-01-13T11:00:00Z",
        description: "Project kickoff meeting",
        calendarId: "primary",
      },
    ]);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("shows errors from sync failures", async () => {
    render(
      <CalendarSyncDialog
        isOpen
        dag={buildDag()}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({
          success: false,
          error: "Calendar sync failed.",
        })}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /sync selected/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Calendar sync failed."
    );
  });
});
