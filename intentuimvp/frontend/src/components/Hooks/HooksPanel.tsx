"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const EVENT_TYPE_OPTIONS = [
  "intent.parsed",
  "assumption.confirmed",
  "assumption.rejected",
  "node.created",
  "node.updated",
  "node.deleted",
  "edge.created",
  "edge.updated",
  "edge.deleted",
  "job.started",
  "job.progress",
  "job.completed",
  "job.failed",
  "response.conversational",
  "response.proposal",
  "response.clarification",
  "response.acknowledgment",
  "response.tool_invocation",
  "external.updated",
  "hook.fired",
  "hook.failed",
  "canvas.action",
];

type HookItem = {
  id: number;
  name: string;
  description?: string | null;
  hookType: string;
  eventType?: string | null;
  scheduleType?: string | null;
  trigger?: Record<string, unknown>;
  action?: Record<string, unknown>;
  enabled: boolean;
  lastFiredAt?: string | null;
  nextRunAt?: string | null;
};

type HooksPanelProps = {
  id?: string;
};

const formatTimestamp = (value?: string | null): string => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const deriveScheduleSummary = (hook: HookItem): string => {
  if (hook.hookType !== "schedule") return "—";
  const trigger = hook.trigger ?? {};
  const intervalSeconds =
    typeof trigger.interval_seconds === "number"
      ? trigger.interval_seconds
      : typeof trigger.intervalSeconds === "number"
        ? trigger.intervalSeconds
        : null;
  if (intervalSeconds) {
    return `Every ${intervalSeconds}s`;
  }
  return hook.scheduleType ?? "schedule";
};

