"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TurnResponse } from "@/hooks/turnTypes";

type EventsViewPanelProps = {
  id?: string;
  turns: TurnResponse[];
  isLoading?: boolean;
  error?: string | null;
};

type EventActor = "user" | "system" | "job" | "external";

const ACTOR_LABELS: Record<EventActor, string> = {
  user: "User",
  system: "System",
  job: "Job",
  external: "External",
};

const DEFAULT_EVENT_TYPES = [
  "intent.parsed",
  "assumption.confirmed",
  "assumption.rejected",
  "node.created",
  "node.updated",
  "node.deleted",
  "edge.created",
  "job.started",
  "job.progress",
  "job.completed",
  "job.failed",
  "response.sent",
  "tool.invoked",
  "external.updated",
];

const JOB_TYPES = new Set(["job_started", "job_progress", "job_completed", "job_failed"]);

const EVENT_TYPE_MAP: Record<string, string> = {
  user_input: "intent.parsed",
  agent_response: "response.sent",
  system_message: "response.sent",
  assumption_presented: "assumption.presented",
  assumption_confirmed: "assumption.confirmed",
  assumption_rejected: "assumption.rejected",
  assumption_modified: "assumption.modified",
  node_created: "node.created",
  node_updated: "node.updated",
  node_deleted: "node.deleted",
  edge_created: "edge.created",
  edge_updated: "edge.updated",
  edge_deleted: "edge.deleted",
  job_started: "job.started",
  job_progress: "job.progress",
  job_completed: "job.completed",
  job_failed: "job.failed",
  mcp_tool_invoked: "tool.invoked",
  mcp_tool_result: "tool.result",
  external_state_change: "external.updated",
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

const normalizeId = (value: unknown): string | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  return null;
};

const extractId = (payload: Record<string, unknown>, keys: string[]): string | null => {
  for (const key of keys) {
    if (!Object.prototype.hasOwnProperty.call(payload, key)) {
      continue;
    }
    const normalized = normalizeId(payload[key]);
    if (normalized) {
      return normalized;
    }
  }
  return null;
};

const extractNestedId = (payload: Record<string, unknown>, key: string): string | null => {
  const nested = payload[key];
  if (!nested || typeof nested !== "object") {
    return null;
  }
  const record = nested as Record<string, unknown>;
  return extractId(record, ["id", "node_id", "nodeId", "edge_id", "edgeId"]);
};

const resolveNodeScopeId = (turn: TurnResponse): string | null => {
  if (turn.relatedNodeId !== null) {
    return String(turn.relatedNodeId);
  }
  const payload = turn.payload ?? {};
  return extractId(payload, ["node_id", "nodeId"]) ?? extractNestedId(payload, "node");
};

const resolveEntity = (
  turn: TurnResponse
): { label: string; id: string } | null => {
  if (turn.relatedNodeId !== null) {
    return { label: "node", id: String(turn.relatedNodeId) };
  }
  if (turn.relatedEdgeId !== null) {
    return { label: "edge", id: String(turn.relatedEdgeId) };
  }
  const payload = turn.payload ?? {};
  const nodeId = extractId(payload, ["node_id", "nodeId"]) ?? extractNestedId(payload, "node");
  if (nodeId) {
    return { label: "node", id: nodeId };
  }
  const edgeId = extractId(payload, ["edge_id", "edgeId"]) ?? extractNestedId(payload, "edge");
  if (edgeId) {
    return { label: "edge", id: edgeId };
  }
  const jobId = extractId(payload, ["job_id", "jobId"]);
  if (jobId) {
    return { label: "job", id: jobId };
  }
  const runId = extractId(payload, ["run_id", "runId"]);
  if (runId) {
    return { label: "run", id: runId };
  }
  const toolId =
    extractId(payload, ["tool_id", "toolId", "tool", "tool_name", "toolName"]) ??
    extractNestedId(payload, "tool");
  if (toolId) {
    return { label: "tool", id: toolId };
  }
  return null;
};

const extractPayloadText = (payload: Record<string, unknown>): string | null => {
  if (typeof payload.title === "string" && typeof payload.message === "string") {
    return `${payload.title}: ${payload.message}`;
  }
  const candidates = [
    payload.message,
    payload.status,
    payload.error,
    payload.prompt,
    payload.text,
    payload.content,
    payload.result,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === "string") {
      return candidate;
    }
  }
  if (payload.result && typeof payload.result === "object") {
    const nested = extractPayloadText(payload.result as Record<string, unknown>);
    if (nested) {
      return nested;
    }
  }
  return null;
};

