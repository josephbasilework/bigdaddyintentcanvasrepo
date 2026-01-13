"use client";

import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Pending calendar action that requires user approval.
 * Matches the backend response from calendar_create when requires_confirmation is true.
 */
export type PendingCalendarAction = {
  tool: string;
  summary: string;
  start: string;
  end: string;
  description?: string | null;
  calendar_id?: string;
  task_id?: string | null;
};

export type CalendarApprovalResult = {
  success: boolean;
  approved: boolean;
  message?: string;
  error?: string;
};

type CalendarApprovalDialogProps = {
  isOpen?: boolean;
  pendingAction: PendingCalendarAction | null;
  onCancel: () => void;
  onConfirm: (action: PendingCalendarAction) => Promise<CalendarApprovalResult>;
};

type CalendarApprovalDialogContentProps = {
  pendingAction: PendingCalendarAction | null;
  onCancel: () => void;
  onConfirm: (action: PendingCalendarAction) => Promise<CalendarApprovalResult>;
};

const formatDateTime = (isoString: string): string => {
  try {
    const date = new Date(isoString);
    return date.toLocaleString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return isoString;
  }
};

const CalendarApprovalDialogContent = ({
  pendingAction,
  onCancel,
  onConfirm,
}: CalendarApprovalDialogContentProps) => {
  const titleId = useId();
  const descriptionId = useId();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  const handleConfirm = async () => {
    if (!pendingAction || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const result = await onConfirm(pendingAction);
      if (!result.success) {
        setError(result.error || "Calendar approval failed.");
        setIsSubmitting(false);
        return;
      }
      setIsSubmitting(false);
      onCancel();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Calendar approval failed.";
      setError(message);
      setIsSubmitting(false);
    }
  };

  if (!pendingAction) {
    return null;
  }

  const { summary, start, end, description, calendar_id, task_id } = pendingAction;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(2, 6, 23, 0.72)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10003,
      }}
      onClick={onCancel}
      role="presentation"
    >
      <div
        style={{
          backgroundColor: "#111827",
          border: "1px solid rgba(148, 163, 184, 0.3)",
          borderRadius: "12px",
          padding: "24px",
          width: "92%",
          maxWidth: "540px",
          maxHeight: "80vh",
          boxShadow: "0 18px 30px rgba(0, 0, 0, 0.5)",
          color: "#e2e8f0",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
          overflow: "hidden",
        }}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <div
            style={{
              fontSize: "12px",
              textTransform: "uppercase",
              letterSpacing: "0.12em",
              color: "#94a3b8",
            }}
          >
            Calendar approval
          </div>
          <h3
            id={titleId}
            style={{ margin: 0, fontSize: "18px", color: "#f8fafc" }}
          >
            Approve calendar event?
          </h3>
        </div>

        <p
          id={descriptionId}
          style={{ margin: 0, color: "#cbd5f5", lineHeight: 1.5 }}
        >
          An agent requests approval to create this calendar event. Review the
          details below.
        </p>

        <div
          style={{
            display: "grid",
            gap: "12px",
            padding: "16px",
            borderRadius: "10px",
            border: "1px solid rgba(148, 163, 184, 0.2)",
            backgroundColor: "rgba(15, 23, 42, 0.9)",
          }}
        >
          <div
            style={{
              fontSize: "15px",
              fontWeight: 600,
              color: "#f8fafc",
              paddingBottom: "8px",
              borderBottom: "1px solid rgba(148, 163, 184, 0.15)",
            }}
          >
            {summary}
          </div>

          <div style={{ display: "grid", gap: "10px", fontSize: "13px" }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
              <span style={{ color: "#94a3b8", minWidth: "60px" }}>When:</span>
              <span style={{ color: "#e2e8f0" }}>
                {formatDateTime(start)} to {formatDateTime(end)}
              </span>
            </div>

            {description && (
              <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                <span style={{ color: "#94a3b8", minWidth: "60px" }}>Details:</span>
                <span style={{ color: "#cbd5f5", lineHeight: 1.5 }}>
                  {description}
                </span>
              </div>
            )}

            <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
              <span style={{ color: "#94a3b8", minWidth: "60px" }}>Calendar:</span>
              <span style={{ color: "#cbd5f5" }}>
                {calendar_id === "primary" || !calendar_id
                  ? "Primary calendar"
                  : calendar_id}
              </span>
            </div>

            {task_id && (
              <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                <span style={{ color: "#94a3b8", minWidth: "60px" }}>Source:</span>
                <span style={{ color: "#cbd5f5" }}>Task: {task_id}</span>
              </div>
            )}
          </div>
        </div>

        {error && (
          <div
            role="alert"
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.12)",
              border: "1px solid rgba(239, 68, 68, 0.35)",
              borderRadius: "10px",
              padding: "10px 12px",
              color: "#fecaca",
              fontSize: "12px",
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            style={{
              padding: "8px 14px",
              backgroundColor: "rgba(148, 163, 184, 0.2)",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              borderRadius: "999px",
              color: "#e2e8f0",
              fontSize: "13px",
              cursor: isSubmitting ? "not-allowed" : "pointer",
              opacity: isSubmitting ? 0.6 : 1,
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isSubmitting}
            style={{
              padding: "8px 14px",
              backgroundColor: isSubmitting ? "#475569" : "#38bdf8",
              border: "none",
              borderRadius: "999px",
              color: "#0f172a",
              fontSize: "13px",
              fontWeight: 600,
              cursor: isSubmitting ? "not-allowed" : "pointer",
            }}
          >
            {isSubmitting ? "Approving..." : "Approve"}
          </button>
        </div>
      </div>
    </div>
  );
};

/**
 * Calendar approval dialog for single event HITL (human-in-the-loop) confirmation.
 *
 * This dialog is shown when an agent or calendar operation returns requires_confirmation=true.
 * It displays the pending calendar event details and allows the user to approve or cancel.
 *
 * Example usage:
 * ```tsx
 * const [pendingAction, setPendingAction] = useState<PendingCalendarAction | null>(null);
 * const [isApprovalOpen, setIsApprovalOpen] = useState(false);
 *
 * const handleApprovalConfirm = async (action: PendingCalendarAction) => {
 *   const response = await fetch('/api/mcp/calendar/create', {
 *     method: 'POST',
 *     body: JSON.stringify({ ...action, user_confirmed: true }),
 *   });
 *   return { success: response.ok, approved: true };
 * };
 *
 * <CalendarApprovalDialog
 *   isOpen={isApprovalOpen}
 *   pendingAction={pendingAction}
 *   onCancel={() => setIsApprovalOpen(false)}
 *   onConfirm={handleApprovalConfirm}
 * />
 * ```
 */
export function CalendarApprovalDialog({
  isOpen = true,
  pendingAction,
  onCancel,
  onConfirm,
}: CalendarApprovalDialogProps) {
  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <CalendarApprovalDialogContent
      pendingAction={pendingAction}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />,
    document.body
  );
}
