"use client";

import { useId, useState } from "react";
import type { Assumption, AssumptionsPanelProps, IntentWorkflowRound } from "./types";
import { getAssumptionCounts } from "./stateMachine";

const formatTimestamp = (value?: string): string => {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
};

const ROUND_STATUS_LABELS: Record<IntentWorkflowRound["status"], string> = {
  reviewing: "In review",
  resolved: "Resolved",
  executed: "Executed",
  dismissed: "Dismissed",
  superseded: "Superseded",
};

const getRoundStatusLabel = (status: IntentWorkflowRound["status"]): string =>
  ROUND_STATUS_LABELS[status] ?? "Unknown";

/**
 * AssumptionsPanel renders the inline intent workflow for review.
 *
 * Shows user input, system proposal, assumptions, and optional clarifying questions.
 */
export function AssumptionsPanel({
  id = "intent-workflow-panel",
  currentRound,
  previousRounds = [],
  onAccept,
  onReject,
  onEdit,
  onConfirm,
  onDismiss,
  onRequestRevision,
  onClarificationSubmit,
}: AssumptionsPanelProps) {
  const titleId = useId();
  const explainId = useId();
  const clarifyId = useId();
  const [showExplain, setShowExplain] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [clarificationText, setClarificationText] = useState("");

  if (!currentRound && previousRounds.length === 0) {
    return null;
  }

  const activeRound = currentRound;
  const assumptions = activeRound?.assumptions ?? [];
  const assumptionSet = activeRound?.assumptionSet;
  const proposalAction = assumptionSet?.action ?? assumptionSet?.intent;
  const clarifyingQuestions = activeRound?.clarifyingQuestions ?? [];
  const isReviewing = activeRound?.status === "reviewing";

  const { pending: pendingCount, accepted: acceptedCount, rejected: rejectedCount } =
    getAssumptionCounts(assumptions);
  const totalCount = assumptions.length;

  const allResolved = pendingCount === 0;
  const hasRejectedAssumptions = rejectedCount > 0;
  const hasClarifyingQuestions = clarifyingQuestions.length > 0;
  const hasEditedAssumptions = assumptions.some((assumption) => {
    if (assumption.status === "pending") {
      return false;
    }
    return assumption.text.trim() !== assumption.originalText.trim();
  });
  const canRequestRevision =
    isReviewing && allResolved && (hasEditedAssumptions || hasRejectedAssumptions);

  const intentConfidence =
    typeof assumptionSet?.confidence === "number" ? assumptionSet.confidence : null;
  const intentConfidencePercent =
    intentConfidence === null ? null : Math.round(intentConfidence * 100);
  const intentConfidenceWidth =
    intentConfidencePercent === null
      ? null
      : Math.min(100, Math.max(0, intentConfidencePercent));
  const hasExplain =
    Boolean(assumptionSet?.reasoning) ||
    Boolean(assumptionSet?.alternatives && assumptionSet.alternatives.length > 0);
  const hasIntentSummary =
    Boolean(proposalAction) ||
    Boolean(assumptionSet?.intentDescription) ||
    intentConfidencePercent !== null;

  const roundCount = previousRounds.length + (currentRound ? 1 : 0);
  const roundIndex = currentRound ? previousRounds.length + 1 : 0;

  // Get category display label
  const getCategoryLabel = (category: Assumption["category"]): string => {
    const labels: Record<Assumption["category"], string> = {
      context: "Context",
      intent: "Intent",
      parameter: "Parameter",
      other: "Other",
    };
    return labels[category] || "Other";
  };

  // Get category color
  const getCategoryColor = (category: Assumption["category"]): string => {
    const colors: Record<Assumption["category"], string> = {
      context: "#3b82f6", // blue
      intent: "#8b5cf6", // purple
      parameter: "#f59e0b", // amber
      other: "#6b7280", // gray
    };
    return colors[category] || colors.other;
  };

  const handleStartEdit = (assumption: Assumption) => {
    if (!isReviewing) {
      return;
    }
    setEditingId(assumption.id);
    setEditText(assumption.text);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditText("");
  };

  const handleSaveEdit = (assumptionId: string) => {
    if (!isReviewing) {
      return;
    }
    const trimmed = editText.trim();
    if (!trimmed) {
      return;
    }
    onEdit(assumptionId, trimmed);
    setEditingId(null);
    setEditText("");
  };

  const handleClarificationSubmit = () => {
    if (!onClarificationSubmit) {
      return;
    }
    const trimmed = clarificationText.trim();
    if (!trimmed) {
      return;
    }
    onClarificationSubmit(trimmed);
    setClarificationText("");
  };

  const renderRoundAssumptions = (round: IntentWorkflowRound) => {
    if (round.assumptions.length === 0) {
      return (
        <div className="assumptions-history-empty">No assumptions were listed.</div>
      );
    }

    return (
      <ul className="assumptions-history-assumptions">
        {round.assumptions.map((assumption) => (
          <li key={assumption.id} className="assumptions-history-assumption">
            <span className="assumptions-history-assumption-text">
              {assumption.text}
            </span>
            <span
              className={`assumptions-history-assumption-status status-${assumption.status}`}
            >
              {assumption.status}
            </span>
          </li>
        ))}
      </ul>
    );
  };

  return (
    <section className="assumptions-panel" id={id} aria-labelledby={titleId}>
      <header className="assumptions-header">
        <div className="assumptions-header-content">
          <h2 className="assumptions-title" id={titleId}>
            Intent Workflow
          </h2>
          {currentRound ? (
            <div className="assumptions-subtitle">
              Round {roundIndex} of {roundCount}
              {totalCount > 0 && ` · ${totalCount} assumptions`}
            </div>
          ) : (
            <div className="assumptions-subtitle">No active proposals.</div>
          )}
        </div>
        {currentRound && (
          <div className="assumptions-header-actions">
            {hasExplain && (
              <button
                type="button"
                onClick={() => setShowExplain((prev) => !prev)}
                className="assumptions-explain-toggle"
                aria-expanded={showExplain}
                aria-controls={explainId}
              >
                {showExplain ? "Hide reasoning" : "Explain"}
              </button>
            )}
            {onDismiss && isReviewing && (
              <button
                type="button"
                onClick={onDismiss}
                className="assumptions-dismiss"
                aria-label="Dismiss"
              >
                Dismiss
              </button>
            )}
          </div>
        )}
      </header>

      <div className="assumptions-body">
        {currentRound ? (
          <>
            <div className="assumptions-stage">
              <span className="assumptions-stage-label">User input</span>
              <div className="assumptions-command">{currentRound.commandText}</div>
              {currentRound.attachments.length > 0 && (
                <div className="assumptions-attachments" role="list">
                  {currentRound.attachments.map((attachment) => (
                    <span
                      key={attachment.id}
                      className="assumptions-attachment"
                      role="listitem"
                    >
                      {attachment.name}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {hasIntentSummary && (
              <div className="assumptions-stage">
                <span className="assumptions-stage-label">System proposal</span>
                <div className="assumptions-overview">
                  <div className="assumptions-intent">
                    <span className="assumptions-intent-label">Primary intent</span>
                    {proposalAction && (
                      <div className="assumptions-intent-value">
                        {proposalAction}
                      </div>
                    )}
                    {assumptionSet?.intentDescription && (
                      <div className="assumptions-intent-description">
                        {assumptionSet.intentDescription}
                      </div>
                    )}
                  </div>
                  {intentConfidencePercent !== null && (
                    <div className="assumptions-confidence">
                      <span className="assumptions-confidence-label">Intent confidence</span>
                      <div className="assumptions-confidence-meter">
                        <div
                          className="assumptions-confidence-fill"
                          style={{ width: `${intentConfidenceWidth}%` }}
                        />
                      </div>
                      <span className="assumptions-confidence-value">
                        {intentConfidencePercent}%
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {showExplain && hasExplain && (
              <div className="assumptions-explain" id={explainId}>
                {assumptionSet?.reasoning && (
                  <div className="assumptions-reasoning">
                    <span className="assumptions-reasoning-label">Reasoning</span>
                    <p className="assumptions-reasoning-text">
                      {assumptionSet.reasoning}
                    </p>
                  </div>
                )}
                {assumptionSet?.alternatives &&
                  assumptionSet.alternatives.length > 0 && (
                    <div className="assumptions-alternatives">
                      <span className="assumptions-alternatives-label">
                        Alternate interpretations
                      </span>
                      <ul className="assumptions-alternatives-list">
                        {assumptionSet.alternatives.map((alternative) => (
                          <li
                            key={alternative.name}
                            className="assumptions-alternative-item"
                          >
                            <div className="assumptions-alternative-header">
                              <span className="assumptions-alternative-name">
                                {alternative.name}
                              </span>
                              <span className="assumptions-alternative-confidence">
                                {Math.round(alternative.confidence * 100)}%
                              </span>
                            </div>
                            <p className="assumptions-alternative-description">
                              {alternative.description}
                            </p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
              </div>
            )}

            {totalCount > 0 && (
              <>
                <div className="assumptions-summary">
                  <span className="assumptions-count">
                    {totalCount} {totalCount === 1 ? "assumption" : "assumptions"}
                  </span>
                  {acceptedCount > 0 && (
                    <span className="assumptions-stat assumptions-stat-accepted">
                      ✓ {acceptedCount} accepted
                    </span>
                  )}
                  {rejectedCount > 0 && (
                    <span className="assumptions-stat assumptions-stat-rejected">
                      ✗ {rejectedCount} rejected
                    </span>
                  )}
                </div>

                <div className="assumptions-list">
                  {assumptions.map((assumption, index) => {
                    const isEditing =
                      isReviewing &&
                      assumption.status === "pending" &&
                      editingId === assumption.id;

                    return (
                      <div
                        key={assumption.id}
                        className={`assumption-item assumption-item-${assumption.status}`}
                        style={{ animationDelay: `${index * 60}ms` }}
                      >
                        <div
                          className="assumption-category"
                          style={{ backgroundColor: getCategoryColor(assumption.category) }}
                        >
                          {getCategoryLabel(assumption.category)}
                        </div>

                        <div className="assumption-content">
                          {isEditing ? (
                            <div className="assumption-edit">
                              <textarea
                                className="assumption-edit-input"
                                value={editText}
                                onChange={(event) => setEditText(event.target.value)}
                                rows={3}
                                aria-label="Edit assumption"
                              />
                            </div>
                          ) : (
                            <p className="assumption-text">{assumption.text}</p>
                          )}
                          {assumption.explanation && (
                            <p className="assumption-explanation">
                              {assumption.explanation}
                            </p>
                          )}
                          <div className="assumption-confidence">
                            Confidence: {Math.round(assumption.confidence * 100)}%
                          </div>
                        </div>

                        {assumption.status === "pending" && isReviewing && (
                          <div className="assumption-actions">
                            {isEditing ? (
                              <>
                                <button
                                  type="button"
                                  onClick={handleCancelEdit}
                                  className="assumption-btn assumption-btn-cancel"
                                >
                                  Cancel
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleSaveEdit(assumption.id)}
                                  className="assumption-btn assumption-btn-save"
                                  disabled={!editText.trim()}
                                >
                                  Save
                                </button>
                              </>
                            ) : (
                              <>
                                <button
                                  type="button"
                                  onClick={() => onReject(assumption.id)}
                                  className="assumption-btn assumption-btn-reject"
                                >
                                  Reject
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleStartEdit(assumption)}
                                  className="assumption-btn assumption-btn-edit"
                                >
                                  Edit
                                </button>
                                <button
                                  type="button"
                                  onClick={() => onAccept(assumption.id)}
                                  className="assumption-btn assumption-btn-confirm"
                                >
                                  Confirm
                                </button>
                              </>
                            )}
                          </div>
                        )}

                        {assumption.status !== "pending" && (
                          <div
                            className={`assumption-status assumption-status-${assumption.status}`}
                          >
                            {assumption.status === "accepted" ? "✓ Accepted" : "✗ Rejected"}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {hasClarifyingQuestions && (
              <div className="assumptions-stage">
                <span className="assumptions-stage-label">Clarifying questions</span>
                <ul className="assumptions-clarify-list">
                  {clarifyingQuestions.map((question) => (
                    <li key={question} className="assumptions-clarify-item">
                      {question}
                    </li>
                  ))}
                </ul>
                {assumptionSet?.alternatives &&
                  assumptionSet.alternatives.length > 0 && (
                    <div className="assumptions-clarify-alternatives">
                      <span className="assumptions-clarify-label">Possible intents</span>
                      <div className="assumptions-clarify-options">
                        {assumptionSet.alternatives.map((alternative) => (
                          <button
                            key={alternative.name}
                            type="button"
                            className="assumptions-clarify-option"
                            onClick={() =>
                              setClarificationText(
                                `${alternative.name}: ${alternative.description}`
                              )
                            }
                            disabled={!isReviewing}
                          >
                            {alternative.name}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                {onClarificationSubmit && isReviewing && (
                  <div className="assumptions-clarify-input">
                    <label htmlFor={clarifyId} className="assumptions-clarify-label">
                      Your response
                    </label>
                    <textarea
                      id={clarifyId}
                      className="assumptions-clarify-textarea"
                      rows={3}
                      value={clarificationText}
                      onChange={(event) => setClarificationText(event.target.value)}
                      placeholder="Share any missing details or corrections..."
                    />
                    <div className="assumptions-clarify-actions">
                      <button
                        type="button"
                        className="assumptions-clarify-submit"
                        onClick={handleClarificationSubmit}
                        disabled={!clarificationText.trim()}
                      >
                        Send clarification
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="assumptions-empty">No active proposals right now.</div>
        )}

        {previousRounds.length > 0 && (
          <div className="assumptions-history">
            <span className="assumptions-stage-label">Previous rounds</span>
            <div className="assumptions-history-list">
              {previousRounds.map((round, index) => {
                const timestamp = formatTimestamp(round.createdAt);

                return (
                  <details key={round.id} className="assumptions-history-item">
                    <summary className="assumptions-history-summary">
                      <div className="assumptions-history-title">
                        <span>Round {index + 1}</span>
                        {timestamp && (
                          <span className="assumptions-history-time">{timestamp}</span>
                        )}
                      </div>
                      <span
                        className={`assumptions-history-status status-${round.status}`}
                      >
                        {getRoundStatusLabel(round.status)}
                      </span>
                    </summary>
                    <div className="assumptions-history-content">
                      <div className="assumptions-history-command">
                        {round.commandText}
                      </div>
                      {(round.assumptionSet?.action ?? round.assumptionSet?.intent) && (
                        <div className="assumptions-history-intent">
                          Proposal:{" "}
                          {round.assumptionSet?.action ?? round.assumptionSet?.intent}
                        </div>
                      )}
                      {round.clarificationResponse && (
                        <div className="assumptions-history-clarification">
                          Clarification: {round.clarificationResponse}
                        </div>
                      )}
                      {renderRoundAssumptions(round)}
                    </div>
                  </details>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {currentRound && (
        <footer className="assumptions-footer">
          {isReviewing ? (
            hasClarifyingQuestions ? (
              <p className="assumptions-footer-hint">
                Provide clarification to refine the proposal.
              </p>
          ) : !allResolved ? (
            <p className="assumptions-footer-hint">
              Please confirm or reject all assumptions to continue
            </p>
          ) : hasRejectedAssumptions ? (
            <div className="assumptions-footer-actions">
              <p className="assumptions-footer-hint">
                Rejected assumptions require a revised proposal.
              </p>
              {canRequestRevision && onRequestRevision && (
                <button
                  type="button"
                  onClick={onRequestRevision}
                  className="assumptions-revise"
                >
                  Request revision
                </button>
              )}
            </div>
          ) : (
            <div className="assumptions-footer-actions">
              {canRequestRevision && onRequestRevision && (
                <button
                  type="button"
                    onClick={onRequestRevision}
                    className="assumptions-revise"
                  >
                    Request revision
                  </button>
                )}
                <button
                  type="button"
                  onClick={onConfirm}
                  className="assumptions-confirm"
                >
                  Continue with Execution
                  {acceptedCount > 0 && ` (${acceptedCount} accepted)`}
                </button>
              </div>
            )
          ) : (
            <p className="assumptions-footer-hint">
              Status: {getRoundStatusLabel(currentRound.status)}
            </p>
          )}
        </footer>
      )}

      <style jsx>{`
        .assumptions-panel {
          --panel-bg: #0b0f16;
          --panel-border: #252b36;
          --panel-muted: #9ca3af;
          --panel-muted-strong: #e2e8f0;
          --panel-surface: #111827;
          --panel-surface-strong: #0f172a;
          --panel-success: #22c55e;
          --panel-danger: #ef4444;
          --panel-warning: #f59e0b;
          --panel-accent: #38bdf8;
          background: radial-gradient(
              circle at top left,
              rgba(59, 130, 246, 0.18),
              transparent 45%
            ),
            radial-gradient(
              circle at bottom right,
              rgba(34, 197, 94, 0.12),
              transparent 40%
            ),
            var(--panel-bg);
          border: 1px solid var(--panel-border);
          border-radius: 0.9rem;
          box-shadow: 0 18px 42px rgba(0, 0, 0, 0.45);
          color: var(--panel-muted-strong);
          font-family: var(--font-geist-sans, "Geist", "Segoe UI", sans-serif);
          overflow: hidden;
          width: 100%;
        }

        .assumptions-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 1rem;
          padding: 0.85rem 1rem 0.75rem;
          border-bottom: 1px solid var(--panel-border);
          background: rgba(15, 23, 42, 0.85);
        }

        .assumptions-header-actions {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .assumptions-title {
          margin: 0;
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.18em;
          color: var(--panel-muted);
        }

        .assumptions-subtitle {
          margin-top: 0.2rem;
          font-size: 0.85rem;
          color: #e2e8f0;
        }

        .assumptions-explain-toggle {
          background-color: rgba(15, 23, 42, 0.6);
          border: 1px solid var(--panel-border);
          color: var(--panel-muted);
          font-size: 0.6875rem;
          font-weight: 600;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          padding: 0.35rem 0.75rem;
          border-radius: 999px;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .assumptions-explain-toggle:hover {
          border-color: rgba(56, 189, 248, 0.6);
          color: #e0f2fe;
          box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.1);
        }

        .assumptions-dismiss {
          background-color: rgba(15, 23, 42, 0.6);
          border: 1px solid var(--panel-border);
          color: var(--panel-muted);
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          padding: 0.35rem 0.75rem;
          border-radius: 999px;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .assumptions-dismiss:hover {
          border-color: rgba(148, 163, 184, 0.6);
          color: #e2e8f0;
        }

        .assumptions-body {
          padding: 1rem;
          display: flex;
          flex-direction: column;
          gap: 0.9rem;
          max-height: min(60vh, 520px);
          overflow-y: auto;
        }

        .assumptions-stage {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .assumptions-stage-label,
        .assumptions-intent-label,
        .assumptions-confidence-label,
        .assumptions-reasoning-label,
        .assumptions-alternatives-label,
        .assumptions-clarify-label {
          font-size: 0.6875rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--panel-muted);
        }

        .assumptions-command {
          background-color: rgba(15, 23, 42, 0.7);
          border: 1px solid var(--panel-border);
          border-radius: 0.6rem;
          padding: 0.65rem 0.75rem;
          color: #f8fafc;
          font-size: 0.95rem;
          line-height: 1.5;
        }

        .assumptions-attachments {
          display: flex;
          flex-wrap: wrap;
          gap: 0.35rem;
        }

        .assumptions-attachment {
          font-size: 0.75rem;
          padding: 0.2rem 0.55rem;
          border-radius: 999px;
          background-color: rgba(15, 23, 42, 0.9);
          border: 1px solid var(--panel-border);
          color: var(--panel-muted-strong);
        }

        .assumptions-overview {
          display: grid;
          grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
          gap: 1rem;
          padding: 0.75rem;
          background-color: rgba(15, 23, 42, 0.55);
          border: 1px solid var(--panel-border);
          border-radius: 0.65rem;
        }

        .assumptions-intent-value {
          margin-top: 0.35rem;
          font-size: 1rem;
          font-weight: 600;
          color: #f8fafc;
        }

        .assumptions-intent-description {
          margin-top: 0.35rem;
          font-size: 0.8125rem;
          color: var(--panel-muted);
          line-height: 1.5;
        }

        .assumptions-confidence {
          display: flex;
          flex-direction: column;
          gap: 0.4rem;
          align-items: flex-start;
        }

        .assumptions-confidence-meter {
          width: 100%;
          height: 0.45rem;
          background-color: rgba(15, 23, 42, 0.85);
          border-radius: 999px;
          border: 1px solid var(--panel-border);
          overflow: hidden;
        }

        .assumptions-confidence-fill {
          height: 100%;
          background: linear-gradient(90deg, #38bdf8, #22c55e);
          border-radius: 999px;
        }

        .assumptions-confidence-value {
          font-size: 0.8125rem;
          font-weight: 600;
          color: #e2e8f0;
        }

        .assumptions-explain {
          display: grid;
          gap: 0.75rem;
          padding: 0.75rem;
          background-color: rgba(15, 23, 42, 0.6);
          border: 1px solid var(--panel-border);
          border-radius: 0.65rem;
        }

        .assumptions-reasoning-text {
          margin: 0.35rem 0 0;
          font-size: 0.875rem;
          line-height: 1.6;
          color: #cbd5f5;
        }

        .assumptions-alternatives-list {
          list-style: none;
          margin: 0.5rem 0 0;
          padding: 0;
          display: grid;
          gap: 0.5rem;
        }

        .assumptions-alternative-item {
          border: 1px solid var(--panel-border);
          background-color: rgba(15, 23, 42, 0.7);
          border-radius: 0.5rem;
          padding: 0.5rem 0.75rem;
        }

        .assumptions-alternative-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.5rem;
        }

        .assumptions-alternative-name {
          font-size: 0.875rem;
          font-weight: 600;
          color: #f8fafc;
        }

        .assumptions-alternative-confidence {
          font-size: 0.75rem;
          color: var(--panel-muted);
        }

        .assumptions-alternative-description {
          margin: 0.35rem 0 0;
          font-size: 0.8125rem;
          color: var(--panel-muted);
          line-height: 1.4;
        }

        .assumptions-summary {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 0.75rem;
          padding: 0.6rem 0.75rem;
          background-color: var(--panel-surface);
          border: 1px solid var(--panel-border);
          border-radius: 0.6rem;
        }

        .assumptions-count {
          font-size: 0.875rem;
          color: var(--panel-muted);
        }

        .assumptions-stat {
          font-size: 0.875rem;
          padding: 0.125rem 0.5rem;
          border-radius: 0.25rem;
        }

        .assumptions-stat-accepted {
          background-color: rgba(34, 197, 94, 0.15);
          color: var(--panel-success);
        }

        .assumptions-stat-rejected {
          background-color: rgba(239, 68, 68, 0.15);
          color: var(--panel-danger);
        }

        .assumptions-list {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .assumption-item {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
          padding: 1rem;
          background-color: var(--panel-surface);
          border: 1px solid var(--panel-border);
          border-radius: 0.5rem;
          transition: all 0.15s ease;
          animation: assumption-fade 0.25s ease both;
        }

        .assumption-item-pending:hover {
          border-color: rgba(56, 189, 248, 0.4);
          box-shadow: 0 8px 18px rgba(15, 23, 42, 0.35);
        }

        .assumption-item-accepted {
          border-color: rgba(34, 197, 94, 0.35);
          background-color: rgba(34, 197, 94, 0.08);
        }

        .assumption-item-rejected {
          border-color: rgba(239, 68, 68, 0.35);
          background-color: rgba(239, 68, 68, 0.08);
          opacity: 0.6;
        }

        .assumption-category {
          display: inline-block;
          font-size: 0.75rem;
          font-weight: 600;
          padding: 0.125rem 0.5rem;
          border-radius: 0.25rem;
          color: #fff;
          text-transform: uppercase;
          letter-spacing: 0.025em;
          width: fit-content;
        }

        .assumption-content {
          flex: 1;
        }

        .assumption-edit {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .assumption-edit-input {
          width: 100%;
          resize: vertical;
          padding: 0.6rem 0.75rem;
          font-size: 0.9rem;
          line-height: 1.5;
          border-radius: 0.5rem;
          border: 1px solid var(--panel-border);
          background-color: rgba(15, 23, 42, 0.7);
          color: #f8fafc;
          outline: none;
          transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }

        .assumption-edit-input:focus {
          border-color: rgba(56, 189, 248, 0.65);
          box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.15);
        }

        .assumption-text {
          margin: 0 0 0.5rem;
          color: #f1f5f9;
          font-size: 0.9375rem;
          line-height: 1.5;
        }

        .assumption-explanation {
          margin: 0 0 0.5rem;
          color: var(--panel-muted);
          font-size: 0.875rem;
          font-style: italic;
        }

        .assumption-confidence {
          font-size: 0.75rem;
          color: var(--panel-muted);
        }

        .assumption-actions {
          display: flex;
          gap: 0.5rem;
          justify-content: flex-end;
        }

        .assumption-btn {
          padding: 0.5rem 1rem;
          font-size: 0.875rem;
          font-weight: 500;
          border-radius: 0.375rem;
          cursor: pointer;
          transition: all 0.15s ease;
          border: 1px solid transparent;
        }

        .assumption-btn-reject {
          background-color: rgba(15, 23, 42, 0.75);
          color: var(--panel-muted);
          border-color: var(--panel-border);
        }

        .assumption-btn-reject:hover:not(:disabled) {
          background-color: rgba(239, 68, 68, 0.15);
          border-color: rgba(239, 68, 68, 0.6);
          color: #fee2e2;
        }

        .assumption-btn-edit {
          background-color: rgba(15, 23, 42, 0.75);
          color: var(--panel-muted);
          border-color: var(--panel-border);
        }

        .assumption-btn-edit:hover:not(:disabled) {
          background-color: rgba(56, 189, 248, 0.12);
          border-color: rgba(56, 189, 248, 0.6);
          color: #e0f2fe;
        }

        .assumption-btn-confirm {
          background-color: rgba(15, 23, 42, 0.75);
          color: var(--panel-muted);
          border-color: var(--panel-border);
        }

        .assumption-btn-confirm:hover:not(:disabled) {
          background-color: rgba(34, 197, 94, 0.16);
          border-color: rgba(34, 197, 94, 0.6);
          color: #dcfce7;
        }

        .assumption-btn-save {
          background-color: rgba(34, 197, 94, 0.18);
          color: #dcfce7;
          border-color: rgba(34, 197, 94, 0.6);
        }

        .assumption-btn-save:hover:not(:disabled) {
          background-color: rgba(34, 197, 94, 0.28);
          border-color: rgba(34, 197, 94, 0.75);
        }

        .assumption-btn-cancel {
          background-color: rgba(15, 23, 42, 0.75);
          color: var(--panel-muted);
          border-color: var(--panel-border);
        }

        .assumption-btn-cancel:hover:not(:disabled) {
          background-color: rgba(148, 163, 184, 0.12);
          border-color: rgba(148, 163, 184, 0.6);
          color: #e2e8f0;
        }

        .assumption-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .assumption-status {
          font-size: 0.875rem;
          font-weight: 500;
          text-align: right;
        }

        .assumption-status-accepted {
          color: var(--panel-success);
        }

        .assumption-status-rejected {
          color: var(--panel-danger);
        }

        .assumptions-clarify-list {
          margin: 0;
          padding: 0;
          list-style: none;
          display: grid;
          gap: 0.45rem;
        }

        .assumptions-clarify-item {
          padding: 0.6rem 0.75rem;
          border-radius: 0.5rem;
          background: rgba(15, 23, 42, 0.65);
          border: 1px solid var(--panel-border);
          font-size: 0.9rem;
          color: #e2e8f0;
        }

        .assumptions-clarify-alternatives {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .assumptions-clarify-options {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
        }

        .assumptions-clarify-option {
          background-color: rgba(15, 23, 42, 0.75);
          border: 1px solid var(--panel-border);
          color: var(--panel-muted-strong);
          font-size: 0.75rem;
          padding: 0.35rem 0.65rem;
          border-radius: 999px;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .assumptions-clarify-option:hover:not(:disabled) {
          border-color: rgba(56, 189, 248, 0.6);
          color: #e0f2fe;
        }

        .assumptions-clarify-option:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .assumptions-clarify-input {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          margin-top: 0.25rem;
        }

        .assumptions-clarify-textarea {
          width: 100%;
          resize: vertical;
          padding: 0.6rem 0.75rem;
          font-size: 0.875rem;
          line-height: 1.5;
          border-radius: 0.5rem;
          border: 1px solid var(--panel-border);
          background-color: rgba(15, 23, 42, 0.7);
          color: #f8fafc;
          outline: none;
        }

        .assumptions-clarify-actions {
          display: flex;
          justify-content: flex-end;
        }

        .assumptions-clarify-submit {
          background: linear-gradient(135deg, #38bdf8, #2563eb);
          border: none;
          color: #fff;
          padding: 0.5rem 1rem;
          border-radius: 0.5rem;
          font-size: 0.85rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .assumptions-clarify-submit:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .assumptions-footer {
          padding: 0.85rem 1rem 1rem;
          border-top: 1px solid var(--panel-border);
          background-color: var(--panel-surface-strong);
        }

        .assumptions-footer-hint {
          margin: 0;
          font-size: 0.875rem;
          color: var(--panel-muted);
          text-align: center;
        }

        .assumptions-footer-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
        }

        .assumptions-revise {
          flex: 1;
          padding: 0.75rem 1rem;
          font-size: 0.9rem;
          font-weight: 600;
          color: #e2e8f0;
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid var(--panel-border);
          border-radius: 0.5rem;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .assumptions-revise:hover {
          border-color: rgba(148, 163, 184, 0.6);
          color: #f8fafc;
        }

        .assumptions-confirm {
          flex: 2;
          padding: 0.75rem 1rem;
          font-size: 0.95rem;
          font-weight: 600;
          color: #fff;
          background: linear-gradient(135deg, #3b82f6, #2563eb);
          border: none;
          border-radius: 0.5rem;
          cursor: pointer;
          transition: all 0.15s ease;
          box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2);
        }

        .assumptions-confirm:hover:not(:disabled) {
          background: linear-gradient(135deg, #2563eb, #1d4ed8);
          box-shadow: 0 6px 8px rgba(37, 99, 235, 0.3);
          transform: translateY(-1px);
        }

        .assumptions-confirm:disabled {
          opacity: 0.5;
          cursor: not-allowed;
          transform: none;
        }

        .assumptions-history {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .assumptions-history-list {
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
        }

        .assumptions-history-item {
          border: 1px solid var(--panel-border);
          border-radius: 0.6rem;
          background-color: rgba(15, 23, 42, 0.6);
          overflow: hidden;
        }

        .assumptions-history-summary {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 0.5rem;
          padding: 0.6rem 0.75rem;
          cursor: pointer;
          list-style: none;
          font-size: 0.85rem;
          color: #e2e8f0;
        }

        .assumptions-history-summary::-webkit-details-marker {
          display: none;
        }

        .assumptions-history-title {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .assumptions-history-time {
          font-size: 0.75rem;
          color: var(--panel-muted);
        }

        .assumptions-history-status {
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }

        .assumptions-history-status.status-reviewing {
          color: var(--panel-accent);
        }

        .assumptions-history-status.status-resolved,
        .assumptions-history-status.status-executed {
          color: var(--panel-success);
        }

        .assumptions-history-status.status-superseded,
        .assumptions-history-status.status-dismissed {
          color: var(--panel-muted);
        }

        .assumptions-history-content {
          padding: 0.6rem 0.75rem 0.75rem;
          border-top: 1px solid var(--panel-border);
          display: grid;
          gap: 0.5rem;
          font-size: 0.85rem;
        }

        .assumptions-history-command {
          color: #f8fafc;
        }

        .assumptions-history-intent,
        .assumptions-history-clarification {
          color: var(--panel-muted);
        }

        .assumptions-history-assumptions {
          list-style: none;
          margin: 0;
          padding: 0;
          display: grid;
          gap: 0.35rem;
        }

        .assumptions-history-assumption {
          display: flex;
          justify-content: space-between;
          gap: 0.5rem;
          padding: 0.4rem 0.5rem;
          border-radius: 0.45rem;
          background: rgba(15, 23, 42, 0.65);
          border: 1px solid var(--panel-border);
        }

        .assumptions-history-assumption-status {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: var(--panel-muted);
        }

        .assumptions-history-assumption-status.status-accepted {
          color: var(--panel-success);
        }

        .assumptions-history-assumption-status.status-rejected {
          color: var(--panel-danger);
        }

        .assumptions-history-empty {
          font-size: 0.8rem;
          color: var(--panel-muted);
        }

        .assumptions-empty {
          padding: 0.75rem;
          border-radius: 0.6rem;
          border: 1px dashed var(--panel-border);
          color: var(--panel-muted);
          text-align: center;
          font-size: 0.85rem;
        }

        @keyframes assumption-fade {
          from {
            opacity: 0;
            transform: translateY(6px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @media (max-width: 640px) {
          .assumptions-body {
            padding: 0.85rem;
            max-height: min(60vh, 420px);
          }

          .assumptions-overview {
            grid-template-columns: 1fr;
          }

          .assumption-actions {
            flex-direction: column;
          }

          .assumption-btn {
            width: 100%;
          }

          .assumptions-footer-actions {
            flex-direction: column;
          }

          .assumptions-revise,
          .assumptions-confirm {
            width: 100%;
          }
        }
      `}</style>
    </section>
  );
}
