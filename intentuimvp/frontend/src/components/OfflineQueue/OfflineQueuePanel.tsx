"use client";

import { useMemo, useState, type CSSProperties } from "react";
import type { OfflineQueuedEvent as QueuedEvent } from "@/state/offlineQueueStore";

type ConnectionState = "connecting" | "open" | "closed" | "error";

interface OfflineQueuePanelProps {
  connectionState: ConnectionState;
  queuedEvents: QueuedEvent[];
  onUpdateEvent: (id: string, data: string | object) => void;
  onDeleteEvent: (id: string) => void;
  isFlushingQueue: boolean;
  lastFlushedEventCount: number;
}

const formatTimestamp = (timestamp: number): string => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "Unknown time";
  }
  const year = String(date.getFullYear());
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
};

const serializeEventData = (data: string | object): string => {
  if (typeof data === "string") {
    return data;
  }
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
};

const parseDraftData = (draft: string): string | object => {
  const trimmed = draft.trim();
  if (!trimmed) {
    return "";
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return draft;
  }
};

const getStatusLabel = (state: ConnectionState): string => {
  switch (state) {
    case "open":
      return "Online";
    case "connecting":
      return "Connecting";
    case "error":
      return "Error";
    case "closed":
    default:
      return "Offline";
  }
};

const getStatusColor = (state: ConnectionState): string => {
  switch (state) {
    case "open":
      return "#22c55e";
    case "connecting":
      return "#f59e0b";
    case "error":
      return "#ef4444";
    case "closed":
    default:
      return "#f97316";
  }
};

