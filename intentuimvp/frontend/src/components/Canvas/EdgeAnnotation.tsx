"use client";

import { useState, useCallback, useId } from "react";
import type { CanvasEdgeAnnotation } from "../../state/canvasStore";

interface EdgeAnnotationProps {
  annotation?: CanvasEdgeAnnotation;
  edgeLabel: string;
  onSave: (annotation: CanvasEdgeAnnotation) => void;
  onCancel: () => void;
}

/**
 * EdgeAnnotation component for editing edge annotations.
 *
 * Provides UI for:
 * - Comment text
 * - Tags for categorization
 * - Status selection
 */
export function EdgeAnnotation({ annotation, edgeLabel, onSave, onCancel }: EdgeAnnotationProps) {
  const [comment, setComment] = useState(annotation?.comment ?? "");
  const [tags, setTags] = useState<string[]>(annotation?.tags ?? []);
  const [status, setStatus] = useState<CanvasEdgeAnnotation["status"]>(
    annotation?.status ?? "active"
  );
  const [newTag, setNewTag] = useState("");

  const titleId = useId();
  const commentId = useId();
  const tagsId = useId();

  const handleAddTag = useCallback(() => {
    const trimmed = newTag.trim();
    if (!trimmed || tags.includes(trimmed)) return;
    setTags([...tags, trimmed]);
    setNewTag("");
  }, [newTag, tags]);

  const handleRemoveTag = useCallback((tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  }, [tags]);

  const handleSave = useCallback(() => {
    const trimmedComment = comment.trim();
    onSave({
      comment: trimmedComment.length > 0 ? trimmedComment : undefined,
      tags,
      status,
    });
  }, [comment, onSave, status, tags]);

  const handleTagKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddTag();
      }
    },
    [handleAddTag]
  );

  const getStatusColor = (value: CanvasEdgeAnnotation["status"]) => {
    switch (value) {
      case "active":
        return "#48bb78";
      case "archived":
        return "#718096";
      case "draft":
        return "#ecc94b";
      case "review":
        return "#4299e1";
      default:
        return "#718096";
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10001,
      }}
      onClick={onCancel}
      role="presentation"
    >
      <div
        style={{
          backgroundColor: "#101826",
          border: "1px solid #1f2937",
          borderRadius: "10px",
          padding: "20px",
          minWidth: "420px",
          maxWidth: "560px",
          maxHeight: "80vh",
          overflow: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <h3
          style={{ marginTop: 0, marginBottom: "16px", color: "#fff" }}
          id={titleId}
        >
          Edge Annotation
        </h3>
        <div style={{ marginBottom: "16px", color: "#94a3b8", fontSize: "12px" }}>
          {edgeLabel}
        </div>

        <div style={{ marginBottom: "18px" }}>
          <label
            htmlFor={commentId}
            style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px" }}
          >
            Comment
          </label>
          <textarea
            id={commentId}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={5}
            style={{
              width: "100%",
              padding: "10px 12px",
              backgroundColor: "#0f172a",
              border: "1px solid #334155",
              borderRadius: "6px",
              color: "#e2e8f0",
              fontSize: "13px",
              boxSizing: "border-box",
              resize: "vertical",
            }}
            placeholder="Add context or notes about this relationship."
          />
        </div>

        <div style={{ marginBottom: "18px" }}>
          <label
            htmlFor={tagsId}
            style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px" }}
          >
            Tags
          </label>
          <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
            <input
              id={tagsId}
              type="text"
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              onKeyDown={handleTagKeyDown}
              placeholder="Add tag"
              style={{
                flex: 1,
                padding: "8px 12px",
                backgroundColor: "#0f172a",
                border: "1px solid #334155",
                borderRadius: "6px",
                color: "#e2e8f0",
                fontSize: "13px",
                boxSizing: "border-box",
              }}
            />
            <button
              type="button"
              onClick={handleAddTag}
              style={{
                padding: "8px 14px",
                backgroundColor: "#2563eb",
                border: "none",
                borderRadius: "6px",
                color: "#fff",
                cursor: "pointer",
                fontSize: "12px",
              }}
            >
              Add
            </button>
          </div>
          {tags.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
              {tags.map((tag) => (
                <span
                  key={tag}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "4px 8px",
                    borderRadius: "999px",
                    backgroundColor: "rgba(148, 163, 184, 0.15)",
                    color: "#e2e8f0",
                    fontSize: "11px",
                  }}
                >
                  {tag}
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    aria-label={`Remove tag ${tag}`}
                    style={{
                      border: "none",
                      backgroundColor: "transparent",
                      color: "#f87171",
                      cursor: "pointer",
                      fontSize: "12px",
                      padding: 0,
                    }}
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        <div style={{ marginBottom: "20px" }}>
          <label style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px" }}>
            Status
          </label>
          <div style={{ display: "flex", gap: "8px" }}>
            {(["active", "draft", "review", "archived"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setStatus(value)}
                style={{
                  padding: "6px 12px",
                  backgroundColor: status === value ? `${getStatusColor(value)}33` : "#1f2937",
                  border: `1px solid ${status === value ? getStatusColor(value) : "#334155"}`,
                  borderRadius: "6px",
                  color: status === value ? getStatusColor(value) : "#cbd5e0",
                  cursor: "pointer",
                  fontSize: "12px",
                  textTransform: "capitalize",
                }}
              >
                {value}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onCancel}
            style={{
              padding: "8px 16px",
              backgroundColor: "#334155",
              border: "none",
              borderRadius: "6px",
              color: "#fff",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            style={{
              padding: "8px 16px",
              backgroundColor: "#22c55e",
              border: "none",
              borderRadius: "6px",
              color: "#fff",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
