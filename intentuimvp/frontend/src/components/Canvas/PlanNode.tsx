"use client";

import type { PlanData } from "../../state/canvasStore";

interface PlanNodeProps {
  plan: PlanData;
}

/**
 * PlanNode component for visualizing plan metadata.
 *
 * Displays:
 * - Goal and approach
 * - Estimated total effort
 * - Assumptions (if any)
 * - Risks (if any)
 */
export function PlanNode({ plan }: PlanNodeProps) {
  return (
    <div
      style={{
        marginTop: "8px",
        fontSize: "13px",
        color: "#e2e8f0",
      }}
      role="region"
      aria-label="Plan details"
    >
      {/* Approach section */}
      <div style={{ marginBottom: "12px" }}>
        <div
          style={{
            fontSize: "11px",
            color: "#94a3b8",
            marginBottom: "4px",
            textTransform: "uppercase",
            letterSpacing: "0.5px",
          }}
        >
          Approach
        </div>
        <div style={{ lineHeight: "1.5" }}>{plan.approach}</div>
      </div>

      {/* Goal section */}
      <div style={{ marginBottom: "12px" }}>
        <div
          style={{
            fontSize: "11px",
            color: "#94a3b8",
            marginBottom: "4px",
            textTransform: "uppercase",
            letterSpacing: "0.5px",
          }}
        >
          Goal
        </div>
        <div
          style={{
            lineHeight: "1.5",
            padding: "8px",
            backgroundColor: "rgba(66, 153, 225, 0.1)",
            borderRadius: "4px",
            borderLeft: "3px solid #4299e1",
          }}
        >
          {plan.goal}
        </div>
      </div>

      {/* Estimated effort */}
      {plan.estimatedTotalEffort && (
        <div style={{ marginBottom: "12px" }}>
          <div
            style={{
              fontSize: "11px",
              color: "#94a3b8",
              marginBottom: "4px",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            Estimated Effort
          </div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 10px",
              backgroundColor: "rgba(72, 187, 120, 0.15)",
              borderRadius: "4px",
              color: "#48bb78",
            }}
          >
            <span>⏱</span>
            <span>{plan.estimatedTotalEffort}</span>
          </div>
        </div>
      )}

      {/* Assumptions */}
      {plan.assumptions && plan.assumptions.length > 0 && (
        <div style={{ marginBottom: "12px" }}>
          <div
            style={{
              fontSize: "11px",
              color: "#94a3b8",
              marginBottom: "4px",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            Assumptions
          </div>
          <ul
            style={{
              margin: 0,
              paddingLeft: "16px",
              color: "#a0aec0",
            }}
          >
            {plan.assumptions.map((assumption, index) => (
              <li key={index} style={{ marginBottom: "4px" }}>
                {assumption}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Risks */}
      {plan.risks && plan.risks.length > 0 && (
        <div>
          <div
            style={{
              fontSize: "11px",
              color: "#94a3b8",
              marginBottom: "4px",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            Risks
          </div>
          <ul
            style={{
              margin: 0,
              paddingLeft: "16px",
            }}
          >
            {plan.risks.map((risk, index) => (
              <li
                key={index}
                style={{
                  marginBottom: "4px",
                  color: "#f56565",
                }}
              >
                {risk}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
