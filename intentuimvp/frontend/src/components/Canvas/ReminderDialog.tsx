"use client";

import { useEffect, useId, useMemo, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { useNotificationsStore } from "@/state/notificationsStore";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SESSION_ID_STORAGE_KEY = "intentui_workspace_session_id";

interface ReminderDialogProps {
  isOpen: boolean;
  nodeId: string;
  nodeTitle: string;
  onCancel: () => void;
}

const getSessionId = (): string | null => {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return localStorage.getItem(SESSION_ID_STORAGE_KEY);
  } catch {
    return null;
  }
};

export function ReminderDialog({
  isOpen,
  nodeId,
  nodeTitle,
  onCancel,
}: ReminderDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [scheduledFor, setScheduledFor] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const enqueueToast = useNotificationsStore((state) => state.enqueueToast);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setTitle(`Reminder: ${nodeTitle}`);
    setMessage(`Remember to follow up on "${nodeTitle}".`);
    setScheduledFor("");
    setError(null);
  }, [isOpen, nodeTitle]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onCancel]);

  const minDateValue = useMemo(() => {
    const now = new Date();
    return new Date(now.getTime() + 60_000).toISOString().slice(0, 16);
  }, []);

  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !message.trim() || !scheduledFor) {
      setError("Title, message, and time are required.");
      return;
    }
    const parsed = new Date(scheduledFor);
    if (Number.isNaN(parsed.getTime())) {
      setError("Provide a valid reminder time.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = {
        title: title.trim(),
        message: message.trim(),
        remindAt: parsed.toISOString(),
        nodeId,
        sessionId: getSessionId(),
      };
      const response = await fetch(`${API_BASE_URL}/api/reminders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`Failed to set reminder (${response.status})`);
      }
      enqueueToast({
        level: "success",
        title: "Reminder set",
        message: `We will remind you about ${nodeTitle}.`,
        durationMs: 4000,
      });
      onCancel();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set reminder.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return createPortal(
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(2, 6, 23, 0.72)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10004,
      }}
      onClick={onCancel}
      role="presentation"
    >
      <form
        style={{
          backgroundColor: "#111827",
          border: "1px solid rgba(148, 163, 184, 0.3)",
          borderRadius: "12px",
          padding: "24px",
          width: "92%",
          maxWidth: "520px",
          boxShadow: "0 18px 30px rgba(0, 0, 0, 0.5)",
          color: "#e2e8f0",
          display: "flex",
          flexDirection: "column",
          gap: "14px",
        }}
        onClick={(event) => event.stopPropagation()}
        onSubmit={handleSubmit}
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
            Reminder
          </div>
          <h3 id={titleId} style={{ margin: 0, fontSize: "18px", color: "#f8fafc" }}>
            Set a reminder
          </h3>
          <p id={descriptionId} style={{ margin: 0, color: "#cbd5f5", fontSize: "13px" }}>
            Schedule a notification for this node.
          </p>
        </div>

        <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <span style={{ fontSize: "12px", color: "#cbd5f5" }}>Title</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Reminder title"
            style={{
              padding: "8px 10px",
              borderRadius: "8px",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              backgroundColor: "rgba(15, 23, 42, 0.8)",
              color: "#e2e8f0",
              fontSize: "13px",
            }}
          />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <span style={{ fontSize: "12px", color: "#cbd5f5" }}>Message</span>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            rows={3}
            placeholder="Reminder details"
            style={{
              padding: "8px 10px",
              borderRadius: "8px",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              backgroundColor: "rgba(15, 23, 42, 0.8)",
              color: "#e2e8f0",
              fontSize: "13px",
              resize: "vertical",
            }}
          />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <span style={{ fontSize: "12px", color: "#cbd5f5" }}>Remind me at</span>
          <input
            type="datetime-local"
            min={minDateValue}
            value={scheduledFor}
            onChange={(event) => setScheduledFor(event.target.value)}
            style={{
              padding: "8px 10px",
              borderRadius: "8px",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              backgroundColor: "rgba(15, 23, 42, 0.8)",
              color: "#e2e8f0",
              fontSize: "13px",
            }}
          />
          <span style={{ fontSize: "11px", color: "#94a3b8" }}>
            Uses your local time zone.
          </span>
        </label>

        {error && (
          <div style={{ color: "#fca5a5", fontSize: "12px" }}>{error}</div>
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
            type="submit"
            disabled={isSubmitting}
            style={{
              padding: "8px 14px",
              backgroundColor: "#38bdf8",
              border: "none",
              borderRadius: "999px",
              color: "#0f172a",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              opacity: isSubmitting ? 0.7 : 1,
            }}
          >
            {isSubmitting ? "Scheduling..." : "Schedule reminder"}
          </button>
        </div>
      </form>
    </div>,
    document.body
  );
}
