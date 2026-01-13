"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import type { DAGData } from "../../state/canvasStore";

export type CalendarSyncCandidate = {
  taskId: string;
  taskTitle: string;
  summary: string;
  start: string;
  end: string;
  description?: string;
  calendarId: string;
};

export type CalendarSyncResult = {
  success: boolean;
  message?: string;
  error?: string;
};

type CalendarSyncDialogProps = {
  isOpen?: boolean;
  dag: DAGData;
  onCancel: () => void;
  onConfirm: (selectedCandidates: CalendarSyncCandidate[]) => Promise<CalendarSyncResult>;
};

type CalendarSyncDialogContentProps = {
  dag: DAGData;
  onCancel: () => void;
  onConfirm: (selectedCandidates: CalendarSyncCandidate[]) => Promise<CalendarSyncResult>;
};

type CalendarSuggestionRow = {
  taskId: string;
  taskTitle: string;
  summary: string | null;
  start: string | null;
  end: string | null;
  description: string | null;
  calendarId: string;
  missingFields: string[];
  candidate: CalendarSyncCandidate | null;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const normalizeText = (value: unknown): string | null => {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return null;
};

const pickText = (
  suggestion: Record<string, unknown>,
  keys: string[]
): string | null => {
  for (const key of keys) {
    const value = normalizeText(suggestion[key]);
    if (value) {
      return value;
    }
  }
  return null;
};

const buildCalendarRows = (dag: DAGData): CalendarSuggestionRow[] => {
  return dag.tasks
    .filter(
      (task) =>
        task.calendarSuggestion &&
        !task.calendarEventId &&
        !task.calendarEventUrl
    )
    .map((task) => {
      const suggestion = isRecord(task.calendarSuggestion)
        ? task.calendarSuggestion
        : {};
      const summary = pickText(suggestion, ["summary", "title"]);
      const start = pickText(suggestion, ["start", "start_time", "startTime"]);
      const end = pickText(suggestion, ["end", "end_time", "endTime"]);
      const description = pickText(suggestion, ["description", "details", "notes"]);
      const calendarId = pickText(suggestion, ["calendar_id", "calendarId"]) ?? "primary";
      const missingFields: string[] = [];

      if (!summary) missingFields.push("summary");
      if (!start) missingFields.push("start");
      if (!end) missingFields.push("end");

      const candidate =
        missingFields.length === 0 && summary && start && end
          ? {
              taskId: task.id,
              taskTitle: task.title,
              summary,
              start,
              end,
              description: description ?? undefined,
              calendarId,
            }
          : null;

      return {
        taskId: task.id,
        taskTitle: task.title,
        summary,
        start,
        end,
        description,
        calendarId,
        missingFields,
        candidate,
      };
    });
};

const CalendarSyncDialogContent = ({
  dag,
  onCancel,
  onConfirm,
}: CalendarSyncDialogContentProps) => {
  const titleId = useId();
  const descriptionId = useId();
  const rows = useMemo(() => buildCalendarRows(dag), [dag]);
  const selectableRows = useMemo(
    () => rows.filter((row) => row.candidate),
    [rows]
  );
  const selectableIds = useMemo(
    () => new Set(selectableRows.map((row) => row.taskId)),
    [selectableRows]
  );
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(
    () => new Set(selectableRows.map((row) => row.taskId))
  );
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

  const eligibleCount = selectableRows.length;
  const selectedCount = Array.from(selectedTaskIds).filter((id) =>
    selectableIds.has(id)
  ).length;
  const allSelected = eligibleCount > 0 && selectedCount === eligibleCount;
  const missingCount = rows.length - eligibleCount;

  const toggleTask = (taskId: string) => {
    setSelectedTaskIds((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  };

  const toggleAll = () => {
    setSelectedTaskIds(allSelected ? new Set() : new Set(selectableIds));
  };

  const handleConfirm = async () => {
    if (isSubmitting) return;
    const selectedCandidates = selectableRows
      .filter((row) => row.candidate && selectedTaskIds.has(row.taskId))
      .map((row) => row.candidate as CalendarSyncCandidate);

    if (selectedCandidates.length === 0) {
      setError("Select at least one task to sync.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const result = await onConfirm(selectedCandidates);
      if (!result.success) {
        setError(result.error || "Calendar sync failed.");
        setIsSubmitting(false);
        return;
      }
      setIsSubmitting(false);
      onCancel();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Calendar sync failed.";
      setError(message);
      setIsSubmitting(false);
    }
  };

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
          maxWidth: "640px",
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
            Review suggested events
          </h3>
        </div>

        <p
          id={descriptionId}
          style={{ margin: 0, color: "#cbd5f5", lineHeight: 1.5 }}
        >
          Select the task suggestions to sync. Only entries with a summary and
          time range can be sent to the calendar.
        </p>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            padding: "12px 14px",
            borderRadius: "10px",
            border: "1px solid rgba(148, 163, 184, 0.2)",
            backgroundColor: "rgba(15, 23, 42, 0.9)",
            fontSize: "12px",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <span style={{ fontWeight: 600, color: "#e2e8f0" }}>
              {eligibleCount} ready to sync
            </span>
            <span style={{ color: "#94a3b8" }}>
              {selectedCount} selected
              {missingCount > 0 ? `, ${missingCount} incomplete` : ""}
            </span>
          </div>
          <button
            type="button"
            onClick={toggleAll}
            disabled={eligibleCount === 0}
            style={{
              padding: "6px 12px",
              borderRadius: "999px",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              backgroundColor:
                eligibleCount === 0
                  ? "rgba(148, 163, 184, 0.2)"
                  : "rgba(59, 130, 246, 0.2)",
              color: eligibleCount === 0 ? "#94a3b8" : "#e2e8f0",
              fontSize: "12px",
              cursor: eligibleCount === 0 ? "not-allowed" : "pointer",
            }}
          >
            {allSelected ? "Clear selection" : "Select all"}
          </button>
        </div>

        <div
          style={{
            display: "grid",
            gap: "12px",
            overflowY: "auto",
            paddingRight: "4px",
          }}
        >
          {rows.length === 0 && (
            <div
              style={{
                padding: "16px",
                borderRadius: "10px",
                border: "1px dashed rgba(148, 163, 184, 0.3)",
                color: "#94a3b8",
                fontSize: "13px",
              }}
            >
              No calendar suggestions available for sync.
            </div>
          )}
          {rows.map((row) => {
            const isDisabled = row.missingFields.length > 0;
            const isChecked = selectedTaskIds.has(row.taskId);
            const scheduleLabel =
              row.start && row.end ? `${row.start} to ${row.end}` : "Missing time range";

            return (
              <label
                key={row.taskId}
                style={{
                  display: "flex",
                  gap: "12px",
                  padding: "12px",
                  borderRadius: "10px",
                  border: "1px solid rgba(148, 163, 184, 0.2)",
                  backgroundColor: "rgba(15, 23, 42, 0.7)",
                  opacity: isDisabled ? 0.6 : 1,
                  cursor: isDisabled ? "not-allowed" : "pointer",
                }}
              >
                <input
                  type="checkbox"
                  aria-label={`Select ${row.taskTitle}`}
                  checked={isChecked}
                  disabled={isDisabled}
                  onChange={() => toggleTask(row.taskId)}
                  style={{ marginTop: "4px" }}
                />
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <div
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "#f8fafc",
                    }}
                  >
                    {row.taskTitle}
                  </div>
                  <div style={{ fontSize: "12px", color: "#cbd5f5" }}>
                    {row.summary ?? "Missing summary"}
                  </div>
                  <div style={{ fontSize: "11px", color: "#94a3b8" }}>
                    {scheduleLabel}
                  </div>
                  {row.description && (
                    <div style={{ fontSize: "11px", color: "#a5b4fc" }}>
                      {row.description}
                    </div>
                  )}
                  {row.calendarId !== "primary" && (
                    <div style={{ fontSize: "11px", color: "#94a3b8" }}>
                      Calendar: {row.calendarId}
                    </div>
                  )}
                  {row.missingFields.length > 0 && (
                    <div style={{ fontSize: "11px", color: "#fca5a5" }}>
                      Missing: {row.missingFields.join(", ")}
                    </div>
                  )}
                </div>
              </label>
            );
          })}
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
            style={{
              padding: "8px 14px",
              backgroundColor: "rgba(148, 163, 184, 0.2)",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              borderRadius: "999px",
              color: "#e2e8f0",
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={selectedCount === 0 || isSubmitting}
            style={{
              padding: "8px 14px",
              backgroundColor:
                selectedCount === 0 || isSubmitting ? "#475569" : "#38bdf8",
              border: "none",
              borderRadius: "999px",
              color: "#0f172a",
              fontSize: "13px",
              fontWeight: 600,
              cursor:
                selectedCount === 0 || isSubmitting ? "not-allowed" : "pointer",
            }}
          >
            {isSubmitting ? "Syncing..." : "Sync selected"}
          </button>
        </div>
      </div>
    </div>
  );
};

export function CalendarSyncDialog({
  isOpen = true,
  dag,
  onCancel,
  onConfirm,
}: CalendarSyncDialogProps) {
  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <CalendarSyncDialogContent dag={dag} onCancel={onCancel} onConfirm={onConfirm} />,
    document.body
  );
}
