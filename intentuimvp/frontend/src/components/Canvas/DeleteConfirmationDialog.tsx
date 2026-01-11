"use client";

import { useEffect, useId } from "react";
import { createPortal } from "react-dom";

interface DeleteConfirmationDialogProps {
  isOpen: boolean;
  nodeCount: number;
  edgeCount: number;
  documentCount: number;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DeleteConfirmationDialog({
  isOpen,
  nodeCount,
  edgeCount,
  documentCount,
  onCancel,
  onConfirm,
}: DeleteConfirmationDialogProps) {
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onCancel]);

  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  const nodeLabel = nodeCount === 1 ? "node" : "nodes";
  const edgeLabel = edgeCount === 1 ? "edge" : "edges";
  const documentLabel = documentCount === 1 ? "document" : "documents";

  return createPortal(
    <div
      data-testid="multi-delete-dialog"
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
          maxWidth: "520px",
          boxShadow: "0 18px 30px rgba(0, 0, 0, 0.5)",
          color: "#e2e8f0",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
        }}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <div style={{ fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.12em", color: "#94a3b8" }}>
            HITL confirmation
          </div>
          <h3 id={titleId} style={{ margin: 0, fontSize: "18px", color: "#f8fafc" }}>
            Delete {nodeCount} {nodeLabel}?
          </h3>
        </div>

        <p id={descriptionId} style={{ margin: 0, color: "#cbd5f5", lineHeight: 1.5 }}>
          This action removes selected nodes and their linked artifacts. It cannot be undone.
        </p>

        <div
          style={{
            backgroundColor: "rgba(15, 23, 42, 0.9)",
            borderRadius: "10px",
            padding: "14px 16px",
            border: "1px solid rgba(148, 163, 184, 0.2)",
            display: "grid",
            gap: "6px",
            fontSize: "14px",
          }}
        >
          <div>
            <span style={{ color: "#94a3b8" }}>Nodes:</span> {nodeCount} {nodeLabel}
          </div>
          <div>
            <span style={{ color: "#94a3b8" }}>Linked edges:</span> {edgeCount} {edgeLabel}
          </div>
          <div>
            <span style={{ color: "#94a3b8" }}>Linked documents:</span> {documentCount} {documentLabel}
          </div>
        </div>

        <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onCancel}
            style={{
              padding: "8px 14px",
              backgroundColor: "rgba(148, 163, 184, 0.2)",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              borderRadius: "999px",
              color: "#e2e8f0",
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            style={{
              padding: "8px 14px",
              backgroundColor: "#ef4444",
              border: "none",
              borderRadius: "999px",
              color: "#fff",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Confirm delete
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
