"use client";

import { SaveStatus } from "../../hooks/useAutoSave";

interface SaveStatusIndicatorProps {
  saveStatus: SaveStatus;
  saveError: string | null;
}

/**
 * Visual indicator for auto-save status.
 *
 * Displays different states:
 * - "saving": Shows a spinner with "Saving..." text
 * - "saved": Shows a checkmark with "Saved" text (briefly)
 * - "error": Shows an error icon with the error message
 * - "idle": Hidden (no indicator)
 *
 * @example
 * ```tsx
 * <SaveStatusIndicator saveStatus="saving" saveError={null} />
 * ```
 */
export function SaveStatusIndicator({ saveStatus, saveError }: SaveStatusIndicatorProps) {
  if (saveStatus === "idle") {
    return null;
  }

  const getIndicator = () => {
    switch (saveStatus) {
      case "saving":
        return (
          <>
            <svg
              width="14"
              height="14"
              viewBox="0 0 14 14"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              style={{ animation: "spin 1s linear infinite" }}
            >
              <circle
                cx="7"
                cy="7"
                r="5"
                stroke="currentColor"
                strokeWidth="2"
                strokeOpacity="0.3"
              />
              <path
                d="M7 2C4.23858 2 2 4.23858 2 7"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
            <span>Saving...</span>
          </>
        );
      case "saved":
        return (
          <>
            <svg
              width="14"
              height="14"
              viewBox="0 0 14 14"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <circle cx="7" cy="7" r="6" fill="currentColor" fillOpacity="0.2" />
              <path
                d="M4.5 7L6.5 9L9.5 5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>Saved</span>
          </>
        );
      case "error":
        return (
          <>
            <svg
              width="14"
              height="14"
              viewBox="0 0 14 14"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <circle cx="7" cy="7" r="6" fill="currentColor" fillOpacity="0.2" />
              <path
                d="M5 5L9 9M9 5L5 9"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
            <span>Save failed</span>
          </>
        );
      default:
        return null;
    }
  };

  const getColor = () => {
    switch (saveStatus) {
      case "saving":
        return "#3b82f6"; // blue
      case "saved":
        return "#22c55e"; // green
      case "error":
        return "#ef4444"; // red
      default:
        return "#94a3b8";
    }
  };

  const color = getColor();

  return (
    <>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
      <div
        data-testid="save-status-indicator"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        aria-label={
          saveStatus === "saving"
            ? "Saving workspace"
            : saveStatus === "saved"
              ? "Workspace saved"
              : "Failed to save workspace"
        }
        style={{
          position: "fixed",
          bottom: "16px",
          right: "16px",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "8px 12px",
          backgroundColor: "rgba(15, 23, 42, 0.95)",
          border: `1px solid ${color}40`,
          borderRadius: "8px",
          color,
          fontSize: "12px",
          fontWeight: 500,
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
          zIndex: 10000,
          transition: "opacity 200ms ease, transform 200ms ease",
        }}
      >
        {getIndicator()}
        {saveError && (
          <span
            style={{
              marginLeft: "8px",
              padding: "4px 8px",
              backgroundColor: `${color}20`,
              borderRadius: "4px",
              fontSize: "11px",
              maxWidth: "200px",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
            title={saveError}
          >
            {saveError}
          </span>
        )}
      </div>
    </>
  );
}
