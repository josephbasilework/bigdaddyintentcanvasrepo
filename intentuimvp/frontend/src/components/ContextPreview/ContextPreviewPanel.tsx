"use client";

import { useMemo } from "react";
import type {
  ContextPreview,
  ContextPreviewAttachment,
  ContextPreviewNode,
  ContextPreviewTurn,
} from "@/types/contextPreview";

type ContextPreviewPanelProps = {
  id?: string;
  preview: ContextPreview | null;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
};

const clipText = (value: string, limit = 180): string => {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed.length <= limit) {
    return trimmed;
  }
  return `${trimmed.slice(0, limit - 3).trimEnd()}...`;
};

const formatNumber = (value?: number | null): string => {
  if (value === null || value === undefined) {
    return "-";
  }
  return value.toFixed(2);
};

const formatReasonLabel = (reason: string): string => {
  if (reason.startsWith("semantic_match:")) {
    const parts = reason.split(":");
    const score = Number(parts[1]);
    if (Number.isFinite(score)) {
      return `Semantic match ${score.toFixed(2)}`;
    }
    return "Semantic match";
  }
  const mapping: Record<string, string> = {
    selected: "Selected",
    primary: "Primary",
    explicit_reference: "Explicit reference",
    expanded: "Expansion",
    recent_turn: "Recency",
    intent_memory: "Intent memory pattern",
  };
  return mapping[reason] ?? reason.replace(/_/g, " ");
};

const renderReasonPills = (
  reasons: string[],
  reasonScores?: Record<string, number> | null
) => {
  if (!reasons.length) {
    return null;
  }
  return (
    <div className="context-preview-reasons">
      {reasons.map((reason) => {
        const score = reasonScores?.[reason];
        return (
          <span key={reason} className="context-preview-reason">
            {formatReasonLabel(reason)}
            {typeof score === "number" && (
              <span className="context-preview-reason-score">+{score.toFixed(2)}</span>
            )}
          </span>
        );
      })}
    </div>
  );
};

const renderNodeItem = (node: ContextPreviewNode) => {
  const summary = node.content ? clipText(node.content) : "";
  return (
    <li key={node.id} className="context-preview-item">
      <div className="context-preview-item-header">
        <div className="context-preview-item-title">
          {node.title || `Node ${node.id}`}
          {node.is_primary && <span className="context-preview-badge">Primary</span>}
        </div>
        <div className="context-preview-item-meta">
          <span>{node.node_type}</span>
          <span>score {formatNumber(node.score)}</span>
          <span>sim {formatNumber(node.similarity)}</span>
        </div>
      </div>
      {summary && <div className="context-preview-item-body">{summary}</div>}
      {renderReasonPills(node.reasons, node.reason_scores)}
    </li>
  );
};

const renderTurnItem = (turn: ContextPreviewTurn) => {
  const summary = clipText(turn.summary, 160);
  return (
    <li key={turn.id} className="context-preview-item">
      <div className="context-preview-item-header">
        <div className="context-preview-item-title">
          Turn {turn.sequence_number} - {turn.actor}/{turn.turn_type}
        </div>
        <div className="context-preview-item-meta">
          <span>score {formatNumber(turn.score)}</span>
          <span>sim {formatNumber(turn.similarity)}</span>
        </div>
      </div>
      {summary && <div className="context-preview-item-body">{summary}</div>}
      {renderReasonPills(turn.reasons, turn.reason_scores)}
    </li>
  );
};

const renderAttachmentItem = (attachment: ContextPreviewAttachment) => {
  const summarySource =
    attachment.text_content || attachment.transcription || attachment.description || "";
  const summary = clipText(summarySource, 140);
  return (
    <li key={attachment.id} className="context-preview-item">
      <div className="context-preview-item-header">
        <div className="context-preview-item-title">{attachment.filename}</div>
        <div className="context-preview-item-meta">
          <span>{attachment.attachment_type}</span>
          <span>{attachment.mime_type}</span>
          <span>{attachment.size_bytes} bytes</span>
        </div>
      </div>
      {summary && <div className="context-preview-item-body">{summary}</div>}
    </li>
  );
};