export function HooksPanel({ id = "hooks-panel" }: HooksPanelProps) {
  const [hooks, setHooks] = useState<HookItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formState, setFormState] = useState({
    name: "",
    description: "",
    hookType: "event",
    eventType: "node.created",
    intervalSeconds: 900,
    command: "/clear",
    enabled: true,
  });

  const fetchHooks = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/hooks`);
      if (!response.ok) {
        throw new Error(`Failed to load hooks (${response.status})`);
      }
      const data = await response.json();
      setHooks(data.hooks ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load hooks.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchHooks();
  }, [fetchHooks]);

  const isSchedule = formState.hookType === "schedule";
  const trimmedCommand = formState.command.trim();
  const canSubmit = useMemo(() => {
    if (!formState.name.trim()) return false;
    if (!trimmedCommand) return false;
    if (isSchedule) {
      return formState.intervalSeconds > 0;
    }
    return Boolean(formState.eventType);
  }, [formState, isSchedule, trimmedCommand]);

  const handleFieldChange = (
    key: keyof typeof formState,
    value: string | boolean | number
  ) => {
    setFormState((prev) => ({ ...prev, [key]: value }));
  };

  const handleCreateHook = async (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    setIsSubmitting(true);
    setError(null);

    const payload: Record<string, unknown> = {
      name: formState.name.trim(),
      description: formState.description.trim() || null,
      hookType: formState.hookType,
      action: {
        type: "command",
        command: trimmedCommand,
      },
      enabled: formState.enabled,
    };

    if (isSchedule) {
      payload.scheduleType = "interval";
      payload.trigger = {
        interval_seconds: formState.intervalSeconds,
      };
    } else {
      payload.eventType = formState.eventType;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/hooks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`Failed to create hook (${response.status})`);
      }
      await fetchHooks();
      setFormState((prev) => ({
        ...prev,
        name: "",
        description: "",
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create hook.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleEnabled = async (hook: HookItem) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/hooks/${hook.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !hook.enabled }),
      });
      if (!response.ok) {
        throw new Error(`Failed to update hook (${response.status})`);
      }
      await fetchHooks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update hook.");
    }
  };

  const handleDelete = async (hookId: number) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/hooks/${hookId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`Failed to delete hook (${response.status})`);
      }
      setHooks((prev) => prev.filter((hook) => hook.id !== hookId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete hook.");
    }
  };

  return (
    <section className="hooks-panel" id={id} aria-live="polite">
      <header className="hooks-panel-header">
        <div>
          <div className="hooks-panel-title">Hooks</div>
          <div className="hooks-panel-subtitle">
            Automate lifecycle and scheduled triggers
          </div>
        </div>
      </header>
      <div className="hooks-panel-body">
        <form className="hooks-form" onSubmit={handleCreateHook}>
          <div className="hooks-form-grid">
            <label className="hooks-field">
              <span>Name</span>
              <input
                value={formState.name}
                onChange={(event) => handleFieldChange("name", event.target.value)}
                placeholder="Summarize completed jobs"
              />
            </label>
            <label className="hooks-field">
              <span>Description</span>
              <input
                value={formState.description}
                onChange={(event) => handleFieldChange("description", event.target.value)}
                placeholder="Optional details"
              />
            </label>
            <label className="hooks-field">
              <span>Hook Type</span>
              <select
                value={formState.hookType}
                onChange={(event) => handleFieldChange("hookType", event.target.value)}
              >
                <option value="event">Lifecycle event</option>
                <option value="schedule">Scheduled interval</option>
              </select>
            </label>
            {!isSchedule ? (
              <label className="hooks-field">
                <span>Event Type</span>
                <select
                  value={formState.eventType}
                  onChange={(event) => handleFieldChange("eventType", event.target.value)}
                >
                  {EVENT_TYPE_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <label className="hooks-field">
                <span>Interval (seconds)</span>
                <input
                  type="number"
                  min={5}
                  value={formState.intervalSeconds}
                  onChange={(event) =>
                    handleFieldChange(
                      "intervalSeconds",
                      Number(event.target.value)
                    )
                  }
                />
              </label>
            )}
            <label className="hooks-field hooks-command">
              <span>Command</span>
              <input
                value={formState.command}
                onChange={(event) => handleFieldChange("command", event.target.value)}
                placeholder="/analyze summarize the research job"
              />
            </label>
          </div>
          <div className="hooks-form-actions">
            <label className="hooks-toggle">
              <input
                type="checkbox"
                checked={formState.enabled}
                onChange={(event) => handleFieldChange("enabled", event.target.checked)}
              />
              Enabled
            </label>
            <button type="submit" disabled={!canSubmit || isSubmitting}>
              {isSubmitting ? "Saving..." : "Create Hook"}
            </button>
          </div>
        </form>

        <div className="hooks-divider" />

        {isLoading && <div className="hooks-state">Loading hooks...</div>}
        {error && !isLoading && <div className="hooks-error">{error}</div>}
        {!isLoading && !error && hooks.length === 0 && (
          <div className="hooks-state">No hooks yet.</div>
        )}

        {hooks.length > 0 && (
          <div className="hooks-list">
            {hooks.map((hook) => (
              <div key={hook.id} className="hooks-card">
                <div className="hooks-card-header">
                  <div>
                    <div className="hooks-card-title">{hook.name}</div>
                    <div className="hooks-card-subtitle">
                      {hook.hookType === "event"
                        ? hook.eventType
                        : deriveScheduleSummary(hook)}
                    </div>
                  </div>
                  <div className="hooks-card-actions">
                    <button
                      type="button"
                      className={hook.enabled ? "active" : ""}
                      onClick={() => handleToggleEnabled(hook)}
                    >
                      {hook.enabled ? "Disable" : "Enable"}
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => handleDelete(hook.id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
                {hook.description && (
                  <div className="hooks-card-description">{hook.description}</div>
                )}
                <div className="hooks-card-meta">
                  <div>
                    <span>Last fired</span>
                    <strong>{formatTimestamp(hook.lastFiredAt)}</strong>
                  </div>
                  <div>
                    <span>Next run</span>
                    <strong>{formatTimestamp(hook.nextRunAt)}</strong>
                  </div>
                  <div>
                    <span>Status</span>
                    <strong>{hook.enabled ? "Enabled" : "Disabled"}</strong>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <style jsx>{`
        .hooks-panel {
          border-radius: 0.9rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
          background: radial-gradient(circle at top, #0f172a 0%, #0b1120 100%);
          color: #e2e8f0;
          box-shadow: 0 18px 42px rgba(0, 0, 0, 0.45);
          overflow: hidden;
        }

        .hooks-panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.85rem 1rem 0.75rem;
          border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.85);
        }

        .hooks-panel-title {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.18em;
          color: #94a3b8;
        }

        .hooks-panel-subtitle {
          font-size: 0.85rem;
          color: #e2e8f0;
          margin-top: 0.2rem;
        }

        .hooks-panel-body {
          padding: 0.85rem 1rem 1rem;
          max-height: min(65vh, 640px);
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .hooks-form {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .hooks-form-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 0.75rem;
        }

        .hooks-field {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
          font-size: 0.8rem;
          color: #94a3b8;
        }

        .hooks-field input,
        .hooks-field select {
          border-radius: 0.6rem;
          border: 1px solid rgba(148, 163, 184, 0.3);
          padding: 0.55rem 0.7rem;
          background: rgba(15, 23, 42, 0.6);
          color: #e2e8f0;
          font-size: 0.85rem;
        }

        .hooks-command {
          grid-column: 1 / -1;
        }

        .hooks-form-actions {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 1rem;
        }

        .hooks-toggle {
          display: flex;
          align-items: center;
          gap: 0.45rem;
          font-size: 0.85rem;
          color: #cbd5f5;
        }

        .hooks-form-actions button {
          border-radius: 999px;
          border: 1px solid rgba(129, 140, 248, 0.5);
          background: rgba(79, 70, 229, 0.3);
          color: #e0e7ff;
          padding: 0.45rem 1.2rem;
          font-size: 0.85rem;
          cursor: pointer;
          transition: transform 0.15s ease, opacity 0.2s ease;
        }

        .hooks-form-actions button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .hooks-divider {
          height: 1px;
          background: rgba(148, 163, 184, 0.2);
          margin: 0.25rem 0;
        }

        .hooks-state {
          font-size: 0.85rem;
          color: #94a3b8;
        }

        .hooks-error {
          font-size: 0.85rem;
          color: #fca5a5;
          background: rgba(127, 29, 29, 0.35);
          border: 1px solid rgba(239, 68, 68, 0.4);
          padding: 0.5rem 0.65rem;
          border-radius: 0.5rem;
        }

        .hooks-list {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .hooks-card {
          border-radius: 0.75rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.65);
          padding: 0.8rem 0.9rem;
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
        }

        .hooks-card-header {
          display: flex;
          justify-content: space-between;
          gap: 1rem;
        }

        .hooks-card-title {
          font-size: 0.95rem;
          font-weight: 600;
        }

        .hooks-card-subtitle {
          font-size: 0.8rem;
          color: #94a3b8;
        }

        .hooks-card-actions {
          display: flex;
          gap: 0.5rem;
        }

        .hooks-card-actions button {
          border-radius: 999px;
          border: 1px solid rgba(148, 163, 184, 0.3);
          background: rgba(15, 23, 42, 0.6);
          color: #e2e8f0;
          padding: 0.35rem 0.8rem;
          font-size: 0.75rem;
          cursor: pointer;
        }

        .hooks-card-actions button.active {
          border-color: rgba(14, 116, 144, 0.6);
          background: rgba(14, 116, 144, 0.25);
        }

        .hooks-card-actions button.danger {
          border-color: rgba(239, 68, 68, 0.5);
          color: #fecaca;
        }

        .hooks-card-description {
          font-size: 0.85rem;
          color: #cbd5f5;
        }

        .hooks-card-meta {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
          gap: 0.5rem;
          font-size: 0.75rem;
          color: #94a3b8;
        }

        .hooks-card-meta strong {
          display: block;
          margin-top: 0.2rem;
          color: #e2e8f0;
          font-weight: 500;
        }

        @media (max-width: 640px) {
          .hooks-form-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </section>
  );
}