export function OfflineQueuePanel({
  connectionState,
  queuedEvents,
  onUpdateEvent,
  onDeleteEvent,
  isFlushingQueue,
  lastFlushedEventCount,
}: OfflineQueuePanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const statusLabel = getStatusLabel(connectionState);
  const statusColor = getStatusColor(connectionState);
  const queuedCount = queuedEvents.length;
  const statusStyle = useMemo(
    () => ({ "--status-color": statusColor } as CSSProperties),
    [statusColor]
  );

  const replayText = useMemo(() => {
    const count = lastFlushedEventCount;
    if (count <= 0) {
      return "Replaying queued events...";
    }
    const label = count === 1 ? "event" : "events";
    return `Replaying ${count} queued ${label}...`;
  }, [lastFlushedEventCount]);

  const toggleLabel = isOpen ? "Collapse queue" : "Expand queue";

  const handleEditStart = (event: QueuedEvent) => {
    setEditingId(event.id);
    setDrafts((prev) => ({
      ...prev,
      [event.id]: serializeEventData(event.data),
    }));
  };

  const handleEditChange = (id: string, value: string) => {
    setDrafts((prev) => ({ ...prev, [id]: value }));
  };

  const handleEditCancel = (id: string) => {
    setEditingId(null);
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  const handleEditSave = (id: string) => {
    const draft = drafts[id] ?? "";
    const nextData = parseDraftData(draft);
    onUpdateEvent(id, nextData);
    handleEditCancel(id);
  };

  return (
    <>
      <div
        className="offline-queue-shell"
        style={statusStyle}
      >
        <button
          type="button"
          className="offline-queue-toggle"
          aria-expanded={isOpen}
          aria-controls="offline-queue-panel"
          aria-label={toggleLabel}
          onClick={() => setIsOpen((prev) => !prev)}
          data-testid="offline-queue-toggle"
        >
          <span className="status-dot" aria-hidden="true" />
          <span className="status-label">{statusLabel}</span>
          {queuedCount > 0 && (
            <span className="queue-count" aria-label={`${queuedCount} queued`}>
              {queuedCount}
            </span>
          )}
          <span className="toggle-icon" aria-hidden="true">
            {isOpen ? "-" : "+"}
          </span>
        </button>
        {isFlushingQueue && (
          <div className="queue-replay" role="status" aria-live="polite">
            <span className="replay-dot" aria-hidden="true" />
            <span>{replayText}</span>
          </div>
        )}
        {isOpen && (
          <div className="queue-panel" id="offline-queue-panel" role="dialog">
            <div className="queue-panel-header">
              <span>Queued actions</span>
              <span className="queue-panel-meta">{queuedCount} pending</span>
            </div>
            {queuedCount === 0 ? (
              <div className="queue-empty">No queued actions.</div>
            ) : (
              <div className="queue-list">
                {queuedEvents.map((queuedEvent) => {
                  const isEditing = editingId === queuedEvent.id;
                  const draft =
                    drafts[queuedEvent.id] ?? serializeEventData(queuedEvent.data);
                  return (
                    <div className="queue-item" key={queuedEvent.id}>
                      <div className="queue-item-header">
                        <span>{formatTimestamp(queuedEvent.timestamp)}</span>
                        {typeof queuedEvent.sequence === "number" && (
                          <span className="queue-item-seq">
                            Seq {queuedEvent.sequence}
                          </span>
                        )}
                      </div>
                      {isEditing ? (
                        <>
                          <textarea
                            className="queue-item-editor"
                            value={draft}
                            onChange={(event) =>
                              handleEditChange(queuedEvent.id, event.target.value)
                            }
                            rows={4}
                          />
                          <div className="queue-item-actions">
                            <button
                              type="button"
                              className="queue-action"
                              onClick={() => handleEditSave(queuedEvent.id)}
                            >
                              Save
                            </button>
                            <button
                              type="button"
                              className="queue-action subtle"
                              onClick={() => handleEditCancel(queuedEvent.id)}
                            >
                              Cancel
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <pre className="queue-item-body">{draft}</pre>
                          <div className="queue-item-actions">
                            <button
                              type="button"
                              className="queue-action"
                              onClick={() => handleEditStart(queuedEvent)}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              className="queue-action danger"
                              onClick={() => onDeleteEvent(queuedEvent.id)}
                            >
                              Delete
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
      <style jsx>{`
        .offline-queue-shell {
          position: fixed;
          top: 16px;
          right: 16px;
          z-index: 10005;
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 8px;
        }

        .offline-queue-toggle {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          border-radius: 999px;
          border: 1px solid rgba(148, 163, 184, 0.4);
          background: rgba(15, 23, 42, 0.9);
          color: #e2e8f0;
          font-size: 12px;
          font-weight: 600;
          letter-spacing: 0.02em;
          cursor: pointer;
          box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
          transition: border-color 150ms ease, transform 150ms ease;
        }

        .offline-queue-toggle:hover {
          border-color: var(--status-color);
          transform: translateY(-1px);
        }

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 999px;
          background: var(--status-color);
          box-shadow: 0 0 0 3px rgba(15, 23, 42, 0.9);
        }

        .status-label {
          text-transform: uppercase;
        }

        .queue-count {
          min-width: 20px;
          padding: 2px 6px;
          border-radius: 999px;
          border: 1px solid var(--status-color);
          background: rgba(15, 23, 42, 0.95);
          color: #f8fafc;
          font-size: 11px;
          font-weight: 700;
          text-align: center;
        }

        .toggle-icon {
          font-size: 12px;
          opacity: 0.7;
        }

        .queue-replay {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 12px;
          border-radius: 999px;
          background: rgba(30, 41, 59, 0.92);
          border: 1px solid rgba(148, 163, 184, 0.35);
          color: #e2e8f0;
          font-size: 11px;
        }

        .replay-dot {
          width: 6px;
          height: 6px;
          border-radius: 999px;
          background: var(--status-color);
          animation: pulse 1.4s ease-in-out infinite;
        }

        .queue-panel {
          width: 360px;
          max-height: 360px;
          overflow: hidden;
          border-radius: 16px;
          border: 1px solid rgba(148, 163, 184, 0.3);
          background: rgba(2, 6, 23, 0.95);
          box-shadow: 0 20px 30px rgba(0, 0, 0, 0.4);
          display: flex;
          flex-direction: column;
        }

        .queue-panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 14px;
          border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          color: #f8fafc;
          font-size: 13px;
          font-weight: 600;
        }

        .queue-panel-meta {
          font-size: 11px;
          color: #94a3b8;
        }

        .queue-list {
          padding: 12px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .queue-item {
          border-radius: 12px;
          border: 1px solid rgba(148, 163, 184, 0.25);
          background: rgba(15, 23, 42, 0.7);
          padding: 10px 12px;
          color: #e2e8f0;
        }

        .queue-item-header {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          color: #94a3b8;
        }

        .queue-item-seq {
          color: #a5b4fc;
        }

        .queue-item-body {
          margin: 8px 0 0;
          font-size: 12px;
          white-space: pre-wrap;
          word-break: break-word;
          max-height: 140px;
          overflow-y: auto;
        }

        .queue-item-editor {
          width: 100%;
          margin-top: 8px;
          padding: 8px;
          border-radius: 10px;
          border: 1px solid rgba(148, 163, 184, 0.35);
          background: rgba(15, 23, 42, 0.9);
          color: #e2e8f0;
          font-size: 12px;
          font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono",
            "Courier New", monospace;
          resize: vertical;
        }

        .queue-item-actions {
          margin-top: 8px;
          display: flex;
          gap: 8px;
        }

        .queue-action {
          padding: 4px 10px;
          border-radius: 999px;
          border: 1px solid rgba(148, 163, 184, 0.35);
          background: rgba(30, 41, 59, 0.9);
          color: #e2e8f0;
          font-size: 11px;
          font-weight: 600;
          cursor: pointer;
          transition: border-color 150ms ease, transform 150ms ease;
        }

        .queue-action:hover {
          border-color: var(--status-color);
          transform: translateY(-1px);
        }

        .queue-action.subtle {
          background: rgba(15, 23, 42, 0.9);
          color: #94a3b8;
        }

        .queue-action.danger {
          border-color: rgba(248, 113, 113, 0.6);
          color: #fca5a5;
          background: rgba(127, 29, 29, 0.45);
        }

        .queue-empty {
          padding: 16px;
          color: #94a3b8;
          font-size: 12px;
          text-align: center;
        }

        @keyframes pulse {
          0% {
            transform: scale(1);
            opacity: 0.6;
          }
          50% {
            transform: scale(1.5);
            opacity: 1;
          }
          100% {
            transform: scale(1);
            opacity: 0.6;
          }
        }

        @media (max-width: 640px) {
          .offline-queue-shell {
            right: 12px;
            left: 12px;
            align-items: stretch;
          }

          .queue-panel {
            width: 100%;
          }
        }
      `}</style>
    </>
  );
}