export function ContextPreviewPanel({
  id = "context-preview-panel",
  preview,
  isLoading,
  error,
  onRefresh,
}: ContextPreviewPanelProps) {
  const inputText = preview?.input_text ?? "";
  const promptText = preview?.prompt ?? "";

  const hasNodes = (preview?.nodes?.length ?? 0) > 0;
  const hasTurns = (preview?.turns?.length ?? 0) > 0;
  const hasAttachments = (preview?.attachments?.length ?? 0) > 0;

  const nodes = useMemo(() => preview?.nodes ?? [], [preview]);
  const turns = useMemo(() => preview?.turns ?? [], [preview]);
  const attachments = useMemo(() => preview?.attachments ?? [], [preview]);

  return (
    <section className="context-preview-panel" id={id} aria-live="polite">
      <header className="context-preview-header">
        <div>
          <h2 className="context-preview-title">Context Preview</h2>
          <div className="context-preview-subtitle">
            {isLoading ? "Refreshing context..." : "Explainable routing snapshot"}
          </div>
        </div>
        {onRefresh && (
          <button
            type="button"
            className="context-preview-refresh"
            onClick={onRefresh}
            disabled={isLoading}
          >
            Refresh
          </button>
        )}
      </header>

      {error && <div className="context-preview-error">{error}</div>}

      {!preview && !isLoading && !error && (
        <div className="context-preview-empty">No context preview yet.</div>
      )}

      {preview && (
        <div className="context-preview-body">
          <div className="context-preview-section">
            <span className="context-preview-section-label">Input</span>
            <div className="context-preview-input">
              {inputText ? inputText : "Draft is empty."}
            </div>
          </div>

          <div className="context-preview-section">
            <span className="context-preview-section-label">Prompt</span>
            <pre className="context-preview-prompt">{promptText || "No prompt yet."}</pre>
          </div>

          <div className="context-preview-section">
            <span className="context-preview-section-label">
              Nodes {hasNodes ? `(${nodes.length})` : ""}
            </span>
            {hasNodes ? (
              <ul className="context-preview-list">{nodes.map(renderNodeItem)}</ul>
            ) : (
              <div className="context-preview-empty">No nodes selected.</div>
            )}
          </div>

          <div className="context-preview-section">
            <span className="context-preview-section-label">
              Turns {hasTurns ? `(${turns.length})` : ""}
            </span>
            {hasTurns ? (
              <ul className="context-preview-list">{turns.map(renderTurnItem)}</ul>
            ) : (
              <div className="context-preview-empty">No recent turns yet.</div>
            )}
          </div>

          <div className="context-preview-section">
            <span className="context-preview-section-label">
              Attachments {hasAttachments ? `(${attachments.length})` : ""}
            </span>
            {hasAttachments ? (
              <ul className="context-preview-list">
                {attachments.map(renderAttachmentItem)}
              </ul>
            ) : (
              <div className="context-preview-empty">No attachments queued.</div>
            )}
          </div>
        </div>
      )}

      <style jsx>{`
        .context-preview-panel {
          background: rgba(15, 23, 42, 0.94);
          border: 1px solid rgba(51, 65, 85, 0.6);
          border-radius: 1rem;
          padding: 1rem;
          color: #e2e8f0;
          box-shadow: 0 12px 30px rgba(15, 23, 42, 0.45);
        }

        .context-preview-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 1rem;
          margin-bottom: 0.75rem;
        }

        .context-preview-title {
          font-size: 1rem;
          font-weight: 600;
          margin: 0;
        }

        .context-preview-subtitle {
          font-size: 0.75rem;
          color: #94a3b8;
        }

        .context-preview-refresh {
          border: 1px solid rgba(71, 85, 105, 0.8);
          background: rgba(30, 41, 59, 0.8);
          color: #e2e8f0;
          font-size: 0.75rem;
          padding: 0.35rem 0.65rem;
          border-radius: 0.5rem;
          cursor: pointer;
          transition: all 0.15s ease-in-out;
        }

        .context-preview-refresh:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .context-preview-refresh:hover:not(:disabled) {
          border-color: #38bdf8;
          color: #e0f2fe;
        }

        .context-preview-error {
          padding: 0.5rem 0.75rem;
          background: rgba(127, 29, 29, 0.7);
          border: 1px solid rgba(239, 68, 68, 0.6);
          border-radius: 0.6rem;
          font-size: 0.75rem;
          margin-bottom: 0.75rem;
        }

        .context-preview-empty {
          font-size: 0.75rem;
          color: #94a3b8;
        }

        .context-preview-body {
          display: flex;
          flex-direction: column;
          gap: 0.85rem;
        }

        .context-preview-section {
          display: flex;
          flex-direction: column;
          gap: 0.4rem;
        }

        .context-preview-section-label {
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-size: 0.65rem;
          color: #94a3b8;
        }

        .context-preview-input {
          font-size: 0.85rem;
          color: #e2e8f0;
        }

        .context-preview-prompt {
          background: rgba(30, 41, 59, 0.75);
          border: 1px solid rgba(71, 85, 105, 0.5);
          border-radius: 0.75rem;
          padding: 0.75rem;
          font-size: 0.75rem;
          color: #e2e8f0;
          white-space: pre-wrap;
          max-height: 200px;
          overflow: auto;
        }

        .context-preview-list {
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .context-preview-item {
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid rgba(51, 65, 85, 0.6);
          border-radius: 0.75rem;
          padding: 0.65rem 0.75rem;
          display: flex;
          flex-direction: column;
          gap: 0.4rem;
        }

        .context-preview-item-header {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          gap: 0.75rem;
        }

        .context-preview-item-title {
          font-size: 0.85rem;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .context-preview-badge {
          font-size: 0.6rem;
          padding: 0.15rem 0.35rem;
          border-radius: 999px;
          background: rgba(56, 189, 248, 0.2);
          color: #7dd3fc;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }

        .context-preview-item-meta {
          display: flex;
          gap: 0.5rem;
          font-size: 0.65rem;
          color: #94a3b8;
          flex-wrap: wrap;
        }

        .context-preview-item-body {
          font-size: 0.75rem;
          color: #cbd5f5;
        }

        .context-preview-reasons {
          display: flex;
          flex-wrap: wrap;
          gap: 0.35rem;
        }

        .context-preview-reason {
          font-size: 0.65rem;
          padding: 0.2rem 0.45rem;
          border-radius: 999px;
          background: rgba(30, 41, 59, 0.8);
          border: 1px solid rgba(71, 85, 105, 0.5);
          color: #e2e8f0;
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
        }

        .context-preview-reason-score {
          font-size: 0.6rem;
          color: #7dd3fc;
        }

        @media (max-width: 640px) {
          .context-preview-panel {
            padding: 0.75rem;
          }

          .context-preview-item-header {
            flex-direction: column;
            align-items: flex-start;
          }
        }
      `}</style>
    </section>
  );
}
