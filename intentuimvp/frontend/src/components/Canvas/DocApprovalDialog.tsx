"use client";

import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type PendingDocUpdate = {
  existingDocArtifactId: number;
  sourceArtifactId: number;
  newContent: string;
  diff: string;
  hasChanges: boolean;
  linesAdded: number;
  linesRemoved: number;
  suggestedAt: string;
};

export type DocApprovalResult = {
  success: boolean;
  approved: boolean;
  message?: string;
  error?: string;
  updatedArtifactId?: number;
};

type DocApprovalDialogProps = {
  isOpen?: boolean;
  pendingUpdate: PendingDocUpdate | null;
  onCancel: () => void;
  onConfirm: (update: PendingDocUpdate) => Promise<DocApprovalResult>;
};

type DocApprovalDialogContentProps = {
  pendingUpdate: PendingDocUpdate | null;
  onCancel: () => void;
  onConfirm: (update: PendingDocUpdate) => Promise<DocApprovalResult>;
};

function DiffViewer({ diff }: { diff: string }) {
  const lines = diff.split("\n");

  return (
    <div
      style={{
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        fontSize: "12px",
        lineHeight: "1.5",
        backgroundColor: "#0d1117",
        borderRadius: "6px",
        border: "1px solid #30363d",
        overflow: "auto",
        maxHeight: "300px",
      }}
    >
      {lines.map((line, index) => {
        const isHeader = line.startsWith("@@") || line.startsWith("diff") ||
                         line.startsWith("---") || line.startsWith("+++") ||
                         line.startsWith("index");
        const isAddition = line.startsWith("+");
        const isRemoval = line.startsWith("-");

        let backgroundColor = "transparent";
        let color = "#c9d1d9";

        if (isHeader) {
          backgroundColor = "#161b22";
          color = "#8b949e";
        } else if (isAddition) {
          backgroundColor = "rgba(46, 160, 67, 0.15)";
          color = "#7ee787";
        } else if (isRemoval) {
          backgroundColor = "rgba(248, 81, 73, 0.15)";
          color = "#ffa198";
        }

        return (
          <div
            key={index}
            style={{
              padding: "2px 8px",
              backgroundColor,
              color,
              whiteSpace: "pre",
            }}
          >
            {line || " "}
          </div>
        );
      })}
    </div>
  );
}

const DocApprovalDialogContent = ({
  pendingUpdate,
  onCancel,
  onConfirm,
}: DocApprovalDialogContentProps) => {
  const titleId = useId();
  const descriptionId = useId();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  const handleConfirm = async () => {
    if (!pendingUpdate || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const result = await onConfirm(pendingUpdate);
      if (!result.success) {
        setError(result.error || "Doc update approval failed.");
        setIsSubmitting(false);
        return;
      }
      setIsSubmitting(false);
      onCancel();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Doc update approval failed.";
      setError(message);
      setIsSubmitting(false);
    }
  };

  if (!pendingUpdate) {
    return null;
  }

  const { diff, linesAdded, linesRemoved } = pendingUpdate;

  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(2, 6, 23, 0.72)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10003,
      }}
      onClick={onCancel}
      role="presentation"
    >
      <div
        style={{
          backgroundColor: "#111827",
          border: "1px solid rgba(148, 163, 184, 0.3)",
          borderRadius: "12px",
          padding: "24px",
          width: "92%",
          maxWidth: "720px",
          maxHeight: "85vh",
          boxShadow: "0 18px 30px rgba(0, 0, 0, 0.5)",
          color: "#e2e8f0",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
          overflow: "hidden",
        }}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <div
            style={{
              fontSize: "12px",
              textTransform: "uppercase",
              letterSpacing: "0.12em",
              color: "#94a3b8",
            }}
          >
            Documentation update
          </div>
          <h3
            id={titleId}
            style={{ margin: 0, fontSize: "18px", color: "#f8fafc" }}
          >
            Review documentation changes
          </h3>
        </div>

        <p
          id={descriptionId}
          style={{ margin: 0, color: "#cbd5f5", lineHeight: 1.5 }}
        >
          An agent has suggested updates to this document. Review the diff below
          and approve to apply the changes, or cancel to discard them.
        </p>

        <div
          style={{
            display: "flex",
            gap: "16px",
            padding: "12px",
            borderRadius: "10px",
            border: "1px solid rgba(148, 163, 184, 0.2)",
            backgroundColor: "rgba(15, 23, 42, 0.9)",
            fontSize: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ color: "#7ee787" }}>+{linesAdded}</span>
            <span style={{ color: "#94a3b8" }}>additions</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ color: "#ffa198" }}>-{linesRemoved}</span>
            <span style={{ color: "#94a3b8" }}>deletions</span>
          </div>
          <div style={{ marginLeft: "auto", color: "#94a3b8" }}>
            {formatTimestamp(pendingUpdate.suggestedAt)}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div
            style={{
              fontSize: "12px",
              fontWeight: 600,
              color: "#e2e8f0",
            }}
          >
            Diff preview
          </div>
          <DiffViewer diff={diff} />
        </div>

        {error && (
          <div
            role="alert"
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.12)",
              border: "1px solid rgba(239, 68, 68, 0.35)",
              borderRadius: "10px",
              padding: "10px 12px",
              color: "#fecaca",
              fontSize: "12px",
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            style={{
              padding: "8px 14px",
              backgroundColor: "rgba(148, 163, 184, 0.2)",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              borderRadius: "999px",
              color: "#e2e8f0",
              fontSize: "13px",
              cursor: isSubmitting ? "not-allowed" : "pointer",
              opacity: isSubmitting ? 0.6 : 1,
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isSubmitting}
            style={{
              padding: "8px 14px",
              backgroundColor: isSubmitting ? "#475569" : "#38bdf8",
              border: "none",
              borderRadius: "999px",
              color: "#0f172a",
              fontSize: "13px",
              fontWeight: 600,
              cursor: isSubmitting ? "not-allowed" : "pointer",
            }}
          >
            {isSubmitting ? "Applying..." : "Approve & Apply"}
          </button>
        </div>
      </div>
    </div>
  );
};

export function DocApprovalDialog({
  isOpen = true,
  pendingUpdate,
  onCancel,
  onConfirm,
}: DocApprovalDialogProps) {
  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <DocApprovalDialogContent
      pendingUpdate={pendingUpdate}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />,
    document.body
  );
}

export async function handleDocUpdateApproval(
  update: PendingDocUpdate,
  userId?: string
): Promise<DocApprovalResult> {
  try {
    const url = new URL(`${API_BASE_URL}/api/docs/apply-update`);
    if (userId) {
      url.searchParams.append("user_id", userId);
    }

    const response = await fetch(url.toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        existing_doc_artifact_id: update.existingDocArtifactId,
        source_artifact_id: update.sourceArtifactId,
        new_content: update.newContent,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        approved: false,
        error: errorData.detail || errorData.message || `Doc update failed (${response.status})`,
      };
    }

    const data = await response.json();
    return {
      success: true,
      approved: true,
      message: "Documentation updated successfully.",
      updatedArtifactId: data.artifact_id,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Network error";
    return {
      success: false,
      approved: false,
      error: `Doc update failed: ${message}`,
    };
  }
}
