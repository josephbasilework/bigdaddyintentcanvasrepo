import { describe, it, expect } from "vitest";
import type { DAGData } from "../state/canvasStore";
import {
  applyCalendarSyncUpdates,
  buildCalendarSyncPayload,
  mergeDagMetadata,
  type CalendarSyncCandidate,
} from "./calendarSync";

describe("buildCalendarSyncPayload", () => {
  it("builds task DAG payload from candidates", () => {
    const candidates: CalendarSyncCandidate[] = [
      {
        taskId: "task-1",
        taskTitle: "Kickoff",
        summary: "Kickoff",
        start: "2026-01-13T10:00:00Z",
        end: "2026-01-13T11:00:00Z",
        description: "Project kickoff meeting",
        calendarId: "work",
      },
      {
        taskId: "task-2",
        taskTitle: "Design review",
        summary: "Design review",
        start: "2026-01-14T09:00:00Z",
        end: "2026-01-14T10:00:00Z",
        calendarId: "primary",
      },
    ];

    const payload = buildCalendarSyncPayload(candidates, {
      calendarId: "primary",
      userConfirmed: true,
    });

    expect(payload).toEqual({
      task_dag: {
        tasks: [
          {
            id: "task-1",
            title: "Kickoff",
            calendar_suggestion: {
              summary: "Kickoff",
              start: "2026-01-13T10:00:00Z",
              end: "2026-01-13T11:00:00Z",
              description: "Project kickoff meeting",
              calendar_id: "work",
            },
          },
          {
            id: "task-2",
            title: "Design review",
            calendar_suggestion: {
              summary: "Design review",
              start: "2026-01-14T09:00:00Z",
              end: "2026-01-14T10:00:00Z",
              calendar_id: "primary",
            },
          },
        ],
      },
      calendar_id: "primary",
      user_confirmed: true,
    });
  });
});

describe("applyCalendarSyncUpdates", () => {
  it("adds calendar event metadata for matched tasks", () => {
    const dag: DAGData = {
      tasks: [
        { id: "task-1", title: "Kickoff", status: "pending" },
        { id: "task-2", title: "Design review", status: "pending", calendarEventId: "existing" },
      ],
    };

    const updated = applyCalendarSyncUpdates(dag, [
      {
        task_id: "task-1",
        event_id: "event-123",
        event_url: "https://calendar.google.com/event?eid=event-123",
      },
      {
        task_id: "missing",
        event_id: "event-999",
      },
    ]);

    expect(updated).not.toBe(dag);
    expect(updated.tasks[0].calendarEventId).toBe("event-123");
    expect(updated.tasks[0].calendarEventUrl).toBe(
      "https://calendar.google.com/event?eid=event-123"
    );
    expect(updated.tasks[1].calendarEventId).toBe("existing");
  });
});

describe("mergeDagMetadata", () => {
  it("updates task_dag metadata while preserving other fields", () => {
    const dag: DAGData = {
      tasks: [
        {
          id: "task-1",
          title: "Kickoff",
          status: "pending",
          calendarEventId: "event-123",
          calendarEventUrl: "https://calendar.google.com/event?eid=event-123",
        },
      ],
    };

    const metadata = {
      task_dag: {
        tasks: [
          {
            id: "task-1",
            title: "Old title",
            status: "pending",
          },
        ],
      },
      dagData: {
        tasks: [
          {
            id: "task-1",
            title: "Old title",
            status: "pending",
          },
        ],
      },
      source: "planner",
    };

    const merged = mergeDagMetadata(metadata, dag);

    expect(merged.source).toBe("planner");
    expect(merged.dagData).toEqual(dag);
    expect(merged.task_dag).toEqual({
      tasks: [
        {
          id: "task-1",
          title: "Kickoff",
          status: "pending",
          calendar_event_id: "event-123",
          calendar_event_url: "https://calendar.google.com/event?eid=event-123",
        },
      ],
    });
  });
});
