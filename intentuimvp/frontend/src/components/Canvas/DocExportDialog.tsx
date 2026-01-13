"use client";

import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type DocFormat = "markdown" | "html" | "text";

export type DocExportResult = {
  success: boolean;
  message?: string;
  error?: string;
  jobId?: string;
  artifactId?: number;
};

type DocExportDialogProps = {
  isOpen?: boolean;
  sourceJobId?: string | null;
  sourceNodeId?: string | null;
  onCancel: () => void;
  onConfirm: (params: {
    sourceJobId: string;
    docFormat: DocFormat;
    includeMetadata: boolean;
  }) => Promise<DocExportResult>;
};

type DocExportDialogContentProps = {
  sourceJobId: string | null;
  sourceNodeId: string | null;
  onCancel: () => void;
  onConfirm: (params: {
    sourceJobId: string;
    docFormat: DocFormat;
    includeMetadata: boolean;
  }) => Promise<DocExportResult>;
};

const DocExportDialogContent = ({
  sourceJobId,
  sourceNodeId,
  onCancel,
  onConfirm,
}: DocExportDialogContentProps) => {
  const titleId = useId();
  const descriptionId = useId();
  const [docFormat, setDocFormat] = useState<DocFormat>("markdown");
  const [includeMetadata, setIncludeMetadata] = useState(true);
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
    if (!sourceJobId || isSubmitting) {
      setError("Source job ID is required for doc generation.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const result = await onConfirm({
        sourceJobId,
        docFormat,
        includeMetadata,
      });
      if (!result.success) {
        setError(result.error || "Doc generation failed.");
        setIsSubmitting(false);
        return;
      }
      setIsSubmitting(false);
      onCancel();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Doc generation failed.";
      setError(message);
      setIsSubmitting(false);
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
          maxWidth: "480px",
          maxHeight: "80vh",
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
            Export documentation
          </div>
          <h3
            id={titleId}
            style={{ margin: 0, fontSize: "18px", color: "#f8fafc" }}
          >
            Generate documentation
          </h3>
        </div>

        <p
          id={descriptionId}
          style={{ margin: 0, color: "#cbd5f5", lineHeight: 1.5 }}
        >
          Generate structured documentation from this node&apos;s content. The document
          will be stored as an artifact and can be exported or updated later.
        </p>

        {sourceNodeId && (
          <div
            style={{
              padding: "10px 12px",
              borderRadius: "8px",
              border: "1px solid rgba(148, 163, 184, 0.2)",
              backgroundColor: "rgba(15, 23, 42, 0.7)",
              fontSize: "12px",
              color: "#94a3b8",
            }}
          >
            Source node ID: {sourceNodeId}
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div>
            <label
              htmlFor="doc-format"
              style={{
                display: "block",
                marginBottom: "8px",
                color: "#a0aec0",
                fontSize: "13px",
                fontWeight: 500,
              }}
            >
              Output format
            </label>
            <select
              id="doc-format"
              value={docFormat}
              onChange={(e) => setDocFormat(e.target.value as DocFormat)}
              disabled={isSubmitting}
              style={{
                width: "100%",
                padding: "8px 12px",
                backgroundColor: "#2d3748",
                border: "1px solid #4a5568",
                borderRadius: "4px",
                color: "#fff",
                fontSize: "14px",
                cursor: isSubmitting ? "not-allowed" : "pointer",
              }}
            >
              <option value="markdown">Markdown (.md)</option>
              <option value="html">HTML (.html)</option>
              <option value="text">Plain text (.txt)</option>
            </select>
          </div>

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              padding: "10px 12px",
              borderRadius: "8px",
              border: "1px solid rgba(148, 163, 184, 0.2)",
              backgroundColor: "rgba(15, 23, 42, 0.7)",
              cursor: isSubmitting ? "not-allowed" : "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={includeMetadata}
              onChange={(e) => setIncludeMetadata(e.target.checked)}
              disabled={isSubmitting}
              style={{ margin: 0 }}
            />
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <span style={{ fontSize: "13px", color: "#e2e8f0" }}>
                Include metadata
              </span>
              <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                Add timestamps, job IDs, and source info
              </span>
            </div>
          </label>
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
            disabled={isSubmitting || !sourceJobId}
            style={{
              padding: "8px 14px",
              backgroundColor:
                isSubmitting || !sourceJobId ? "#475569" : "#38bdf8",
              border: "none",
              borderRadius: "999px",
              color: "#0f172a",
              fontSize: "13px",
              fontWeight: 600,
              cursor: isSubmitting || !sourceJobId ? "not-allowed" : "pointer",
            }}
          >
            {isSubmitting ? "Generating..." : "Generate"}
          </button>
        </div>
      </div>
    </div>
  );
};

export function DocExportDialog({
  isOpen = true,
  sourceJobId = null,
  sourceNodeId = null,
  onCancel,
  onConfirm,
}: DocExportDialogProps) {
  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <DocExportDialogContent
      sourceJobId={sourceJobId}
      sourceNodeId={sourceNodeId}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />,
    document.body
  );
}

export async function handleDocGeneration(
  params: {
    sourceJobId: string;
    docFormat: DocFormat;
    includeMetadata: boolean;
  },
  userId: string,
  workspaceId?: string
): Promise<DocExportResult> {
  try {
    const url = new URL(`${API_BASE_URL}/api/jobs/generate-doc`);
    url.searchParams.append("user_id", userId);
    if (workspaceId) {
      url.searchParams.append("workspace_id", workspaceId);
    }

    const response = await fetch(url.toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_job_id: params.sourceJobId,
        doc_format: params.docFormat,
        include_metadata: params.includeMetadata,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || errorData.message || `Doc generation failed (${response.status})`,
      };
    }

    const data = await response.json();
    return {
      success: true,
      message: "Documentation generation started successfully.",
      jobId: data.job_id,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Network error";
    return {
      success: false,
      error: `Doc generation failed: ${message}`,
    };
  }
}
