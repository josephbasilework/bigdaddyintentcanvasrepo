"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type UIEvent,
} from "react";
import {
  getResponseType,
  getResponseTypeLabel,
  type TurnResponse,
} from "@/hooks/turnTypes";
import { useCanvasStore, type CanvasNode } from "@/state/canvasStore";
import { ReferenceText } from "@/components/References/ReferenceText";

type WheelViewPanelProps = {
  id?: string;
  turns: TurnResponse[];
  isLoading?: boolean;
  error?: string | null;
};

type ActorGroup = "user" | "system" | "job";
type TurnCategory = "input" | "response" | "proposal" | "crud" | "other";

const ACTOR_GROUPS: ActorGroup[] = ["user", "system", "job"];
const ACTOR_LABELS: Record<ActorGroup, string> = {
  user: "User",
  system: "System",
  job: "Job",
};
const ACTOR_SHORT: Record<ActorGroup, string> = {
  user: "U",
  system: "S",
  job: "J",
};

const CATEGORY_LABELS: Record<TurnCategory, string> = {
  input: "Input",
  response: "Response",
  proposal: "Proposal",
  crud: "CRUD",
  other: "Other",
};

const INPUT_TYPES = new Set(["user_input", "user_canvas_action"]);
const CRUD_TYPES = new Set([
  "node_created",
  "node_updated",
  "node_deleted",
  "edge_created",
  "edge_updated",
  "edge_deleted",
]);
const JOB_TYPES = new Set(["job_started", "job_progress", "job_completed", "job_failed"]);
const PROPOSAL_TYPES = new Set(["assumption_presented"]);
const RESPONSE_TYPES = new Set([
  "agent_response",
  "system_message",
  "assumption_confirmed",
  "assumption_rejected",
  "assumption_modified",
  "mcp_tool_result",
  "mcp_tool_invoked",
  "external_state_change",
]);

const COLLAPSED_ROW_HEIGHT = 96;
const EXPANDED_ROW_HEIGHT = 240;
const OVERSCAN_PX = 280;

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
    const resultPayload = payload.result as Record<string, unknown>;
    const nested = extractPayloadText(resultPayload);
    if (nested) {
      return nested;
    }
  }
  return null;
};