const buildSummary = (turn: TurnResponse): string => {
  const payload = turn.payload ?? {};
  if (turn.type === "user_input" && typeof payload.command === "string") {
    return payload.command;
  }
  const payloadText = extractPayloadText(payload);
  if (payloadText) {
    return payloadText;
  }
  return turn.summary;
};

const getEventType = (turn: TurnResponse): string => {
  return EVENT_TYPE_MAP[turn.type] ?? turn.type.replace(/_/g, ".");
};

const getActorGroup = (turn: TurnResponse): EventActor => {
  if (JOB_TYPES.has(turn.type)) {
    return "job";
  }
  if (turn.actor === "user") {
    return "user";
  }
  if (turn.actor === "mcp") {
    return "external";
  }
  return "system";
};

const getBadgeTone = (eventType: string): string => {
  if (eventType.startsWith("intent.")) return "intent";
  if (eventType.startsWith("assumption.")) return "assumption";
  if (eventType.startsWith("node.") || eventType.startsWith("edge.")) return "canvas";
  if (eventType.startsWith("job.")) return "job";
  if (eventType.startsWith("response.")) return "response";
  if (eventType.startsWith("tool.")) return "tool";
  if (eventType.startsWith("external.")) return "external";
  return "neutral";
};

export function EventsViewPanel({
  id = "events-view-panel",
  turns,
  isLoading = false,
  error = null,
}: EventsViewPanelProps) {
  const [actorFilters, setActorFilters] = useState<EventActor[]>([
    "user",
    "system",
    "job",
    "external",
  ]);
  const [typeFilters, setTypeFilters] = useState<string[]>([]);
  const [nodeFilter, setNodeFilter] = useState("");
  const [expandedEventIds, setExpandedEventIds] = useState<Set<number>>(
    () => new Set()
  );
  const prevTypeOptionsRef = useRef<string[]>([]);

  const eventRows = useMemo(
    () =>
      turns.map((turn) => {
        const eventType = getEventType(turn);
        const actor = getActorGroup(turn);
        const entity = resolveEntity(turn);
        return {
          id: turn.id,
          turn,
          eventType,
          actor,
          entity,
          nodeScopeId: resolveNodeScopeId(turn),
          summary: buildSummary(turn),
        };
      }),
    [turns]
  );

  const orderedEvents = useMemo(() => {
    const copy = [...eventRows];
    return copy.sort((a, b) => {
      const aTime = Date.parse(a.turn.timestamp) || 0;
      const bTime = Date.parse(b.turn.timestamp) || 0;
      return bTime - aTime;
    });
  }, [eventRows]);

  const eventTypeOptions = useMemo(() => {
    const set = new Set<string>(DEFAULT_EVENT_TYPES);
    for (const row of eventRows) {
      set.add(row.eventType);
    }
    const options = Array.from(set);
    return options.sort((a, b) => a.localeCompare(b));
  }, [eventRows]);

  const nodeOptions = useMemo(() => {
    const set = new Set<string>();
    for (const row of eventRows) {
      if (row.nodeScopeId) {
        set.add(row.nodeScopeId);
      }
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [eventRows]);

  useEffect(() => {
    setTypeFilters((prev) => {
      if (eventTypeOptions.length === 0) {
        return [];
      }
      if (prev.length === 0) {
        return eventTypeOptions;
      }
      const wasAll =
        prevTypeOptionsRef.current.length > 0 &&
        prev.length === prevTypeOptionsRef.current.length;
      const filtered = prev.filter((type) => eventTypeOptions.includes(type));
      if (wasAll) {
        return eventTypeOptions;
      }
      return filtered.length > 0 ? filtered : eventTypeOptions;
    });
    prevTypeOptionsRef.current = eventTypeOptions;
  }, [eventTypeOptions]);

  const activeTypeFilters = typeFilters.length > 0 ? typeFilters : eventTypeOptions;

  const filteredEvents = useMemo(() => {
    const actorSet = new Set(actorFilters);
    const typeSet = new Set(activeTypeFilters);
    const normalizedNode = nodeFilter.trim();
    return orderedEvents.filter((row) => {
      if (!actorSet.has(row.actor)) {
        return false;
      }
      if (activeTypeFilters.length > 0 && !typeSet.has(row.eventType)) {
        return false;
      }
      if (normalizedNode) {
        return row.nodeScopeId === normalizedNode;
      }
      return true;
    });
  }, [actorFilters, activeTypeFilters, nodeFilter, orderedEvents]);

  const toggleExpanded = useCallback((eventId: number) => {
    setExpandedEventIds((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) {
        next.delete(eventId);
      } else {
        next.add(eventId);
      }
      return next;
    });
  }, []);

  return (
    <section className="events-panel" aria-live="polite" aria-busy={isLoading} id={id}>
      <header className="events-panel-header">
        <div>
          <div className="events-panel-title">Events View</div>
          <div className="events-panel-subtitle">
            {turns.length === 0
              ? "No events yet"
              : `${turns.length} event${turns.length === 1 ? "" : "s"}`}
          </div>
        </div>
        <div className="events-panel-status">
          {filteredEvents.length} shown
        </div>
      </header>
      <div className="events-panel-controls">
        <div className="events-filter-group">
          <div className="events-filter-label">Actors</div>
          <div className="events-filter-chips" role="group" aria-label="Actor filters">
            {(["user", "system", "job", "external"] as EventActor[]).map((actor) => {
              const isActive = actorFilters.includes(actor);
              return (
                <button
                  key={actor}
                  type="button"
                  className={`events-filter-chip${isActive ? " is-active" : ""}`}
                  onClick={() => {
                    setActorFilters((prev) => {
                      if (prev.includes(actor)) {
                        return prev.filter((item) => item !== actor);
                      }
                      return [...prev, actor];
                    });
                  }}
                  aria-pressed={isActive}
                >
                  {ACTOR_LABELS[actor]}
                </button>
              );
            })}
          </div>
        </div>
        <div className="events-filter-group">
          <label className="events-filter-label" htmlFor="events-type-filter">
            Event types
          </label>
          <select
            id="events-type-filter"
            className="events-filter-select"
            multiple
            size={Math.min(6, Math.max(eventTypeOptions.length, 3))}
            value={activeTypeFilters}
            onChange={(event) => {
              const selected = Array.from(event.target.selectedOptions).map(
                (option) => option.value
              );
              setTypeFilters(selected.length > 0 ? selected : eventTypeOptions);
            }}
            aria-label="Event type filter"
          >
            {eventTypeOptions.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="events-filter-reset"
            onClick={() => {
              setTypeFilters(eventTypeOptions);
            }}
          >
            All types
          </button>
        </div>
        <div className="events-filter-group">
          <label className="events-filter-label" htmlFor="events-node-filter">
            Node scope
          </label>
          <input
            id="events-node-filter"
            className="events-filter-input"
            list="events-node-options"
            placeholder="Node ID"
            value={nodeFilter}
            onChange={(event) => setNodeFilter(event.target.value)}
          />
          <datalist id="events-node-options">
            {nodeOptions.map((nodeId) => (
              <option key={nodeId} value={nodeId} />
            ))}
          </datalist>
          <button
            type="button"
            className="events-filter-reset"
            onClick={() => setNodeFilter("")}
          >
            Clear
          </button>
        </div>
        <button
          type="button"
          className="events-filter-reset"
          onClick={() => {
            setActorFilters(["user", "system", "job", "external"]);
            setTypeFilters(eventTypeOptions);
            setNodeFilter("");
          }}
        >
          Reset filters
        </button>
      </div>
      <div className="events-panel-body" role="log" aria-live="polite">
        {isLoading && <div className="events-panel-state">Loading events...</div>}
        {error && !isLoading && <div className="events-panel-error">{error}</div>}
        {!isLoading && !error && filteredEvents.length === 0 && (
          <div className="events-panel-state">No events match these filters.</div>
        )}
        {!isLoading && !error && filteredEvents.length > 0 && (
          <div className="events-table" role="list">
            <div className="events-header-row" role="listitem" aria-hidden="true">
              <div className="events-cell events-cell-type">Event</div>
              <div className="events-cell events-cell-actor">Actor</div>
              <div className="events-cell events-cell-entity">Entity</div>
              <div className="events-cell events-cell-time">Timestamp</div>
              <div className="events-cell events-cell-action">Details</div>
            </div>
            {filteredEvents.map((row) => {
              const isExpanded = expandedEventIds.has(row.id);
              const payload = row.turn.payload ?? {};
              const payloadText =
                payload && Object.keys(payload).length > 0
                  ? JSON.stringify(payload, null, 2)
                  : null;
              const badgeTone = getBadgeTone(row.eventType);
              const entityLabel = row.entity ? `${row.entity.label}:${row.entity.id}` : "--";

              return (
                <div key={row.id} className="events-row" role="listitem">
                  <div className="events-row-main">
                    <div className="events-cell events-cell-type">
                      <span className={`events-badge tone-${badgeTone}`}>
                        {row.eventType}
                      </span>
                      <div className="events-summary">{row.summary}</div>
                    </div>
                    <div className="events-cell events-cell-actor">
                      {ACTOR_LABELS[row.actor]}
                    </div>
                    <div className="events-cell events-cell-entity">{entityLabel}</div>
                    <div className="events-cell events-cell-time">
                      {formatTimestamp(row.turn.timestamp)}
                    </div>
                    <div className="events-cell events-cell-action">
                      <button
                        type="button"
                        className="events-detail-toggle"
                        onClick={() => toggleExpanded(row.id)}
                        aria-expanded={isExpanded}
                        aria-controls={`event-details-${row.id}`}
                        aria-label={`Toggle details for ${row.eventType} event ${row.turn.sequenceNumber}`}
                      >
                        {isExpanded ? "Hide" : "Details"}
                      </button>
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="events-row-details" id={`event-details-${row.id}`}>
                      <div className="events-detail-grid">
                        <div className="events-detail">
                          <div className="events-detail-label">Session</div>
                          <div className="events-detail-value">{row.turn.sessionId}</div>
                        </div>
                        <div className="events-detail">
                          <div className="events-detail-label">Sequence</div>
                          <div className="events-detail-value">#{row.turn.sequenceNumber}</div>
                        </div>
                        <div className="events-detail">
                          <div className="events-detail-label">Actor</div>
                          <div className="events-detail-value">{row.turn.actor}</div>
                        </div>
                        <div className="events-detail">
                          <div className="events-detail-label">Turn type</div>
                          <div className="events-detail-value">{row.turn.type}</div>
                        </div>
                      </div>
                      <div className="events-detail-block">
                        <div className="events-detail-label">Payload</div>
                        {payloadText ? (
                          <pre className="events-detail-payload">{payloadText}</pre>
                        ) : (
                          <div className="events-detail-empty">No payload recorded.</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
      <style jsx>{`
        .events-panel {
          border-radius: 0.9rem;
          border: 1px solid #1f2937;
          background: linear-gradient(180deg, #0f172a 0%, #0b1120 100%);
          color: #e2e8f0;
          box-shadow: 0 18px 42px rgba(0, 0, 0, 0.45);
          overflow: hidden;
        }

        .events-panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 1rem;
          padding: 0.85rem 1rem 0.75rem;
          border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.85);
        }

        .events-panel-title {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.18em;
          color: #94a3b8;
        }

        .events-panel-subtitle {
          font-size: 0.9rem;
          color: #e2e8f0;
          margin-top: 0.2rem;
        }

        .events-panel-status {
          font-size: 0.75rem;
          color: #94a3b8;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }

        .events-panel-controls {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 0.8rem 1rem;
          padding: 0.75rem 1rem;
          border-bottom: 1px solid rgba(148, 163, 184, 0.15);
          background: rgba(15, 23, 42, 0.6);
        }

        .events-filter-group {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          flex-wrap: wrap;
        }

        .events-filter-label {
          font-size: 0.65rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: #94a3b8;
        }

        .events-filter-chips {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          flex-wrap: wrap;
        }

        .events-filter-chip {
          border-radius: 999px;
          border: 1px solid rgba(71, 85, 105, 0.6);
          background: rgba(15, 23, 42, 0.85);
          color: #cbd5f5;
          font-size: 0.7rem;
          padding: 0.25rem 0.65rem;
          cursor: pointer;
          letter-spacing: 0.04em;
          text-transform: uppercase;
        }

        .events-filter-chip.is-active {
          border-color: rgba(56, 189, 248, 0.6);
          color: #e0f2fe;
          box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.25);
        }

        .events-filter-select {
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid rgba(71, 85, 105, 0.6);
          color: #e2e8f0;
          border-radius: 0.6rem;
          padding: 0.35rem 0.6rem;
          font-size: 0.75rem;
          min-width: 180px;
        }

        .events-filter-input {
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid rgba(71, 85, 105, 0.6);
          color: #e2e8f0;
          border-radius: 0.6rem;
          padding: 0.35rem 0.6rem;
          font-size: 0.75rem;
          min-width: 120px;
        }

        .events-filter-reset {
          border: 1px solid rgba(71, 85, 105, 0.6);
          background: transparent;
          color: #94a3b8;
          font-size: 0.7rem;
          padding: 0.35rem 0.6rem;
          border-radius: 0.6rem;
          cursor: pointer;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }

        .events-panel-body {
          padding: 0.85rem 1rem 1rem;
          max-height: min(60vh, 520px);
          overflow-y: auto;
        }

        .events-panel-state {
          font-size: 0.85rem;
          color: #94a3b8;
        }

        .events-panel-error {
          font-size: 0.85rem;
          color: #fca5a5;
          background: rgba(127, 29, 29, 0.35);
          border: 1px solid rgba(239, 68, 68, 0.4);
          padding: 0.5rem 0.65rem;
          border-radius: 0.5rem;
        }

        .events-table {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .events-header-row,
        .events-row-main {
          display: grid;
          grid-template-columns: minmax(180px, 1.4fr) 0.6fr 0.7fr 0.7fr auto;
          gap: 0.75rem;
          align-items: center;
        }

        .events-header-row {
          font-size: 0.65rem;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: #94a3b8;
          padding: 0 0.25rem;
        }

        .events-row {
          border-radius: 0.85rem;
          border: 1px solid rgba(30, 41, 59, 0.7);
          background: rgba(15, 23, 42, 0.65);
          padding: 0.65rem 0.75rem;
        }

        .events-cell {
          font-size: 0.75rem;
        }

        .events-cell-type {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
        }

        .events-badge {
          display: inline-flex;
          align-items: center;
          width: fit-content;
          padding: 0.15rem 0.5rem;
          border-radius: 999px;
          font-size: 0.6rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          border: 1px solid rgba(148, 163, 184, 0.35);
        }

        .events-badge.tone-intent {
          color: #38bdf8;
          border-color: rgba(56, 189, 248, 0.45);
        }

        .events-badge.tone-assumption {
          color: #fbbf24;
          border-color: rgba(251, 191, 36, 0.45);
        }

        .events-badge.tone-canvas {
          color: #34d399;
          border-color: rgba(52, 211, 153, 0.45);
        }

        .events-badge.tone-job {
          color: #f97316;
          border-color: rgba(249, 115, 22, 0.45);
        }

        .events-badge.tone-response {
          color: #fca5a5;
          border-color: rgba(248, 113, 113, 0.45);
        }

        .events-badge.tone-tool {
          color: #22d3ee;
          border-color: rgba(34, 211, 238, 0.45);
        }

        .events-badge.tone-external {
          color: #a3e635;
          border-color: rgba(163, 230, 53, 0.45);
        }

        .events-badge.tone-neutral {
          color: #cbd5f5;
          border-color: rgba(148, 163, 184, 0.35);
        }

        .events-summary {
          font-size: 0.85rem;
          color: #e2e8f0;
          line-height: 1.45;
        }

        .events-cell-entity {
          font-variant-numeric: tabular-nums;
          color: #cbd5f5;
        }

        .events-cell-time {
          font-variant-numeric: tabular-nums;
          color: #94a3b8;
        }

        .events-detail-toggle {
          border: 1px solid rgba(71, 85, 105, 0.6);
          background: rgba(15, 23, 42, 0.6);
          color: #e2e8f0;
          border-radius: 0.6rem;
          font-size: 0.7rem;
          padding: 0.3rem 0.65rem;
          cursor: pointer;
          height: fit-content;
        }

        .events-row-details {
          margin-top: 0.7rem;
          border-top: 1px solid rgba(148, 163, 184, 0.2);
          padding-top: 0.7rem;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .events-detail-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
          gap: 0.6rem;
        }

        .events-detail {
          display: flex;
          flex-direction: column;
          gap: 0.2rem;
          font-size: 0.75rem;
        }

        .events-detail-label {
          text-transform: uppercase;
          letter-spacing: 0.1em;
          font-size: 0.6rem;
          color: #94a3b8;
        }

        .events-detail-value {
          color: #e2e8f0;
          word-break: break-word;
        }

        .events-detail-block {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
          font-size: 0.8rem;
        }

        .events-detail-payload {
          background: rgba(2, 6, 23, 0.8);
          border-radius: 0.6rem;
          padding: 0.6rem 0.75rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
          font-size: 0.75rem;
          color: #e2e8f0;
          overflow-x: auto;
          white-space: pre-wrap;
        }

        .events-detail-empty {
          font-size: 0.75rem;
          color: #94a3b8;
        }

        @media (max-width: 720px) {
          .events-panel-header {
            flex-direction: column;
            align-items: flex-start;
          }

          .events-panel-controls {
            align-items: flex-start;
          }

          .events-header-row,
          .events-row-main {
            grid-template-columns: 1fr;
            gap: 0.4rem;
          }

          .events-cell-action {
            display: flex;
            justify-content: flex-start;
          }
        }
      `}</style>
    </section>
  );
}
