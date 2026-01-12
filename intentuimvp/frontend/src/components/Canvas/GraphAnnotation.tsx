"use client";

import { useState, useCallback, useId } from "react";
import { GraphNodeAnnotation } from "../../state/canvasStore";

interface GraphAnnotationProps {
  annotation?: GraphNodeAnnotation;
  onSave: (annotation: GraphNodeAnnotation) => void;
  onCancel: () => void;
}

/**
 * GraphAnnotation component for editing graph node annotations.
 *
 * Provides UI for:
 * - Bullet-point annotations
 * - Tags for categorization
 * - Status selection
 */
export function GraphAnnotation({ annotation, onSave, onCancel }: GraphAnnotationProps) {
  const [bullets, setBullets] = useState<string[]>(annotation?.bullets ?? []);
  const [tags, setTags] = useState<string[]>(annotation?.tags ?? []);
  const [status, setStatus] = useState<GraphNodeAnnotation["status"]>(
    annotation?.status ?? "active"
  );
  const [newBullet, setNewBullet] = useState("");
  const [newTag, setNewTag] = useState("");

  const titleId = useId();
  const bulletsId = useId();
  const tagsId = useId();
  const statusId = useId();
  const dialogId = useId();

  const handleAddBullet = useCallback(() => {
    if (newBullet.trim()) {
      setBullets([...bullets, newBullet.trim()]);
      setNewBullet("");
    }
  }, [bullets, newBullet]);

  const handleRemoveBullet = useCallback((index: number) => {
    setBullets(bullets.filter((_, i) => i !== index));
  }, [bullets]);

  const handleAddTag = useCallback(() => {
    if (newTag.trim() && !tags.includes(newTag.trim())) {
      setTags([...tags, newTag.trim()]);
      setNewTag("");
    }
  }, [tags, newTag]);

  const handleRemoveTag = useCallback((tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  }, [tags]);

  const handleSave = useCallback(() => {
    onSave({ bullets, tags, status });
  }, [bullets, tags, status, onSave]);

  const handleBulletKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddBullet();
    }
  }, [handleAddBullet]);

  const handleTagKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddTag();
    }
  }, [handleAddTag]);

  const getStatusColor = (s: GraphNodeAnnotation["status"]) => {
    switch (s) {
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
          backgroundColor: "#1a202c",
          border: "1px solid #2d3748",
          borderRadius: "8px",
          padding: "20px",
          minWidth: "450px",
          maxWidth: "550px",
          maxHeight: "80vh",
          overflow: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={dialogId}
      >
        <h3
          style={{ marginTop: 0, marginBottom: "20px", color: "#fff" }}
          id={titleId}
        >
          Graph Node Annotations
        </h3>

        {/* Status */}
        <div style={{ marginBottom: "20px" }}>
          <label
            htmlFor={statusId}
            style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px" }}
          >
            Status
          </label>
          <div style={{ display: "flex", gap: "8px" }}>
            {(["active", "draft", "review", "archived"] as const).map((s) => (
              <button
                key={s}
                type="button"
                id={`${statusId}-${s}`}
                onClick={() => setStatus(s)}
                style={{
                  padding: "6px 12px",
                  backgroundColor: status === s ? `${getStatusColor(s)}33` : "#2d3748",
                  border: `1px solid ${status === s ? getStatusColor(s) : "#4a5568"}`,
                  borderRadius: "4px",
                  color: status === s ? getStatusColor(s) : "#cbd5e0",
                  cursor: "pointer",
                  fontSize: "12px",
                  textTransform: "capitalize",
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Bullets */}
        <div style={{ marginBottom: "20px" }}>
          <label
            htmlFor={bulletsId}
            style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px" }}
          >
            Bullet Annotations
          </label>
          <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
            <input
              id={bulletsId}
              type="text"
              value={newBullet}
              onChange={(e) => setNewBullet(e.target.value)}
              onKeyDown={handleBulletKeyDown}
              placeholder="Add a bullet point..."
              style={{
                flex: 1,
                padding: "8px 12px",
                backgroundColor: "#2d3748",
                border: "1px solid #4a5568",
                borderRadius: "4px",
                color: "#fff",
                fontSize: "13px",
                boxSizing: "border-box",
              }}
            />
            <button
              type="button"
              onClick={handleAddBullet}
              style={{
                padding: "8px 16px",
                backgroundColor: "#4299e1",
                border: "none",
                borderRadius: "4px",
                color: "#fff",
                cursor: "pointer",
                fontSize: "13px",
              }}
            >
              Add
            </button>
          </div>
          {bullets.length > 0 && (
            <ul
              style={{
                margin: 0,
                padding: "0 0 0 20px",
                listStylePosition: "inside",
                maxHeight: "120px",
                overflow: "auto",
              }}
            >
              {bullets.map((bullet, index) => (
                <li
                  key={index}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "4px 0",
                    color: "#e2e8f0",
                    fontSize: "13px",
                  }}
                >
                  <span style={{ flex: 1 }}>{bullet}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveBullet(index)}
                    style={{
                      padding: "2px 8px",
                      backgroundColor: "#e53e3e",
                      border: "none",
                      borderRadius: "3px",
                      color: "#fff",
                      cursor: "pointer",
                      fontSize: "11px",
                      marginLeft: "8px",
                    }}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Tags */}
        <div style={{ marginBottom: "20px" }}>
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
              placeholder="Add a tag..."
              style={{
                flex: 1,
                padding: "8px 12px",
                backgroundColor: "#2d3748",
                border: "1px solid #4a5568",
                borderRadius: "4px",
                color: "#fff",
                fontSize: "13px",
                boxSizing: "border-box",
              }}
            />
            <button
              type="button"
              onClick={handleAddTag}
              style={{
                padding: "8px 16px",
                backgroundColor: "#4299e1",
                border: "none",
                borderRadius: "4px",
                color: "#fff",
                cursor: "pointer",
                fontSize: "13px",
              }}
            >
              Add
            </button>
          </div>
          {tags.length > 0 && (
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "6px",
              }}
            >
              {tags.map((tag) => (
                <span
                  key={tag}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    padding: "4px 8px",
                    borderRadius: "4px",
                    backgroundColor: "#4a5568",
                    color: "#e2e8f0",
                    fontSize: "12px",
                  }}
                >
                  {tag}
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    style={{
                      padding: "0 4px",
                      backgroundColor: "transparent",
                      border: "none",
                      color: "#a0aec0",
                      cursor: "pointer",
                      fontSize: "14px",
                      marginLeft: "4px",
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onCancel}
            style={{
              padding: "8px 16px",
              backgroundColor: "#4a5568",
              border: "none",
              borderRadius: "4px",
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
              backgroundColor: "#48bb78",
              border: "none",
              borderRadius: "4px",
              color: "#fff",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            Save Annotations
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * GraphAnnotationDisplay component for displaying annotations on a graph node.
 */
interface GraphAnnotationDisplayProps {
  annotation?: GraphNodeAnnotation;
  onEdit: () => void;
}

export function GraphAnnotationDisplay({ annotation, onEdit }: GraphAnnotationDisplayProps) {
  if (!annotation) return null;

  const { bullets, tags, status } = annotation;
  const hasContent = (bullets && bullets.length > 0) || (tags && tags.length > 0) || status;

  if (!hasContent) return null;

  const getStatusColor = (s: GraphNodeAnnotation["status"]) => {
    switch (s) {
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
        marginTop: "12px",
        paddingTop: "8px",
        borderTop: "1px solid rgba(255, 255, 255, 0.1)",
      }}
    >
      {/* Status badge */}
      {status && (
        <div style={{ marginBottom: "8px" }}>
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: "4px",
              backgroundColor: `${getStatusColor(status)}33`,
              color: getStatusColor(status),
              fontSize: "10px",
              fontWeight: 600,
              textTransform: "uppercase",
            }}
          >
            {status}
          </span>
        </div>
      )}

      {/* Bullets */}
      {bullets && bullets.length > 0 && (
        <div style={{ marginBottom: "8px" }}>
          <ul
            style={{
              margin: 0,
              padding: "0 0 0 16px",
              listStylePosition: "inside",
            }}
          >
            {bullets.map((bullet, index) => (
              <li
                key={index}
                style={{
                  color: "#a0aec0",
                  fontSize: "11px",
                  lineHeight: "1.4",
                  marginBottom: "2px",
                }}
              >
                {bullet}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Tags */}
      {tags && tags.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
          {tags.map((tag) => (
            <span
              key={tag}
              style={{
                padding: "2px 6px",
                borderRadius: "3px",
                backgroundColor: "rgba(74, 85, 104, 0.5)",
                color: "#94a3b8",
                fontSize: "10px",
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Edit button */}
      <button
        type="button"
        onClick={onEdit}
        style={{
          marginTop: "8px",
          padding: "4px 8px",
          backgroundColor: "transparent",
          border: "1px solid #4a5568",
          borderRadius: "3px",
          color: "#718096",
          cursor: "pointer",
          fontSize: "10px",
        }}
      >
        Edit Annotations
      </button>
    </div>
  );
}
