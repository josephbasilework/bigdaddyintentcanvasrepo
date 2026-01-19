import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationsPanel } from "../Notifications/NotificationsPanel";
import { useNotificationsStore } from "@/state/notificationsStore";

const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

const baseNotification = {
  id: 1,
  userId: "default_user",
  level: "info",
  title: "Reminder",
  message: "Check the task",
  createdAt: new Date().toISOString(),
  readAt: null,
  dismissedAt: null,
  metadata: {},
};

describe("NotificationsPanel", () => {
  beforeEach(() => {
    useNotificationsStore.getState().reset();
    mockFetch.mockReset();
  });

  it("renders and loads notifications", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ notifications: [baseNotification], count: 1 }),
    } as Response);

    render(<NotificationsPanel />);

    expect(screen.getByText("Notifications")).toBeInTheDocument();

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/notifications")
      );
    });

    expect(screen.getByText("Reminder")).toBeInTheDocument();
  });

  it("marks notifications as read", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ notifications: [baseNotification], count: 1 }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...baseNotification, readAt: new Date().toISOString() }),
      } as Response);

    render(<NotificationsPanel />);

    await waitFor(() => {
      expect(screen.getByText("Mark read")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Mark read"));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/notifications/1"),
        expect.objectContaining({ method: "PUT" })
      );
    });
  });
});
