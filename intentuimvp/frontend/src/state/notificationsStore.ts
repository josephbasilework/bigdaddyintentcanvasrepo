import { create } from "zustand";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SESSION_ID_STORAGE_KEY = "intentui_workspace_session_id";

export type NotificationLevel = "info" | "success" | "warning";

export interface NotificationItem {
  id: number;
  userId: string;
  workspaceId?: number | null;
  sessionId?: string | null;
  source?: string | null;
  level: NotificationLevel;
  title: string;
  message: string;
  createdAt: string;
  readAt?: string | null;
  dismissedAt?: string | null;
  relatedNodeId?: number | null;
  relatedEdgeId?: number | null;
  metadata?: Record<string, unknown> | null;
}

export interface NotificationToast {
  id: string;
  level: NotificationLevel;
  title: string;
  message: string;
  durationMs: number | null;
  receivedAt: string;
}

interface NotificationsState {
  items: NotificationItem[];
  toasts: NotificationToast[];
  isLoading: boolean;
  error: string | null;
  needsRefresh: boolean;
  fetchNotifications: (options?: { includeDismissed?: boolean }) => Promise<void>;
  markRead: (id: number) => Promise<void>;
  dismiss: (id: number) => Promise<void>;
  enqueueToastFromPayload: (payload: Record<string, unknown>) => void;
  enqueueToast: (toast: Omit<NotificationToast, "id" | "receivedAt">) => void;
  removeToast: (id: string) => void;
  reset: () => void;
}

const createToastId = (): string => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `toast-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

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

const coerceLevel = (value: unknown): NotificationLevel => {
  if (value === "success" || value === "warning") {
    return value;
  }
  return "info";
};

const extractToastDuration = (payload: Record<string, unknown>): number | null => {
  const duration = payload.duration;
  if (typeof duration === "number" && Number.isFinite(duration)) {
    return Math.max(0, Math.round(duration));
  }
  return null;
};

const normalizeNotifications = (value: unknown): NotificationItem[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is NotificationItem => {
    if (!item || typeof item !== "object") {
      return false;
    }
    return typeof (item as NotificationItem).id === "number";
  });
};

const initialState = {
  items: [],
  toasts: [],
  isLoading: false,
  error: null,
  needsRefresh: false,
};

export const useNotificationsStore = create<NotificationsState>((set, get) => ({
  ...initialState,
  fetchNotifications: async (options) => {
    if (get().isLoading) return;
    set({ isLoading: true, error: null });
    const params = new URLSearchParams();
    const sessionId = getSessionId();
    if (sessionId) {
      params.set("sessionId", sessionId);
    }
    if (options?.includeDismissed) {
      params.set("includeDismissed", "true");
    }
    const url = `${API_BASE_URL}/api/notifications${
      params.toString() ? `?${params.toString()}` : ""
    }`;
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to load notifications (${response.status})`);
      }
      const data = await response.json();
      const items = normalizeNotifications(data.notifications);
      set({ items, isLoading: false, needsRefresh: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to load notifications.",
        isLoading: false,
      });
    }
  },
  markRead: async (id) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/notifications/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ read: true }),
      });
      if (!response.ok) {
        throw new Error(`Failed to update notification (${response.status})`);
      }
      const data = await response.json();
      set((state) => ({
        items: state.items.map((item) => (item.id === id ? data : item)),
        error: null,
      }));
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to update notification.",
      });
    }
  },
  dismiss: async (id) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/notifications/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dismissed: true }),
      });
      if (!response.ok) {
        throw new Error(`Failed to dismiss notification (${response.status})`);
      }
      const data = await response.json();
      set((state) => ({
        items: state.items.filter((item) => item.id !== data.id),
        error: null,
      }));
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to dismiss notification.",
      });
    }
  },
  enqueueToastFromPayload: (payload) => {
    const title = typeof payload.title === "string" ? payload.title : "Notification";
    const message = typeof payload.message === "string" ? payload.message : "";
    if (title === "Heartbeat") {
      return;
    }
    if (!message && title === "Notification") {
      return;
    }
    const toast: NotificationToast = {
      id: createToastId(),
      level: coerceLevel(payload.level),
      title,
      message,
      durationMs: extractToastDuration(payload),
      receivedAt: new Date().toISOString(),
    };
    set((state) => ({
      toasts: [...state.toasts, toast],
      needsRefresh: true,
    }));
  },
  enqueueToast: (toast) => {
    set((state) => ({
      toasts: [
        ...state.toasts,
        {
          id: createToastId(),
          receivedAt: new Date().toISOString(),
          ...toast,
        },
      ],
    }));
  },
  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((toast) => toast.id !== id),
    }));
  },
  reset: () => {
    set({ ...initialState });
  },
}));
