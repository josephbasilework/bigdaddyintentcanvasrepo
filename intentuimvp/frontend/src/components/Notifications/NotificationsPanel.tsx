"use client";

import { useEffect, useMemo } from "react";
import { useNotificationsStore } from "@/state/notificationsStore";

type NotificationsPanelProps = {
  id?: string;
};

const formatTimestamp = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export function NotificationsPanel({ id = "notifications-panel" }: NotificationsPanelProps) {
  const {
    items,
    isLoading,
    error,
    needsRefresh,
    fetchNotifications,
    markRead,
    dismiss,
  } = useNotificationsStore();

  useEffect(() => {
    void fetchNotifications();
  }, [fetchNotifications]);

  useEffect(() => {
    if (needsRefresh) {
      void fetchNotifications();
    }
  }, [needsRefresh, fetchNotifications]);

  const unreadCount = useMemo(
    () => items.filter((item) => !item.readAt).length,
    [items]
  );

  return (
    <section className="notifications-panel" id={id} aria-live="polite">
      <header className="notifications-panel-header">
        <div>
          <div className="notifications-panel-title">Notifications</div>
          <div className="notifications-panel-subtitle">
            Reminders and system updates
          </div>
        </div>
        <div className="notifications-panel-actions">
          <span className="notifications-panel-count">
            {unreadCount} unread
          </span>
          <button
            type="button"
            onClick={() => {
              void fetchNotifications();
            }}
            className="notifications-panel-refresh"
          >
            Refresh
          </button>
        </div>
      </header>
      <div className="notifications-panel-body">
        {isLoading && <div className="notifications-state">Loading notifications...</div>}
        {error && !isLoading && <div className="notifications-error">{error}</div>}
        {!isLoading && !error && items.length === 0 && (
          <div className="notifications-state">No notifications yet.</div>
        )}
        {items.length > 0 && (
          <div className="notifications-list">
            {items.map((notification) => {
              const isUnread = !notification.readAt;
              return (
                <div
                  key={notification.id}
                  className={`notifications-card${isUnread ? " is-unread" : ""}`}
                >
                  <div className="notifications-card-header">
                    <div>
                      <div className="notifications-card-title">{notification.title}</div>
                      <div className="notifications-card-meta">
                        <span className={`notifications-level level-${notification.level}`}>
                          {notification.level}
                        </span>
                        <span>{formatTimestamp(notification.createdAt)}</span>
                        {isUnread && <span className="notifications-unread">Unread</span>}
                      </div>
                    </div>
                    <div className="notifications-card-actions">
                      {isUnread && (
                        <button
                          type="button"
                          onClick={() => markRead(notification.id)}
                        >
                          Mark read
                        </button>
                      )}
                      <button
                        type="button"
                        className="danger"
                        onClick={() => dismiss(notification.id)}
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                  <div className="notifications-card-message">{notification.message}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <style jsx>{`
        .notifications-panel {
          background: rgba(15, 23, 42, 0.95);
          border: 1px solid rgba(148, 163, 184, 0.2);
          border-radius: 12px;
          padding: 16px;
          color: #e2e8f0;
          width: min(520px, 90vw);
          margin: 12px auto 0;
        }
        .notifications-panel-header {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: center;
        }
        .notifications-panel-title {
          font-size: 16px;
          font-weight: 600;
        }
        .notifications-panel-subtitle {
          font-size: 12px;
          color: #94a3b8;
          margin-top: 4px;
        }
        .notifications-panel-actions {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 12px;
          color: #cbd5f5;
        }
        .notifications-panel-count {
          background: rgba(148, 163, 184, 0.2);
          border-radius: 999px;
          padding: 4px 10px;
        }
        .notifications-panel-refresh {
          background: transparent;
          border: 1px solid rgba(148, 163, 184, 0.3);
          border-radius: 999px;
          color: #e2e8f0;
          padding: 4px 10px;
          cursor: pointer;
          font-size: 12px;
        }
        .notifications-panel-body {
          margin-top: 12px;
        }
        .notifications-state {
          font-size: 13px;
          color: #cbd5f5;
        }
        .notifications-error {
          font-size: 13px;
          color: #fca5a5;
        }
        .notifications-list {
          display: grid;
          gap: 12px;
        }
        .notifications-card {
          background: rgba(30, 41, 59, 0.6);
          border: 1px solid rgba(148, 163, 184, 0.2);
          border-radius: 10px;
          padding: 12px;
          display: grid;
          gap: 8px;
        }
        .notifications-card.is-unread {
          border-color: rgba(125, 211, 252, 0.6);
          box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.2);
        }
        .notifications-card-header {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: flex-start;
        }
        .notifications-card-title {
          font-size: 14px;
          font-weight: 600;
        }
        .notifications-card-meta {
          display: flex;
          gap: 8px;
          align-items: center;
          font-size: 11px;
          color: #cbd5f5;
          margin-top: 4px;
        }
        .notifications-level {
          text-transform: uppercase;
          font-size: 10px;
          letter-spacing: 0.08em;
          padding: 2px 6px;
          border-radius: 999px;
          background: rgba(148, 163, 184, 0.2);
        }
        .notifications-level.level-success {
          background: rgba(74, 222, 128, 0.2);
          color: #86efac;
        }
        .notifications-level.level-warning {
          background: rgba(251, 191, 36, 0.2);
          color: #fde68a;
        }
        .notifications-unread {
          color: #38bdf8;
        }
        .notifications-card-actions {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .notifications-card-actions button {
          background: transparent;
          border: 1px solid rgba(148, 163, 184, 0.3);
          border-radius: 999px;
          color: #e2e8f0;
          padding: 4px 8px;
          font-size: 11px;
          cursor: pointer;
        }
        .notifications-card-actions button.danger {
          border-color: rgba(248, 113, 113, 0.4);
          color: #fca5a5;
        }
        .notifications-card-message {
          font-size: 13px;
          color: #e2e8f0;
          line-height: 1.4;
        }
      `}</style>
    </section>
  );
}
