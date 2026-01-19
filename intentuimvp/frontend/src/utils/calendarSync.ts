import type { DAGData, DAGTask } from "../state/canvasStore";

export type CalendarSyncCandidate = {
  taskId: string;
  taskTitle: string;
  summary: string;
  start: string;
  end: string;
  description?: string;
  calendarId: string;
};

export type CalendarSyncCreatedEvent = {
  task_id?: string | null;
  event_id?: string | null;
  event_url?: string | null;
  event?: Record<string, unknown> | null;
};

export type CalendarSyncApiResponse = {
  success: boolean;
  requires_confirmation?: boolean;
  message?: string | null;
  error?: string | null;
  created_events?: CalendarSyncCreatedEvent[];
  failed_events?: Array<{ task_id?: string | null; error?: string | null }>;
};

const normalizeText = (value: unknown): string | undefined => {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return undefined;
};

const serializeDagTask = (task: DAGTask): Record<string, unknown> => {
  const payload: Record<string, unknown> = {
    id: task.id,
    title: task.title,
    status: task.status,
  };

  if (task.description) payload.description = task.description;
  if (task.priority) payload.priority = task.priority;
  if (task.estimatedEffort) payload.estimated_effort = task.estimatedEffort;
  if (task.dependencies) payload.dependencies = task.dependencies;
  if (task.statusUpdatedAt) payload.status_updated_at = task.statusUpdatedAt;
  if (task.statusUpdatedBy) payload.status_updated_by = task.statusUpdatedBy;
  if (task.docCheckboxId) payload.doc_checkbox_id = task.docCheckboxId;
  if (task.docTaskId) payload.doc_task_id = task.docTaskId;
  if (task.docDocumentId) payload.doc_document_id = task.docDocumentId;
  if (task.calendarSuggestion) payload.calendar_suggestion = task.calendarSuggestion;
  if (task.calendarEventId) payload.calendar_event_id = task.calendarEventId;
  if (task.calendarEventUrl) payload.calendar_event_url = task.calendarEventUrl;

  return payload;
};

const serializeDagDependencies = (dag: DAGData): Array<Record<string, unknown>> | undefined => {
  if (!dag.dependencies || dag.dependencies.length === 0) {
    return undefined;
  }

  return dag.dependencies.map((dependency) => {
    const payload: Record<string, unknown> = {
      task_id: dependency.taskId,
      depends_on_task_id: dependency.dependsOnTaskId,
    };

    if (dependency.type) payload.dependency_type = dependency.type;

    return payload;
  });
};

export const serializeDagData = (dag: DAGData): Record<string, unknown> => {
  const payload: Record<string, unknown> = {
    tasks: dag.tasks.map(serializeDagTask),
  };

  const dependencies = serializeDagDependencies(dag);
  if (dependencies) {
    payload.dependencies = dependencies;
  }

  return payload;
};

export const mergeDagMetadata = (
  metadata: Record<string, unknown> | undefined,
  dag: DAGData
): Record<string, unknown> => {
  const nextMetadata: Record<string, unknown> = { ...(metadata ?? {}) };
  const serializedDag = serializeDagData(dag);

  nextMetadata.task_dag = serializedDag;

  if ("dagData" in nextMetadata) {
    nextMetadata.dagData = dag;
  }
  if ("dag_data" in nextMetadata) {
    nextMetadata.dag_data = serializedDag;
  }
  if ("taskDag" in nextMetadata) {
    nextMetadata.taskDag = dag;
  }
  if ("dag" in nextMetadata) {
    nextMetadata.dag = serializedDag;
  }

  return nextMetadata;
};

export const applyCalendarSyncUpdates = (
  dag: DAGData,
  createdEvents: CalendarSyncCreatedEvent[]
): DAGData => {
  if (!Array.isArray(createdEvents) || createdEvents.length === 0) {
    return dag;
  }

  const eventMap = new Map<string, { eventId?: string; eventUrl?: string }>();
  for (const event of createdEvents) {
    const taskId = normalizeText(event.task_id);
    if (!taskId) continue;
    const eventId = normalizeText(event.event_id);
    const eventUrl = normalizeText(event.event_url);
    eventMap.set(taskId, { eventId, eventUrl });
  }

  if (eventMap.size === 0) {
    return dag;
  }

  let didChange = false;
  const updatedTasks = dag.tasks.map((task) => {
    const match = eventMap.get(task.id);
    if (!match) return task;

    const nextTask: DAGTask = { ...task };
    if (match.eventId) {
      nextTask.calendarEventId = match.eventId;
    }
    if (match.eventUrl) {
      nextTask.calendarEventUrl = match.eventUrl;
    }

    if (nextTask.calendarEventId !== task.calendarEventId ||
        nextTask.calendarEventUrl !== task.calendarEventUrl) {
      didChange = true;
    }

    return nextTask;
  });

  if (!didChange) {
    return dag;
  }

  return {
    ...dag,
    tasks: updatedTasks,
  };
};

export const buildCalendarSyncPayload = (
  candidates: CalendarSyncCandidate[],
  options?: { calendarId?: string; userConfirmed?: boolean }
): Record<string, unknown> => {
  const calendarId = options?.calendarId ?? "primary";
  const userConfirmed = options?.userConfirmed ?? true;

  return {
    task_dag: {
      tasks: candidates.map((candidate) => {
        const calendarSuggestion: Record<string, unknown> = {
          summary: candidate.summary,
          start: candidate.start,
          end: candidate.end,
          calendar_id: candidate.calendarId || calendarId,
        };

        if (candidate.description) {
          calendarSuggestion.description = candidate.description;
        }

        return {
          id: candidate.taskId,
          title: candidate.taskTitle,
          calendar_suggestion: calendarSuggestion,
        };
      }),
    },
    calendar_id: calendarId,
    user_confirmed: userConfirmed,
  };
};