const extractRationale = (payload: Record<string, unknown>): string | null => {
  const candidates = [
    payload.reasoning,
    payload.rationale,
    payload.confidence_rationale,
    payload.analysis,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      return candidate;
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

const getActorGroup = (turn: TurnResponse): ActorGroup => {
  if (JOB_TYPES.has(turn.type)) {
    return "job";
  }
  if (turn.actor === "user") {
    return "user";
  }
  return "system";
};

const getCategory = (turn: TurnResponse): TurnCategory => {
  const responseType = getResponseType(turn);
  if (responseType === "proposal") {
    return "proposal";
  }
  if (responseType) {
    return "response";
  }
  if (CRUD_TYPES.has(turn.type)) {
    return "crud";
  }
  if (INPUT_TYPES.has(turn.type)) {
    return "input";
  }
  if (PROPOSAL_TYPES.has(turn.type)) {
    return "proposal";
  }
  if (RESPONSE_TYPES.has(turn.type)) {
    return "response";
  }
  return "other";
};

type TurnRowProps = {
  turn: TurnResponse;
  actorGroup: ActorGroup;
  category: TurnCategory;
  turnIdBySequence: Map<number, number>;
  nodes: CanvasNode[];
  isExpanded: boolean;
  onToggle: () => void;
  onLink: () => void;
  onHeightChange: (id: number, height: number) => void;
};

const TurnRow = ({
  turn,
  actorGroup,
  category,
  turnIdBySequence,
  nodes,
  isExpanded,
  onToggle,
  onLink,
  onHeightChange,
}: TurnRowProps) => {
  const rowRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = rowRef.current;
    if (!element) {
      return;
    }
    const updateHeight = () => {
      onHeightChange(turn.id, element.getBoundingClientRect().height);
    };
    updateHeight();
    if (typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(() => updateHeight());
    observer.observe(element);
    return () => observer.disconnect();
  }, [onHeightChange, turn.id, isExpanded]);

  const payload = turn.payload ?? {};
  const rationale = extractRationale(payload);
  const payloadText = extractPayloadText(payload);
  const formattedPayload =
    payload && Object.keys(payload).length > 0 ? JSON.stringify(payload, null, 2) : null;
  const responseType = getResponseType(turn);
  const responseLabel = responseType ? getResponseTypeLabel(responseType) : null;

  return (
    <div
      ref={rowRef}
      className={`wheel-turn is-${actorGroup}${
        responseType ? ` response-${responseType}` : ""
      }${isExpanded ? " is-expanded" : ""}`}
      id={`turn-${turn.id}`}
    >
      <div className="wheel-turn-header">
        <div className="wheel-turn-marker">
          <span className={`wheel-turn-icon icon-${actorGroup}`} aria-hidden="true">
            {ACTOR_SHORT[actorGroup]}
          </span>
          <button
            type="button"
            className="wheel-turn-link"
            onClick={onLink}
            aria-label={`Jump to turn ${turn.sequenceNumber}`}
          >
            #{turn.sequenceNumber}
          </button>
        </div>
        <div className="wheel-turn-main">
          <div className="wheel-turn-meta">
            <span className="wheel-turn-actor">{ACTOR_LABELS[actorGroup]}</span>
            <span className={`wheel-turn-tag tag-${category}`}>
              {CATEGORY_LABELS[category]}
            </span>
            {responseType && (
              <span className={`wheel-turn-tag response-${responseType}`}>
                {responseLabel}
              </span>
            )}
            <span className="wheel-turn-type">{turn.type}</span>
            <time className="wheel-turn-time">{formatTimestamp(turn.timestamp)}</time>
          </div>
          <div className="wheel-turn-summary">
            <ReferenceText
              text={buildSummary(turn)}
              turnIdBySequence={turnIdBySequence}
              nodes={nodes}
            />
          </div>
        </div>
        <button
          type="button"
          className="wheel-turn-toggle"
          onClick={onToggle}
          aria-expanded={isExpanded}
          aria-controls={`turn-details-${turn.id}`}
        >
          {isExpanded ? "Hide" : "Details"}
        </button>
      </div>
      {isExpanded && (
        <div className="wheel-turn-details" id={`turn-details-${turn.id}`}>
          <div className="wheel-detail-grid">
            <div className="wheel-detail">
              <div className="wheel-detail-label">Session</div>
              <div className="wheel-detail-value">{turn.sessionId}</div>
            </div>
            <div className="wheel-detail">
              <div className="wheel-detail-label">Actor</div>
              <div className="wheel-detail-value">{turn.actor}</div>
            </div>
            <div className="wheel-detail">
              <div className="wheel-detail-label">Response type</div>
              <div className="wheel-detail-value">
                {responseLabel ?? "None"}
              </div>
            </div>
            <div className="wheel-detail">
              <div className="wheel-detail-label">Related node</div>
              <div className="wheel-detail-value">
                {turn.relatedNodeId ?? "None"}
              </div>
            </div>
            <div className="wheel-detail">
              <div className="wheel-detail-label">Related edge</div>
              <div className="wheel-detail-value">
                {turn.relatedEdgeId ?? "None"}
              </div>
            </div>
          </div>
          {payloadText && payloadText !== turn.summary && (
            <div className="wheel-detail-block">
              <div className="wheel-detail-label">Payload summary</div>
              <div className="wheel-detail-text">
                <ReferenceText
                  text={payloadText}
                  turnIdBySequence={turnIdBySequence}
                  nodes={nodes}
                />
              </div>
            </div>
          )}
          {rationale && (
            <div className="wheel-detail-block">
              <div className="wheel-detail-label">Rationale</div>
              <div className="wheel-detail-text">
                <ReferenceText
                  text={rationale}
                  turnIdBySequence={turnIdBySequence}
                  nodes={nodes}
                />
              </div>
            </div>
          )}
          <div className="wheel-detail-block">
            <div className="wheel-detail-label">Payload</div>
            {formattedPayload ? (
              <pre className="wheel-detail-payload">{formattedPayload}</pre>
            ) : (
              <div className="wheel-detail-empty">No payload recorded.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export function WheelViewPanel({
  id = "wheel-view-panel",
  turns,
  isLoading = false,
  error = null,
}: WheelViewPanelProps) {
  const nodes = useCanvasStore((state) => state.nodes);
  const [actorFilters, setActorFilters] = useState<ActorGroup[]>([...ACTOR_GROUPS]);
  const [typeFilter, setTypeFilter] = useState<TurnCategory | "all">("all");
  const [expandedTurnIds, setExpandedTurnIds] = useState<Set<number>>(new Set());
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(360);
  const [heightMap, setHeightMap] = useState<Map<number, number>>(new Map());
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const turnIdBySequence = useMemo(() => {
    const map = new Map<number, number>();
    turns.forEach((turn) => {
      map.set(turn.sequenceNumber, turn.id);
    });
    return map;
  }, [turns]);

  const orderedTurns = useMemo(() => {
    const copy = [...turns];
    return copy.sort((a, b) => {
      const aTime = Date.parse(a.timestamp) || 0;
      const bTime = Date.parse(b.timestamp) || 0;
      return aTime - bTime;
    });
  }, [turns]);

  const filteredTurns = useMemo(() => {
    const activeActors = new Set(actorFilters);
    return orderedTurns.filter((turn) => {
      const actorGroup = getActorGroup(turn);
      if (!activeActors.has(actorGroup)) {
        return false;
      }
      const category = getCategory(turn);
      if (typeFilter === "all") {
        return true;
      }
      return category === typeFilter;
    });
  }, [actorFilters, orderedTurns, typeFilter]);

  const idToIndex = useMemo(() => {
    const map = new Map<number, number>();
    filteredTurns.forEach((turn, index) => {
      map.set(turn.id, index);
    });
    return map;
  }, [filteredTurns]);

  const setRowHeight = useCallback((id: number, height: number) => {
    if (!Number.isFinite(height) || height <= 0) {
      return;
    }
    setHeightMap((prev) => {
      const currentHeight = prev.get(id);
      if (currentHeight === height) {
        return prev;
      }
      const next = new Map(prev);
      next.set(id, height);
      return next;
    });
  }, []);

  const layout = useMemo(() => {
    const heights = filteredTurns.map((turn) => {
      const measured = heightMap.get(turn.id);
      if (typeof measured === "number") {
        return measured;
      }
      return expandedTurnIds.has(turn.id) ? EXPANDED_ROW_HEIGHT : COLLAPSED_ROW_HEIGHT;
    });
    const offsets: number[] = [];
    let totalHeight = 0;
    for (const height of heights) {
      offsets.push(totalHeight);
      totalHeight += height;
    }
    return { heights, offsets, totalHeight };
  }, [expandedTurnIds, filteredTurns, heightMap]);

  const visibleRange = useMemo(() => {
    if (filteredTurns.length === 0) {
      return {
        startIndex: 0,
        endIndex: 0,
        topPadding: 0,
        bottomPadding: 0,
      };
    }
    const startOffset = Math.max(scrollTop - OVERSCAN_PX, 0);
    let startIndex = 0;
    while (
      startIndex < layout.offsets.length - 1 &&
      layout.offsets[startIndex + 1] <= startOffset
    ) {
      startIndex += 1;
    }

    const endOffset = scrollTop + viewportHeight + OVERSCAN_PX;
    let endIndex = startIndex;
    while (endIndex < layout.offsets.length && layout.offsets[endIndex] < endOffset) {
      endIndex += 1;
    }

    const topPadding = layout.offsets[startIndex] ?? 0;
    const endPaddingOffset =
      endIndex < layout.offsets.length ? layout.offsets[endIndex] : layout.totalHeight;
    const visibleHeight = endPaddingOffset - topPadding;
    const bottomPadding = Math.max(layout.totalHeight - topPadding - visibleHeight, 0);

    return {
      startIndex,
      endIndex,
      topPadding,
      bottomPadding,
    };
  }, [filteredTurns.length, layout, scrollTop, viewportHeight]);

  const visibleTurns = useMemo(
    () => filteredTurns.slice(visibleRange.startIndex, visibleRange.endIndex),
    [filteredTurns, visibleRange.endIndex, visibleRange.startIndex]
  );

  const handleScroll = useCallback((event: UIEvent<HTMLDivElement>) => {
    setScrollTop(event.currentTarget.scrollTop);
  }, []);

  const scrollToTurn = useCallback(
    (turnId: number, behavior: ScrollBehavior = "smooth") => {
      const container = scrollRef.current;
      const index = idToIndex.get(turnId);
      if (!container || index === undefined) {
        return;
      }
      const offset = layout.offsets[index] ?? 0;
      container.scrollTo({ top: offset, behavior });
    },
    [idToIndex, layout.offsets]
  );

  const handleLink = useCallback(
    (turnId: number) => {
      if (typeof window === "undefined") {
        return;
      }
      window.history.replaceState(null, "", `#turn-${turnId}`);
      scrollToTurn(turnId);
      setExpandedTurnIds((prev) => {
        const next = new Set(prev);
        next.add(turnId);
        return next;
      });
    },
    [scrollToTurn]
  );

  const toggleExpanded = useCallback((turnId: number) => {
    setExpandedTurnIds((prev) => {
      const next = new Set(prev);
      if (next.has(turnId)) {
        next.delete(turnId);
      } else {
        next.add(turnId);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) {
      return;
    }
    const updateHeight = () => {
      setViewportHeight(element.clientHeight || 360);
    };
    updateHeight();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateHeight);
      return () => window.removeEventListener("resize", updateHeight);
    }
    const observer = new ResizeObserver(() => updateHeight());
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [actorFilters, typeFilter]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handleHash = () => {
      const hash = window.location.hash;
      if (!hash.startsWith("#turn-")) {
        return;
      }
      const id = Number(hash.replace("#turn-", ""));
      if (!Number.isFinite(id)) {
        return;
      }
      scrollToTurn(id, "auto");
      setExpandedTurnIds((prev) => {
        const next = new Set(prev);
        next.add(id);
        return next;
      });
    };
    handleHash();
    window.addEventListener("hashchange", handleHash);
    return () => window.removeEventListener("hashchange", handleHash);
  }, [scrollToTurn]);

  const activeCount = actorFilters.length;

  return (
    <section className="wheel-panel" aria-live="polite" aria-busy={isLoading} id={id}>
      <header className="wheel-panel-header">
        <div>
          <div className="wheel-panel-title">Wheel View</div>
          <div className="wheel-panel-subtitle">
            {turns.length === 0
              ? "No turns yet"
              : `${turns.length} turn${turns.length === 1 ? "" : "s"}`}
          </div>
        </div>
        <div className="wheel-panel-status">
          {activeCount} actor{activeCount === 1 ? "" : "s"} active
        </div>
      </header>
      <div className="wheel-panel-controls">
        <div className="wheel-filter-group">
          <div className="wheel-filter-label">Actors</div>
          <div className="wheel-filter-chips" role="group" aria-label="Actor filters">
            {ACTOR_GROUPS.map((actor) => {
              const isActive = actorFilters.includes(actor);
              return (
                <button
                  key={actor}
                  type="button"
                  className={`wheel-filter-chip${isActive ? " is-active" : ""}`}
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
        <div className="wheel-filter-group">
          <label className="wheel-filter-label" htmlFor="wheel-type-filter">
            Type
          </label>
          <select
            id="wheel-type-filter"
            className="wheel-filter-select"
            value={typeFilter}
            onChange={(event) => {
              setTypeFilter(event.target.value as TurnCategory | "all");
            }}
            aria-label="Type filter"
          >
            <option value="all">All types</option>
            <option value="input">Input</option>
            <option value="response">Response</option>
            <option value="proposal">Proposal</option>
            <option value="crud">CRUD</option>
          </select>
        </div>
        <button
          type="button"
          className="wheel-filter-reset"
          onClick={() => {
            setActorFilters([...ACTOR_GROUPS]);
            setTypeFilter("all");
          }}
        >
          Reset filters
        </button>
      </div>
      <div className="wheel-panel-body" role="log" aria-live="polite" onScroll={handleScroll} ref={scrollRef}>
        {isLoading && <div className="wheel-panel-state">Loading timeline...</div>}
        {error && !isLoading && <div className="wheel-panel-error">{error}</div>}
        {!isLoading && !error && filteredTurns.length === 0 && (
          <div className="wheel-panel-state">No turns match these filters.</div>
        )}
        {!isLoading && !error && filteredTurns.length > 0 && (
          <div className="wheel-turns" role="list">
            <div style={{ height: visibleRange.topPadding }} aria-hidden="true" />
            {visibleTurns.map((turn) => {
              const actorGroup = getActorGroup(turn);
              const category = getCategory(turn);
              const isExpanded = expandedTurnIds.has(turn.id);
              return (
                <TurnRow
                  key={turn.id}
                  turn={turn}
                  actorGroup={actorGroup}
                  category={category}
                  turnIdBySequence={turnIdBySequence}
                  nodes={nodes}
                  isExpanded={isExpanded}
                  onToggle={() => toggleExpanded(turn.id)}
                  onLink={() => handleLink(turn.id)}
                  onHeightChange={setRowHeight}
                />
              );
            })}
            <div style={{ height: visibleRange.bottomPadding }} aria-hidden="true" />
          </div>
        )}
      </div>
      <style jsx>{`
        .wheel-panel {
          border-radius: 0.9rem;
          border: 1px solid #1f2937;
          background: radial-gradient(circle at top, #0f172a 0%, #0b1120 70%);
          color: #e2e8f0;
          box-shadow: 0 18px 42px rgba(0, 0, 0, 0.45);
          overflow: hidden;
        }

        .wheel-panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 1rem;
          padding: 0.85rem 1rem 0.75rem;
          border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.85);
        }

        .wheel-panel-title {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.18em;
          color: #94a3b8;
        }

        .wheel-panel-subtitle {
          font-size: 0.9rem;
          color: #e2e8f0;
          margin-top: 0.2rem;
        }

        .wheel-panel-status {
          font-size: 0.75rem;
          color: #94a3b8;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }

        .wheel-panel-controls {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 0.6rem 1rem;
          padding: 0.75rem 1rem;
          border-bottom: 1px solid rgba(148, 163, 184, 0.15);
          background: rgba(15, 23, 42, 0.6);
        }

        .wheel-filter-group {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          flex-wrap: wrap;
        }

        .wheel-filter-label {
          font-size: 0.65rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: #94a3b8;
        }

        .wheel-filter-chips {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          flex-wrap: wrap;
        }

        .wheel-filter-chip {
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

        .wheel-filter-chip.is-active {
          border-color: rgba(56, 189, 248, 0.6);
          color: #e0f2fe;
          box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.25);
        }

        .wheel-filter-select {
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid rgba(71, 85, 105, 0.6);
          color: #e2e8f0;
          border-radius: 0.6rem;
          padding: 0.35rem 0.6rem;
          font-size: 0.75rem;
        }

        .wheel-filter-reset {
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

        .wheel-panel-body {
          padding: 0.85rem 1rem 1rem;
          max-height: min(60vh, 520px);
          overflow-y: auto;
        }

        .wheel-panel-state {
          font-size: 0.85rem;
          color: #94a3b8;
        }

        .wheel-panel-error {
          font-size: 0.85rem;
          color: #fca5a5;
          background: rgba(127, 29, 29, 0.35);
          border: 1px solid rgba(239, 68, 68, 0.4);
          padding: 0.5rem 0.65rem;
          border-radius: 0.5rem;
        }

        .wheel-turns {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .wheel-turn {
          position: relative;
          padding: 0.75rem 0.85rem 0.75rem 1.4rem;
          border-radius: 0.85rem;
          border: 1px solid rgba(30, 41, 59, 0.7);
          background: rgba(15, 23, 42, 0.65);
        }

        .wheel-turn::before {
          content: "";
          position: absolute;
          left: 0.65rem;
          top: 0.5rem;
          bottom: 0.5rem;
          width: 1px;
          background: rgba(148, 163, 184, 0.25);
        }

        .wheel-turn-header {
          display: grid;
          grid-template-columns: auto 1fr auto;
          gap: 0.75rem;
          align-items: start;
        }

        .wheel-turn-marker {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.3rem;
          min-width: 3rem;
        }

        .wheel-turn-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 1.6rem;
          height: 1.6rem;
          border-radius: 999px;
          font-size: 0.75rem;
          font-weight: 700;
          color: #0f172a;
        }

        .icon-user {
          background: #38bdf8;
        }

        .icon-system {
          background: #f97316;
        }

        .icon-job {
          background: #22c55e;
        }

        .wheel-turn-link {
          border: none;
          background: none;
          color: #e2e8f0;
          font-size: 0.7rem;
          cursor: pointer;
          text-decoration: underline;
          text-decoration-color: rgba(148, 163, 184, 0.4);
        }

        .wheel-turn-main {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
        }

        .wheel-turn-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          font-size: 0.7rem;
          color: #94a3b8;
          align-items: center;
        }

        .wheel-turn-actor {
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-weight: 600;
          color: #e2e8f0;
        }

        .wheel-turn-tag {
          padding: 0.1rem 0.4rem;
          border-radius: 999px;
          border: 1px solid rgba(148, 163, 184, 0.3);
          font-size: 0.6rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
        }

        .tag-input {
          color: #38bdf8;
          border-color: rgba(56, 189, 248, 0.4);
        }

        .tag-response {
          color: #fca5a5;
          border-color: rgba(248, 113, 113, 0.45);
        }

        .tag-proposal {
          color: #fbbf24;
          border-color: rgba(251, 191, 36, 0.4);
        }

        .wheel-turn-tag.response-conversational {
          color: #93c5fd;
          border-color: rgba(147, 197, 253, 0.45);
        }

        .wheel-turn-tag.response-proposal {
          color: #fb923c;
          border-color: rgba(251, 146, 60, 0.45);
        }

        .wheel-turn-tag.response-clarification {
          color: #facc15;
          border-color: rgba(250, 204, 21, 0.45);
        }

        .wheel-turn-tag.response-acknowledgment {
          color: #34d399;
          border-color: rgba(52, 211, 153, 0.45);
        }

        .wheel-turn-tag.response-tool_invocation {
          color: #22d3ee;
          border-color: rgba(34, 211, 238, 0.45);
        }

        .tag-crud {
          color: #a7f3d0;
          border-color: rgba(52, 211, 153, 0.45);
        }

        .wheel-turn-type {
          font-size: 0.65rem;
          padding: 0.1rem 0.35rem;
          border-radius: 0.5rem;
          background: rgba(15, 23, 42, 0.6);
          color: #cbd5f5;
        }

        .wheel-turn-time {
          font-variant-numeric: tabular-nums;
        }

        .wheel-turn-summary {
          font-size: 0.95rem;
          color: #e2e8f0;
          line-height: 1.45;
        }

        .wheel-turn-summary :global(a.reference-link),
        .wheel-detail-text :global(a.reference-link) {
          color: #7dd3fc;
          text-decoration: underline;
          text-decoration-thickness: 1px;
          text-underline-offset: 2px;
        }

        .wheel-turn-summary :global(a.reference-link:hover),
        .wheel-detail-text :global(a.reference-link:hover) {
          color: #bae6fd;
        }

        .wheel-turn-toggle {
          border: 1px solid rgba(71, 85, 105, 0.6);
          background: rgba(15, 23, 42, 0.6);
          color: #e2e8f0;
          border-radius: 0.6rem;
          font-size: 0.7rem;
          padding: 0.3rem 0.65rem;
          cursor: pointer;
          height: fit-content;
        }

        .wheel-turn-details {
          margin-top: 0.7rem;
          border-top: 1px solid rgba(148, 163, 184, 0.2);
          padding-top: 0.7rem;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .wheel-detail-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
          gap: 0.6rem;
        }

        .wheel-detail {
          display: flex;
          flex-direction: column;
          gap: 0.2rem;
          font-size: 0.75rem;
        }

        .wheel-detail-label {
          text-transform: uppercase;
          letter-spacing: 0.1em;
          font-size: 0.6rem;
          color: #94a3b8;
        }

        .wheel-detail-value {
          color: #e2e8f0;
          word-break: break-word;
        }

        .wheel-detail-block {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
          font-size: 0.8rem;
        }

        .wheel-detail-text {
          color: #e2e8f0;
          line-height: 1.5;
        }

        .wheel-detail-payload {
          background: rgba(2, 6, 23, 0.8);
          border-radius: 0.6rem;
          padding: 0.6rem 0.75rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
          font-size: 0.75rem;
          color: #e2e8f0;
          overflow-x: auto;
          white-space: pre-wrap;
        }

        .wheel-detail-empty {
          font-size: 0.75rem;
          color: #94a3b8;
        }

        @media (max-width: 640px) {
          .wheel-panel-header {
            flex-direction: column;
            align-items: flex-start;
          }

          .wheel-panel-controls {
            align-items: flex-start;
          }

          .wheel-turn-header {
            grid-template-columns: 1fr;
          }

          .wheel-turn-marker {
            flex-direction: row;
            justify-content: flex-start;
            min-width: 0;
          }

          .wheel-turn-toggle {
            width: 100%;
          }
        }
      `}</style>
    </section>
  );
}
