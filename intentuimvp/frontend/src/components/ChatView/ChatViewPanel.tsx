"use client";

import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  getResponseType,
  getResponseTypeLabel,
  type TurnResponse,
} from "@/hooks/turnTypes";

type ChatViewPanelProps = {
  id?: string;
  turns: TurnResponse[];
  isLoading?: boolean;
  error?: string | null;
};

const ACTOR_LABELS: Record<string, string> = {
  user: "You",
  agent: "Agent",
  system: "System",
  mcp: "Tool",
};

const CLARIFICATION_TYPES = new Set([
  "assumption_presented",
  "assumption_confirmed",
  "assumption_rejected",
  "assumption_modified",
]);

const formatTimestamp = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString([], {
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

const buildTurnContent = (turn: TurnResponse): string => {
  const payload = turn.payload ?? {};
  if (turn.type === "user_input" && typeof payload.command === "string") {
    return payload.command;
  }
  if (turn.type === "assumption_confirmed" && typeof payload.final_text === "string") {
    return `Clarification confirmed: ${payload.final_text}`;
  }
  if (turn.type === "assumption_rejected" && typeof payload.original_text === "string") {
    return `Clarification rejected: ${payload.original_text}`;
  }
  if (turn.type === "assumption_modified" && typeof payload.final_text === "string") {
    return `Clarification updated: ${payload.final_text}`;
  }
  const payloadText = extractPayloadText(payload);
  if (payloadText) {
    return payloadText;
  }
  return turn.summary;
};

export function ChatViewPanel({
  id = "chat-view-panel",
  turns,
  isLoading = false,
  error = null,
}: ChatViewPanelProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const target = bottomRef.current;
    if (target && typeof target.scrollIntoView === "function") {
      target.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [turns.length]);

  return (
    <section className="chat-panel" aria-live="polite" aria-busy={isLoading} id={id}>
      <header className="chat-panel-header">
        <div>
          <div className="chat-panel-title">Chat View</div>
          <div className="chat-panel-subtitle">
            {turns.length === 0
              ? "No conversation yet"
              : `${turns.length} message${turns.length === 1 ? "" : "s"}`}
          </div>
        </div>
      </header>
      <div className="chat-panel-body" role="log" aria-live="polite">
        {isLoading && <div className="chat-panel-state">Loading conversation...</div>}
        {error && !isLoading && (
          <div className="chat-panel-error">{error}</div>
        )}
        {!isLoading && !error && turns.length === 0 && (
          <div className="chat-panel-state">No chat turns yet.</div>
        )}
        <div className="chat-turns">
          {turns.map((turn) => {
            const role = turn.actor === "user" ? "user" : "system";
            const label = ACTOR_LABELS[turn.actor] ?? "System";
            const content = buildTurnContent(turn);
            const timestamp = formatTimestamp(turn.timestamp);
            const responseType = getResponseType(turn);
            const responseLabel = responseType
              ? getResponseTypeLabel(responseType)
              : null;
            const isClarification =
              !responseType && CLARIFICATION_TYPES.has(turn.type);

            return (
              <div
                key={turn.id}
                className={`chat-turn ${role}${
                  responseType ? ` response-${responseType}` : ""
                }`}
              >
                <div className="chat-meta">
                  <span className="chat-role">{label}</span>
                  {responseType && (
                    <span className={`chat-tag response-${responseType}`}>
                      {responseLabel}
                    </span>
                  )}
                  {isClarification && !responseType && (
                    <span className="chat-tag response-clarification">
                      Clarification
                    </span>
                  )}
                  {timestamp && <time className="chat-time">{timestamp}</time>}
                </div>
                <div
                  className={`chat-bubble${
                    responseType ? ` response-${responseType}` : ""
                  }`}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      </div>
      <style jsx>{`
        .chat-panel {
          border-radius: 0.9rem;
          border: 1px solid #1f2937;
          background: linear-gradient(180deg, #0f172a 0%, #0b1120 100%);
          color: #e2e8f0;
          box-shadow: 0 18px 42px rgba(0, 0, 0, 0.45);
          overflow: hidden;
        }

        .chat-panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.85rem 1rem 0.75rem;
          border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(15, 23, 42, 0.85);
        }

        .chat-panel-title {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.18em;
          color: #94a3b8;
        }

        .chat-panel-subtitle {
          font-size: 0.85rem;
          color: #e2e8f0;
          margin-top: 0.2rem;
        }

        .chat-panel-body {
          padding: 0.85rem 1rem 1rem;
          max-height: min(58vh, 520px);
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .chat-panel-state {
          font-size: 0.85rem;
          color: #94a3b8;
        }

        .chat-panel-error {
          font-size: 0.85rem;
          color: #fca5a5;
          background: rgba(127, 29, 29, 0.35);
          border: 1px solid rgba(239, 68, 68, 0.4);
          padding: 0.5rem 0.65rem;
          border-radius: 0.5rem;
        }

        .chat-turns {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .chat-turn {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
          max-width: 82%;
        }

        .chat-turn.user {
          align-self: flex-end;
          text-align: right;
        }

        .chat-turn.system {
          align-self: flex-start;
        }

        .chat-meta {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.7rem;
          color: #94a3b8;
        }

        .chat-turn.user .chat-meta {
          justify-content: flex-end;
        }

        .chat-role {
          font-weight: 600;
          letter-spacing: 0.04em;
          text-transform: uppercase;
        }

        .chat-time {
          font-variant-numeric: tabular-nums;
        }

        .chat-tag {
          padding: 0.15rem 0.4rem;
          border-radius: 999px;
          border: 1px solid rgba(56, 189, 248, 0.35);
          color: #7dd3fc;
          font-size: 0.65rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
        }

        .chat-tag.response-conversational {
          color: #93c5fd;
          border-color: rgba(147, 197, 253, 0.45);
        }

        .chat-tag.response-proposal {
          color: #fb923c;
          border-color: rgba(251, 146, 60, 0.45);
        }

        .chat-tag.response-clarification {
          color: #facc15;
          border-color: rgba(250, 204, 21, 0.45);
        }

        .chat-tag.response-acknowledgment {
          color: #34d399;
          border-color: rgba(52, 211, 153, 0.45);
        }

        .chat-tag.response-tool_invocation {
          color: #22d3ee;
          border-color: rgba(34, 211, 238, 0.45);
        }

        .chat-bubble {
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid rgba(148, 163, 184, 0.2);
          border-radius: 0.85rem;
          padding: 0.65rem 0.85rem;
          font-size: 0.95rem;
          line-height: 1.5;
          color: #e2e8f0;
        }

        .chat-turn.user .chat-bubble {
          background: rgba(30, 41, 59, 0.9);
          border-color: rgba(56, 189, 248, 0.35);
        }

        .chat-bubble.response-conversational {
          border-color: rgba(147, 197, 253, 0.45);
        }

        .chat-bubble.response-proposal {
          border-color: rgba(251, 146, 60, 0.5);
        }

        .chat-bubble.response-clarification {
          border-color: rgba(250, 204, 21, 0.5);
        }

        .chat-bubble.response-acknowledgment {
          border-color: rgba(52, 211, 153, 0.5);
        }

        .chat-bubble.response-tool_invocation {
          border-color: rgba(34, 211, 238, 0.55);
        }

        .chat-bubble :global(p) {
          margin: 0 0 0.5rem;
        }

        .chat-bubble :global(p:last-child) {
          margin-bottom: 0;
        }

        .chat-bubble :global(code) {
          font-family: "SFMono-Regular", ui-monospace, SFMono-Regular, Menlo, Monaco,
            Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 0.85rem;
          background: rgba(15, 23, 42, 0.65);
          padding: 0.15rem 0.35rem;
          border-radius: 0.35rem;
          border: 1px solid rgba(148, 163, 184, 0.2);
        }

        .chat-bubble :global(pre) {
          margin: 0.6rem 0 0;
          padding: 0.6rem 0.75rem;
          background: rgba(2, 6, 23, 0.8);
          border-radius: 0.6rem;
          overflow-x: auto;
          border: 1px solid rgba(148, 163, 184, 0.2);
        }

        .chat-bubble :global(pre code) {
          padding: 0;
          border: none;
          background: transparent;
        }

        .chat-bubble :global(ul),
        .chat-bubble :global(ol) {
          margin: 0.5rem 0 0.5rem 1.25rem;
          padding: 0;
        }

        .chat-bubble :global(li + li) {
          margin-top: 0.35rem;
        }

        @media (max-width: 640px) {
          .chat-panel-body {
            max-height: min(60vh, 420px);
            padding: 0.75rem 0.85rem 0.85rem;
          }

          .chat-turn {
            max-width: 92%;
          }

          .chat-bubble {
            font-size: 0.9rem;
          }
        }
      `}</style>
    </section>
  );
}
