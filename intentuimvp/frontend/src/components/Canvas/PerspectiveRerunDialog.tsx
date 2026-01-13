"use client";

import { useState, useCallback } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Available perspectives for multi-judge compute (FR-012).
 * These map to the PerspectiveAgent's default perspective types.
 */
export const AVAILABLE_PERSPECTIVES = [
  { id: "skeptic", label: "Skeptic", description: "Challenges claims, looks for weak evidence" },
  { id: "advocate", label: "Advocate", description: "Steelmans the argument, finds supporting evidence" },
  { id: "synthesizer", label: "Synthesizer", description: "Identifies common ground and key tensions" },
  { id: "technical", label: "Technical", description: "Evaluates from an engineering/technical perspective" },
  { id: "business", label: "Business", description: "Analyzes business impact and ROI" },
  { id: "user", label: "User", description: "Considers end-user needs and experience" },
  { id: "ethical", label: "Ethical", description: "Examines ethical implications and concerns" },
  { id: "historical", label: "Historical", description: "Contextualizes within historical patterns" },
] as const;

export type PerspectiveId = (typeof AVAILABLE_PERSPECTIVES)[number]["id"];

export interface PerspectiveRerunDialogProps {
  /** Whether the dialog is open */
  isOpen: boolean;
  /** Callback when dialog should close */
  onClose: () => void;
  /** Topic to analyze */
  topic: string;
  /** Currently selected perspectives (for showing what's already used) */
  currentPerspectives?: PerspectiveId[];
  /** Optional node ID to link results to */
  targetNodeId?: string;
  /** Callback when a new job is successfully triggered */
  onJobCreated?: (jobId: string) => void;
}

/**
 * PerspectiveRerunDialog - Dialog for configuring and triggering rerun with more compute.
 *
 * Part of FR-012: Multi-Judge Compute. Allows users to configure additional perspectives
 * for re-running perspective analysis with more compute (more critics / deeper passes).
 */
