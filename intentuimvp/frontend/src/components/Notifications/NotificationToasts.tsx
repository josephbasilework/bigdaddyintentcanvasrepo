"use client";

import { useEffect, useRef } from "react";
import { useNotificationsStore } from "@/state/notificationsStore";

const DEFAULT_DURATION_MS = 6000;

export function NotificationToasts() {
  const { toasts, removeToast } = useNotificationsStore();
  const timersRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    const timers = timersRef.current;
    toasts.forEach((toast) => {
      if (timers.has(toast.id)) {
        return;
      }
      const duration = toast.durationMs ?? DEFAULT_DURATION_MS;
      if (duration === 0) {
        return;
      }
      const timeout = window.setTimeout(() => {
        removeToast(toast.id);
      }, duration);
      timers.set(toast.id, timeout);
    });

    timers.forEach((timeout, id) => {
      if (!toasts.some((toast) => toast.id === id)) {
        window.clearTimeout(timeout);
        timers.delete(id);
      }
    });
    return () => {
      timers.forEach((timeout) => window.clearTimeout(timeout));
      timers.clear();
    };
  }, [toasts, removeToast]);

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div className="notification-toast-stack" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`notification-toast level-${toast.level}`}>
          <div className="toast-header">
            <span className="toast-title">{toast.title}</span>
            <button
              type="button"
            className="toast-close"
            onClick={() => removeToast(toast.id)}
            aria-label="Dismiss notification"
          >
            x
          </button>
          </div>
          {toast.message && <div className="toast-message">{toast.message}</div>}
        </div>
      ))}
      <style jsx>{`
        .notification-toast-stack {
          position: fixed;
          top: 20px;
          right: 20px;
          display: grid;
          gap: 10px;
          z-index: 10050;
          width: min(320px, 90vw);
        }
        .notification-toast {
          background: rgba(15, 23, 42, 0.95);
          border: 1px solid rgba(148, 163, 184, 0.3);
          border-radius: 10px;
          padding: 12px 14px;
          color: #e2e8f0;
          box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4);
        }
        .notification-toast.level-success {
          border-color: rgba(74, 222, 128, 0.5);
        }
        .notification-toast.level-warning {
          border-color: rgba(251, 191, 36, 0.5);
        }
        .toast-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 10px;
        }
        .toast-title {
          font-size: 13px;
          font-weight: 600;
        }
        .toast-close {
          border: none;
          background: transparent;
          color: #94a3b8;
          font-size: 16px;
          cursor: pointer;
        }
        .toast-message {
          margin-top: 6px;
          font-size: 12px;
          color: #cbd5f5;
          line-height: 1.4;
        }
      `}</style>
    </div>
  );
}
