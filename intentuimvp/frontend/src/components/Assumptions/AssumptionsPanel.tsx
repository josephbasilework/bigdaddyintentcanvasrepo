"use client";

import type { Assumption, AssumptionsPanelProps } from "./types";

/**
 * AssumptionsPanel displays agent-extracted assumptions for user confirmation.
 *
 * Shows each assumption with accept/reject buttons. Users must resolve all
 * assumptions before proceeding with action execution.
 */
export function AssumptionsPanel({
  assumptions,
  onAccept,
  onReject,
  onConfirm,
  onDismiss,
}: AssumptionsPanelProps) {
  // Filter assumptions by status
  const pendingAssumptions = assumptions.filter((a) => a.status === "pending");
  const acceptedCount = assumptions.filter((a) => a.status === "accepted").length;
  const rejectedCount = assumptions.filter((a) => a.status === "rejected").length;
  const totalCount = assumptions.length;

  // Can confirm when all assumptions are resolved (accepted or rejected)
  const allResolved = pendingAssumptions.length === 0;

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
      <div className="assumptions-panel">
        {/* Header */}
        <div className="assumptions-header">
          <h2 className="assumptions-title">
            {pendingAssumptions.length > 0
              ? "Please Review These Assumptions"
              : "All Assumptions Resolved"}
          </h2>
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
          {assumptions.map((assumption) => (
            <div
              key={assumption.id}
              className={`assumption-item assumption-item-${assumption.status}`}
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
            background-color: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2000;
            padding: 1rem;
            backdrop-filter: blur(4px);
          }

          .assumptions-panel {
            background-color: #1a1a1a;
            border: 1px solid #333;
            border-radius: 0.75rem;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5),
              0 8px 10px -6px rgba(0, 0, 0, 0.5);
            max-width: 600px;
            width: 100%;
            max-height: 80vh;
            display: flex;
            flex-direction: column;
          }

          .assumptions-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1.25rem 1.5rem 1rem;
            border-bottom: 1px solid #333;
          }

          .assumptions-title {
            margin: 0;
            font-size: 1.125rem;
            font-weight: 600;
            color: #e5e5e5;
          }

          .assumptions-dismiss {
            background: none;
            border: none;
            color: #666;
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
            background-color: #262626;
            color: #a3a3a3;
          }

          .assumptions-summary {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem 1.5rem;
            background-color: #0f0f0f;
            border-bottom: 1px solid #333;
          }

          .assumptions-count {
            font-size: 0.875rem;
            color: #a3a3a3;
          }

          .assumptions-stat {
            font-size: 0.875rem;
            padding: 0.125rem 0.5rem;
            border-radius: 0.25rem;
          }

          .assumptions-stat-accepted {
            background-color: rgba(34, 197, 94, 0.15);
            color: #22c55e;
          }

          .assumptions-stat-rejected {
            background-color: rgba(239, 68, 68, 0.15);
            color: #ef4444;
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
            background-color: #0f0f0f;
            border: 1px solid #333;
            border-radius: 0.5rem;
            margin-bottom: 0.75rem;
            transition: all 0.15s ease;
          }

          .assumption-item:last-child {
            margin-bottom: 0;
          }

          .assumption-item-pending:hover {
            border-color: #444;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
          }

          .assumption-item-accepted {
            border-color: rgba(34, 197, 94, 0.3);
            background-color: rgba(34, 197, 94, 0.05);
          }

          .assumption-item-rejected {
            border-color: rgba(239, 68, 68, 0.3);
            background-color: rgba(239, 68, 68, 0.05);
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
            color: #e5e5e5;
            font-size: 0.9375rem;
            line-height: 1.5;
          }

          .assumption-explanation {
            margin: 0 0 0.5rem;
            color: #737373;
            font-size: 0.875rem;
            font-style: italic;
          }

          .assumption-confidence {
            font-size: 0.75rem;
            color: #525252;
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
            background-color: #262626;
            color: #a3a3a3;
            border-color: #404040;
          }

          .assumption-btn-reject:hover:not(:disabled) {
            background-color: #292524;
            border-color: #ef4444;
            color: #ef4444;
          }

          .assumption-btn-accept {
            background-color: #262626;
            color: #a3a3a3;
            border-color: #404040;
          }

          .assumption-btn-accept:hover:not(:disabled) {
            background-color: #14532d;
            border-color: #22c55e;
            color: #22c55e;
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
            color: #22c55e;
          }

          .assumption-status-rejected {
            color: #ef4444;
          }

          .assumptions-footer {
            padding: 1rem 1.5rem 1.25rem;
            border-top: 1px solid #333;
            background-color: #0f0f0f;
            border-radius: 0 0 0.75rem 0.75rem;
          }

          .assumptions-footer-hint {
            margin: 0;
            font-size: 0.875rem;
            color: #737373;
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

          @media (max-width: 640px) {
            .assumptions-panel {
              max-height: 90vh;
            }

            .assumptions-header,
            .assumptions-list,
            .assumptions-footer {
              padding-left: 1rem;
              padding-right: 1rem;
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