export function PerspectiveRerunDialog({
  isOpen,
  onClose,
  topic,
  currentPerspectives = [],
  targetNodeId,
  onJobCreated,
}: PerspectiveRerunDialogProps) {
  const [selectedPerspectives, setSelectedPerspectives] = useState<Set<PerspectiveId>>(
    new Set(currentPerspectives.length > 0 ? currentPerspectives : ["skeptic", "advocate", "synthesizer"])
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const togglePerspective = useCallback((perspectiveId: PerspectiveId) => {
    setSelectedPerspectives((prev) => {
      const next = new Set(prev);
      if (next.has(perspectiveId)) {
        next.delete(perspectiveId);
      } else {
        next.add(perspectiveId);
      }
      return next;
    });
  }, []);

  const handleSubmit = useCallback(async () => {
    if (selectedPerspectives.size === 0) {
      setError("Please select at least one perspective");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const perspectivesArray = Array.from(selectedPerspectives);
      const body = {
        topic,
        perspectives: perspectivesArray,
        input_refs: targetNodeId ? [parseInt(targetNodeId.replace(/\D/g, "") || "0", 10)] : undefined,
      };

      const response = await fetch(`${API_BASE_URL}/api/jobs/perspective-analysis?user_id=user-1`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to trigger job (${response.status})`);
      }

      const data = await response.json();
      onJobCreated?.(data.job_id);
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to trigger perspective analysis";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [selectedPerspectives, topic, targetNodeId, onJobCreated, onClose]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        handleSubmit();
      }
      if (e.key === "Escape") {
        onClose();
      }
    },
    [handleSubmit, onClose]
  );

  if (!isOpen) return null;

  const perspectiveCount = selectedPerspectives.size;
  const computeLevel =
    perspectiveCount <= 2 ? "Light" : perspectiveCount <= 4 ? "Medium" : "Heavy";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="perspective-rerun-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10010,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "rgba(0, 0, 0, 0.5)",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      onKeyDown={handleKeyDown}
    >
      <div
        style={{
          backgroundColor: "#0f172a",
          border: "1px solid rgba(148, 163, 184, 0.3)",
          borderRadius: "16px",
          padding: "24px",
          maxWidth: "480px",
          width: "calc(100% - 32px)",
          maxHeight: "90vh",
          overflow: "auto",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.5)",
        }}
      >
        {/* Header */}
        <div style={{ marginBottom: "20px" }}>
          <h2
            id="perspective-rerun-title"
            style={{
              fontSize: "18px",
              fontWeight: 600,
              color: "#e2e8f0",
              margin: 0,
            }}
          >
            Rerun with More Compute
          </h2>
          <p
            style={{
              fontSize: "13px",
              color: "#94a3b8",
              margin: "8px 0 0 0",
              lineHeight: 1.5,
            }}
          >
            Configure additional perspectives for deeper multi-judge analysis.
          </p>
        </div>

        {/* Topic display */}
        <div
          style={{
            backgroundColor: "rgba(15, 23, 42, 0.8)",
            border: "1px solid rgba(148, 163, 184, 0.2)",
            borderRadius: "8px",
            padding: "12px",
            marginBottom: "20px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#64748b", marginBottom: "4px" }}>
            TOPIC
          </div>
          <div
            style={{
              fontSize: "14px",
              color: "#e2e8f0",
              fontWeight: 500,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
            title={topic}
          >
            {topic}
          </div>
        </div>

        {/* Compute level indicator */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "16px",
            padding: "8px 12px",
            backgroundColor:
              computeLevel === "Light"
                ? "rgba(148, 163, 184, 0.1)"
                : computeLevel === "Medium"
                  ? "rgba(59, 130, 246, 0.15)"
                  : "rgba(168, 85, 247, 0.15)",
            border: "1px solid",
            borderColor:
              computeLevel === "Light"
                ? "rgba(148, 163, 184, 0.3)"
                : computeLevel === "Medium"
                  ? "rgba(59, 130, 246, 0.4)"
                  : "rgba(168, 85, 247, 0.4)",
            borderRadius: "8px",
          }}
        >
          <span style={{ fontSize: "12px", color: "#94a3b8" }}>Compute Level</span>
          <span
            style={{
              fontSize: "12px",
              fontWeight: 600,
              color:
                computeLevel === "Light"
                  ? "#94a3b8"
                  : computeLevel === "Medium"
                    ? "#60a5fa"
                    : "#c084fc",
            }}
          >
            {computeLevel} ({perspectiveCount} perspective{perspectiveCount !== 1 ? "s" : ""})
          </span>
        </div>

        {/* Perspectives selection */}
        <div style={{ marginBottom: "20px" }}>
          <div
            style={{
              fontSize: "11px",
              color: "#64748b",
              marginBottom: "8px",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            Select Perspectives
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap: "8px",
            }}
          >
            {AVAILABLE_PERSPECTIVES.map((perspective) => {
              const isSelected = selectedPerspectives.has(perspective.id);
              return (
                <button
                  key={perspective.id}
                  type="button"
                  onClick={() => togglePerspective(perspective.id)}
                  style={{
                    backgroundColor: isSelected
                      ? "rgba(59, 130, 246, 0.2)"
                      : "rgba(15, 23, 42, 0.6)",
                    border: "1px solid",
                    borderColor: isSelected ? "#3b82f6" : "rgba(148, 163, 184, 0.2)",
                    borderRadius: "8px",
                    padding: "10px 12px",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <div
                      style={{
                        width: "16px",
                        height: "16px",
                        borderRadius: "4px",
                        border: "2px solid",
                        borderColor: isSelected ? "#3b82f6" : "#64748b",
                        backgroundColor: isSelected ? "#3b82f6" : "transparent",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {isSelected && (
                        <svg
                          width="10"
                          height="10"
                          viewBox="0 0 10 10"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path
                            d="M8 2L3.5 7.5L2 6"
                            stroke="white"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </div>
                    <div>
                      <div
                        style={{
                          fontSize: "13px",
                          fontWeight: 500,
                          color: isSelected ? "#e2e8f0" : "#94a3b8",
                        }}
                      >
                        {perspective.label}
                      </div>
                      <div
                        style={{
                          fontSize: "11px",
                          color: "#64748b",
                          marginTop: "2px",
                        }}
                      >
                        {perspective.description}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div
            role="alert"
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.4)",
              borderRadius: "8px",
              color: "#fecaca",
              fontSize: "13px",
              padding: "10px 12px",
              marginBottom: "16px",
            }}
          >
            {error}
          </div>
        )}

        {/* Actions */}
        <div
          style={{
            display: "flex",
            gap: "12px",
            justifyContent: "flex-end",
          }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            style={{
              border: "1px solid rgba(148, 163, 184, 0.3)",
              backgroundColor: "transparent",
              color: "#94a3b8",
              borderRadius: "8px",
              padding: "10px 16px",
              fontSize: "13px",
              fontWeight: 500,
              cursor: isSubmitting ? "not-allowed" : "pointer",
              opacity: isSubmitting ? 0.5 : 1,
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting || selectedPerspectives.size === 0}
            style={{
              border: "none",
              backgroundColor: isSubmitting || selectedPerspectives.size === 0
                ? "#3b82f6"
                : "#6366f1",
              color: "white",
              borderRadius: "8px",
              padding: "10px 20px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: isSubmitting || selectedPerspectives.size === 0 ? "not-allowed" : "pointer",
              opacity: isSubmitting || selectedPerspectives.size === 0 ? 0.6 : 1,
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            {isSubmitting ? (
              <>
                <div
                  style={{
                    width: "14px",
                    height: "14px",
                    border: "2px solid transparent",
                    borderTopColor: "white",
                    borderRadius: "50%",
                    animation: "spin 0.8s linear infinite",
                  }}
                />
                Starting...
              </>
            ) : (
              <>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M7 1.4V12.6M1.4 7H12.6"
                    stroke="white"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
                Run Analysis
              </>
            )}
          </button>
        </div>
      </div>

      {/* Spinner animation */}
      <style jsx>{`
        @keyframes spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
}
