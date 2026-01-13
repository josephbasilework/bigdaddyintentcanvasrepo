import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CalendarApprovalDialog } from "../CalendarApprovalDialog";
import type { PendingCalendarAction } from "../CalendarApprovalDialog";

const buildPendingAction = (): PendingCalendarAction => ({
  tool: "calendar_create",
  summary: "Team Standup",
  start: "2026-01-14T09:00:00Z",
  end: "2026-01-14T09:30:00Z",
  description: "Daily team standup meeting",
  calendar_id: "primary",
  task_id: "task-123",
});

const buildPendingActionWithoutDescription = (): PendingCalendarAction => ({
  tool: "calendar_create",
  summary: "Focus Time",
  start: "2026-01-15T14:00:00Z",
  end: "2026-01-15T16:00:00Z",
  calendar_id: "work",
});

describe("CalendarApprovalDialog", () => {
  it("renders nothing when closed", () => {
    render(
      <CalendarApprovalDialog
        isOpen={false}
        pendingAction={buildPendingAction()}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    expect(
      screen.queryByRole("dialog", { name: /approve calendar event\?/i })
    ).not.toBeInTheDocument();
  });

  it("defaults to open when isOpen is omitted", () => {
    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    expect(
      screen.getByRole("dialog", { name: /approve calendar event\?/i })
    ).toBeInTheDocument();
  });

  it("renders nothing when pendingAction is null", () => {
    render(
      <CalendarApprovalDialog
        pendingAction={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    expect(
      screen.queryByRole("dialog", { name: /approve calendar event\?/i })
    ).not.toBeInTheDocument();
  });

  it("displays calendar event details", () => {
    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    expect(screen.getByText("Team Standup")).toBeInTheDocument();
    expect(screen.getByText(/daily team standup meeting/i)).toBeInTheDocument();
    expect(screen.getByText(/primary calendar/i)).toBeInTheDocument();
    expect(screen.getByText(/task: task-123/i)).toBeInTheDocument();
  });

  it("does not display description section when not provided", () => {
    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingActionWithoutDescription()}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    expect(screen.getByText("Focus Time")).toBeInTheDocument();
    expect(screen.queryByText(/details:/i)).not.toBeInTheDocument();
    expect(screen.getByText(/work/i)).toBeInTheDocument();
  });

  it("closes when cancel button is clicked", () => {
    const onCancel = vi.fn();

    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={onCancel}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("closes when escape key is pressed", () => {
    const onCancel = vi.fn();

    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={onCancel}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("closes when overlay is clicked", () => {
    const onCancel = vi.fn();

    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={onCancel}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    // The overlay is rendered via createPortal to document.body
    const overlay = document.body.querySelector('[role="presentation"]');
    expect(overlay).toBeInTheDocument();
    if (overlay) {
      fireEvent.click(overlay);
      expect(onCancel).toHaveBeenCalledTimes(1);
    }
  });

  it("calls onConfirm with pending action when approve button is clicked", async () => {
    const onConfirm = vi.fn().mockResolvedValue({ success: true, approved: true });
    const onCancel = vi.fn();
    const pendingAction = buildPendingAction();

    render(
      <CalendarApprovalDialog
        pendingAction={pendingAction}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /approve/i }));

    await waitFor(() => expect(onConfirm).toHaveBeenCalledTimes(1));
    expect(onConfirm).toHaveBeenCalledWith(pendingAction);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("shows loading state while submitting", async () => {
    const onConfirm = vi.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({ success: true, approved: true }), 100))
    );

    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />
    );

    const approveButton = screen.getByRole("button", { name: /approve/i });
    fireEvent.click(approveButton);

    expect(approveButton).toHaveTextContent("Approving...");
    expect(approveButton).toBeDisabled();

    await waitFor(() => {
      expect(approveButton).toHaveTextContent("Approve");
    });
  });

  it("shows error message when approval fails", async () => {
    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({
          success: false,
          approved: false,
          error: "Failed to create calendar event",
        })}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /approve/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Failed to create calendar event"
    );
  });

  it("shows error message when onConfirm throws", async () => {
    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockRejectedValue(new Error("Network error"))
        }
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /approve/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Network error");
  });

  it("disables buttons during submission", async () => {
    const onConfirm = vi.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({ success: true, approved: true }), 100))
    );

    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /approve/i }));

    const cancelButton = screen.getByRole("button", { name: /cancel/i });
    await waitFor(() => expect(cancelButton).toBeDisabled());
  });

  it("displays formatted date and time", () => {
    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    // The formatted date should be visible (checking for "When:" label which precedes the date)
    expect(screen.getByText(/when:/i)).toBeInTheDocument();
    // Check for the date/time span by looking for multiple AM/PM occurrences in the time range
    // We'll use getAllByText since AM appears twice in the time range (start and end time)
    const amPmElements = screen.getAllByText(/AM|PM/i);
    expect(amPmElements.length).toBeGreaterThan(0);
  });

  it("displays correct calendar label for primary calendar", () => {
    render(
      <CalendarApprovalDialog
        pendingAction={buildPendingAction()}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    expect(screen.getByText(/primary calendar/i)).toBeInTheDocument();
  });

  it("displays correct calendar label for non-primary calendar", () => {
    const action = buildPendingAction();
    action.calendar_id = "work@example.com";

    render(
      <CalendarApprovalDialog
        pendingAction={action}
        onCancel={vi.fn()}
        onConfirm={vi.fn().mockResolvedValue({ success: true, approved: true })}
      />
    );

    expect(screen.getByText(/work@example.com/i)).toBeInTheDocument();
  });
});
