"use client";

import { useId, useState } from "react";
import type { Assumption, AssumptionsPanelProps } from "./types";

/**
 * AssumptionsPanel displays agent-extracted assumptions for user confirmation.
 *
 * Shows each assumption with accept/reject buttons. Users must resolve all
 * assumptions before proceeding with action execution.
 */
export function AssumptionsPanel({
  assumptions,
  assumptionSet,
  onAccept,
  onReject,
  onConfirm,
  onDismiss,
}: AssumptionsPanelProps) {
  const titleId = useId();
  const explainId = useId();
  const [showExplain, setShowExplain] = useState(false);
  // Filter assumptions by status
  const pendingAssumptions = assumptions.filter((a) => a.status === "pending");
  const acceptedCount = assumptions.filter((a) => a.status === "accepted").length;
  const rejectedCount = assumptions.filter((a) => a.status === "rejected").length;
  const totalCount = assumptions.length;

  // Can confirm when all assumptions are resolved (accepted or rejected)
  const allResolved = pendingAssumptions.length === 0;
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
    Boolean(assumptionSet?.intent) ||
    Boolean(assumptionSet?.intentDescription) ||
    intentConfidencePercent !== null;

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

  if (assumptions.length === 0) {
    return null;
  }

  return (
    <div className="assumptions-panel-overlay">
      <div
        className="assumptions-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        {/* Header */}
        <div className="assumptions-header">
          <div className="assumptions-header-content">
            <h2 className="assumptions-title" id={titleId}>
              {pendingAssumptions.length > 0
                ? "Please Review These Assumptions"
                : "All Assumptions Resolved"}
            </h2>
          </div>
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
            {onDismiss && (
              <button
                type="button"
                onClick={onDismiss}
                className="assumptions-dismiss"
                aria-label="Dismiss"
              >
                ×
              </button>
            )}
          </div>
        </div>

        {hasIntentSummary && (
          <div className="assumptions-overview">
            <div className="assumptions-intent">
              <span className="assumptions-intent-label">Primary intent</span>
              {assumptionSet?.intent && (
                <div className="assumptions-intent-value">{assumptionSet.intent}</div>
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
            {assumptionSet?.alternatives && assumptionSet.alternatives.length > 0 && (
              <div className="assumptions-alternatives">
                <span className="assumptions-alternatives-label">
                  Alternate interpretations
                </span>
                <ul className="assumptions-alternatives-list">
                  {assumptionSet.alternatives.map((alternative) => (
                    <li key={alternative.name} className="assumptions-alternative-item">
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

        {/* Summary */}
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

        {/* Assumptions List */}
        <div className="assumptions-list">
          {assumptions.map((assumption, index) => (
            <div
              key={assumption.id}
              className={`assumption-item assumption-item-${assumption.status}`}
              style={{ animationDelay: `${index * 60}ms` }}
            >
              {/* Category Badge */}
              <div
                className="assumption-category"
                style={{ backgroundColor: getCategoryColor(assumption.category) }}
              >
                {getCategoryLabel(assumption.category)}
              </div>

              {/* Assumption Text */}
              <div className="assumption-content">
                <p className="assumption-text">{assumption.text}</p>
                {assumption.explanation && (
                  <p className="assumption-explanation">{assumption.explanation}</p>
                )}
                <div className="assumption-confidence">
                  Confidence: {Math.round(assumption.confidence * 100)}%
                </div>
              </div>

              {/* Action Buttons */}
              {assumption.status === "pending" && (
                <div className="assumption-actions">
                  <button
                    type="button"
                    onClick={() => onReject(assumption.id)}
                    className="assumption-btn assumption-btn-reject"
                    disabled={assumption.status !== "pending"}
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    onClick={() => onAccept(assumption.id)}
                    className="assumption-btn assumption-btn-accept"
                    disabled={assumption.status !== "pending"}
                  >
                    Accept
                  </button>
                </div>
              )}

              {/* Status Indicator */}
              {assumption.status !== "pending" && (
                <div
                  className={`assumption-status assumption-status-${assumption.status}`}
                >
                  {assumption.status === "accepted" ? "✓ Accepted" : "✗ Rejected"}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Footer with Confirm Button */}
        <div className="assumptions-footer">
          {!allResolved ? (
            <p className="assumptions-footer-hint">
              Please accept or reject all assumptions to continue
            </p>
          ) : (
            <button
              type="button"
              onClick={onConfirm}
              className="assumptions-confirm"
              disabled={!allResolved}
            >
              Continue with Execution
              {acceptedCount > 0 && ` (${acceptedCount} accepted)`}
            </button>
          )}
        </div>

        <style jsx>{`
          .assumptions-panel-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(
                circle at top,
                rgba(15, 23, 42, 0.55),
                transparent 65%
              ),
              rgba(4, 6, 10, 0.82);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2000;
            padding: 1rem;
            backdrop-filter: blur(6px);
            animation: overlay-fade 0.2s ease-out;
          }

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
            border-radius: 0.75rem;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5),
              0 8px 10px -6px rgba(0, 0, 0, 0.5);
            max-width: 600px;
            width: 100%;
            max-height: 80vh;
            display: flex;
            flex-direction: column;
            color: var(--panel-muted-strong);
            font-family: var(--font-geist-sans, "Geist", "Segoe UI", sans-serif);
            animation: panel-rise 0.25s ease-out;
          }

          .assumptions-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            padding: 1.25rem 1.5rem 0.75rem;
            border-bottom: 1px solid var(--panel-border);
          }

          .assumptions-header-actions {
            display: flex;
            align-items: center;
            gap: 0.5rem;
          }

          .assumptions-title {
            margin: 0;
            font-size: 1.125rem;
            font-weight: 600;
            color: #f8fafc;
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
            background: none;
            border: none;
            color: var(--panel-muted);
            font-size: 1.5rem;
            cursor: pointer;
            padding: 0;
            width: 2rem;
            height: 2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 0.25rem;
            transition: all 0.15s ease;
          }

          .assumptions-dismiss:hover {
            background-color: rgba(15, 23, 42, 0.6);
            color: #e2e8f0;
          }

          .assumptions-header-content {
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
          }

          .assumptions-overview {
            display: grid;
            grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
            gap: 1.5rem;
            padding: 0.75rem 1.5rem 1rem;
            background-color: rgba(15, 23, 42, 0.55);
            border-bottom: 1px solid var(--panel-border);
          }

          .assumptions-intent-label,
          .assumptions-confidence-label,
          .assumptions-reasoning-label,
          .assumptions-alternatives-label {
            font-size: 0.6875rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--panel-muted);
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
            padding: 0.75rem 1.5rem 1rem;
            background-color: rgba(15, 23, 42, 0.6);
            border-bottom: 1px solid var(--panel-border);
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
            padding: 0.75rem 1.5rem;
            background-color: var(--panel-surface);
            border-bottom: 1px solid var(--panel-border);
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
            padding: 1rem 1.5rem;
            overflow-y: auto;
            flex: 1;
          }

          .assumption-item {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            padding: 1rem;
            background-color: var(--panel-surface);
            border: 1px solid var(--panel-border);
            border-radius: 0.5rem;
            margin-bottom: 0.75rem;
            transition: all 0.15s ease;
            animation: assumption-fade 0.25s ease both;
          }

          .assumption-item:last-child {
            margin-bottom: 0;
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

          .assumption-btn-accept {
            background-color: rgba(15, 23, 42, 0.75);
            color: var(--panel-muted);
            border-color: var(--panel-border);
          }

          .assumption-btn-accept:hover:not(:disabled) {
            background-color: rgba(34, 197, 94, 0.16);
            border-color: rgba(34, 197, 94, 0.6);
            color: #dcfce7;
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

          .assumptions-footer {
            padding: 1rem 1.5rem 1.25rem;
            border-top: 1px solid var(--panel-border);
            background-color: var(--panel-surface-strong);
            border-radius: 0 0 0.75rem 0.75rem;
          }

          .assumptions-footer-hint {
            margin: 0;
            font-size: 0.875rem;
            color: var(--panel-muted);
            text-align: center;
          }

          .assumptions-confirm {
            width: 100%;
            padding: 0.75rem 1.5rem;
            font-size: 1rem;
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

          @keyframes overlay-fade {
            from {
              opacity: 0;
            }
            to {
              opacity: 1;
            }
          }

          @keyframes panel-rise {
            from {
              opacity: 0;
              transform: translateY(10px) scale(0.98);
            }
            to {
              opacity: 1;
              transform: translateY(0) scale(1);
            }
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
            .assumptions-panel {
              max-height: 90vh;
            }

            .assumptions-header,
            .assumptions-overview,
            .assumptions-explain,
            .assumptions-summary,
            .assumptions-list,
            .assumptions-footer {
              padding-left: 1rem;
              padding-right: 1rem;
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
          }
        `}</style>
      </div>
    </div>
  );
}
