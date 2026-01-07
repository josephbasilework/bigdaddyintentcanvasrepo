"use client";

import { useState, useRef, useCallback } from "react";

export interface Annotation {
  id: string;
  x: number;
  y: number;
  content: string;
  author?: string;
  createdAt: Date;
  color?: string;
}

interface AnnotationLayerProps {
  annotations: Annotation[];
  onAdd: (annotation: Omit<Annotation, "id" | "createdAt">) => void;
  onUpdate: (id: string, content: string) => void;
  onDelete: (id: string) => void;
  isActive: boolean;
  onToggleActive: () => void;
}

/**
 * AnnotationLayer component for adding and managing canvas annotations.
 *
 * Features:
 * - Click-to-add annotation mode
 * - Editable annotation notes
 * - Color-coded annotations
 * - Author tracking
 * - Timestamp display
 * - Delete functionality
 */
export function AnnotationLayer({
  annotations,
  onAdd,
  onUpdate,
  onDelete,
  isActive,
  onToggleActive,
}: AnnotationLayerProps) {
  const layerRef = useRef<HTMLDivElement>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const handleLayerClick = useCallback(
    (e: React.MouseEvent) => {
      if (!isActive || editingId) return;

      const rect = layerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const newAnnotation: Omit<Annotation, "id" | "createdAt"> = {
        x,
        y,
        content: "",
        color: "#fef08a", // Default yellow
      };

      onAdd(newAnnotation);
      setEditingId(`temp-${Date.now()}`);
      setEditContent("");
    },
    [isActive, editingId, onAdd]
  );

  const handleEdit = (annotation: Annotation) => {
    setEditingId(annotation.id);
    setEditContent(annotation.content);
  };

  const handleSave = (id: string) => {
    if (editContent.trim()) {
      onUpdate(id, editContent);
    } else {
      onDelete(id);
    }
    setEditingId(null);
    setEditContent("");
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditContent("");
  };

  const handleKeyDown = (e: React.KeyboardEvent, id: string) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSave(id);
    } else if (e.key === "Escape") {
      handleCancel();
    }
  };

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={onToggleActive}
        style={{
          position: "fixed",
          bottom: "20px",
          left: "20px",
          padding: "10px 16px",
          backgroundColor: isActive ? "#4299e1" : "#2d3748",
          border: "none",
          borderRadius: "8px",
          color: "#fff",
          cursor: "pointer",
          fontSize: "14px",
          fontWeight: 500,
          zIndex: 1000,
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = isActive ? "#3182ce" : "#4a5568";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = isActive ? "#4299e1" : "#2d3748";
        }}
      >
        💬 {isActive ? "Annotation Mode ON" : "Add Annotation"}
      </button>

      {/* Annotation layer */}
      <div
        ref={layerRef}
        onClick={handleLayerClick}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          pointerEvents: isActive ? "auto" : "none",
          zIndex: 100,
          cursor: isActive ? "crosshair" : "default",
        }}
      >
        {/* Existing annotations */}
        {annotations.map((annotation) => {
          const isEditing = editingId === annotation.id;
          const isHovered = hoveredId === annotation.id;

          return (
            <div
              key={annotation.id}
              onMouseEnter={() => setHoveredId(annotation.id)}
              onMouseLeave={() => setHoveredId(null)}
              style={{
                position: "absolute",
                left: annotation.x,
                top: annotation.y,
                transform: "translate(-50%, -100%)",
                zIndex: isEditing ? 110 : 101,
              }}
            >
              {/* Annotation marker */}
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  bottom: -20,
                  transform: "translateX(-50%)",
                  width: isHovered || isEditing ? "16px" : "10px",
                  height: isHovered || isEditing ? "16px" : "10px",
                  backgroundColor: annotation.color || "#fef08a",
                  border: "2px solid #fff",
                  borderRadius: "50%",
                  cursor: "pointer",
                  transition: "all 0.2s",
                  boxShadow: "0 2px 8px rgba(0, 0, 0, 0.3)",
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isEditing && !isActive) {
                    handleEdit(annotation);
                  }
                }}
              />

              {/* Annotation content */}
              {(isEditing || annotation.content || isHovered) && (
                <div
                  style={{
                    backgroundColor: annotation.color || "#fef08a",
                    color: "#1a202c",
                    padding: "8px 12px",
                    borderRadius: "8px",
                    minWidth: "150px",
                    maxWidth: "250px",
                    boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
                    border: "2px solid #fff",
                    marginBottom: "8px",
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {isEditing ? (
                    <div>
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        onKeyDown={(e) => handleKeyDown(e, annotation.id)}
                        placeholder="Add a note..."
                        autoFocus
                        style={{
                          width: "100%",
                          minHeight: "60px",
                          padding: "8px",
                          backgroundColor: "#fff",
                          border: "1px solid #e2e8f0",
                          borderRadius: "4px",
                          fontSize: "13px",
                          resize: "vertical",
                          fontFamily: "inherit",
                        }}
                      />
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "flex-end",
                          gap: "4px",
                          marginTop: "8px",
                        }}
                      >
                        <button
                          onClick={handleCancel}
                          style={{
                            padding: "4px 8px",
                            backgroundColor: "#e2e8f0",
                            border: "none",
                            borderRadius: "4px",
                            fontSize: "11px",
                            cursor: "pointer",
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleSave(annotation.id)}
                          style={{
                            padding: "4px 8px",
                            backgroundColor: "#4299e1",
                            border: "none",
                            borderRadius: "4px",
                            color: "#fff",
                            fontSize: "11px",
                            cursor: "pointer",
                          }}
                        >
                          Save
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div
                        style={{
                          fontSize: "13px",
                          lineHeight: "1.4",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                        }}
                      >
                        {annotation.content}
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginTop: "6px",
                          paddingTop: "6px",
                          borderTop: "1px solid rgba(0, 0, 0, 0.1)",
                          fontSize: "10px",
                          opacity: 0.7,
                        }}
                      >
                        <span>
                          {annotation.author && `${annotation.author} • `}
                          {new Date(annotation.createdAt).toLocaleDateString()}
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEdit(annotation);
                          }}
                          style={{
                            padding: "2px 6px",
                            backgroundColor: "rgba(0, 0, 0, 0.1)",
                            border: "none",
                            borderRadius: "3px",
                            cursor: "pointer",
                            fontSize: "10px",
                          }}
                        >
                          Edit
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {/* Active mode indicator */}
        {isActive && (
          <div
            style={{
              position: "fixed",
              top: "20px",
              left: "50%",
              transform: "translateX(-50%)",
              padding: "8px 16px",
              backgroundColor: "rgba(66, 153, 225, 0.9)",
              color: "#fff",
              borderRadius: "20px",
              fontSize: "13px",
              fontWeight: 500,
              pointerEvents: "none",
              zIndex: 1000,
            }}
          >
            Click anywhere on the canvas to add an annotation
          </div>
        )}
      </div>
    </>
  );
}

/**
 * useAnnotationStore hook for managing annotation state.
 *
 * Provides a simple interface for components to integrate annotations.
 */
export function useAnnotationStore() {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [isAnnotationModeActive, setIsAnnotationModeActive] = useState(false);

  const addAnnotation = useCallback(
    (annotation: Omit<Annotation, "id" | "createdAt">) => {
      const newAnnotation: Annotation = {
        ...annotation,
        id: `annotation-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
        createdAt: new Date(),
      };
      setAnnotations((prev) => [...prev, newAnnotation]);
    },
    []
  );

  const updateAnnotation = useCallback((id: string, content: string) => {
    setAnnotations((prev) =>
      prev.map((a) => (a.id === id ? { ...a, content } : a))
    );
  }, []);

  const deleteAnnotation = useCallback((id: string) => {
    setAnnotations((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const toggleAnnotationMode = useCallback(() => {
    setIsAnnotationModeActive((prev) => !prev);
  }, []);

  return {
    annotations,
    addAnnotation,
    updateAnnotation,
    deleteAnnotation,
    isAnnotationModeActive,
    toggleAnnotationMode,
  };
}
