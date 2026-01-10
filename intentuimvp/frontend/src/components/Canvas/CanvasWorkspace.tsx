"use client";

import { useEffect, useCallback, useState } from "react";
import { useCanvasStore } from "../../state/canvasStore";
import { Node } from "./Node";
import { EdgesLayer } from "./Edge";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * CanvasWorkspace component that renders all nodes on the canvas.
 *
 * Handles:
 * - Loading/saving canvas state from/to the backend API
 * - Rendering all nodes and edges from the store
 * - Clearing selection when clicking empty space
 */
export function CanvasWorkspace() {
  const { nodes, edges, clearSelection, setNodes, setEdges } = useCanvasStore();
  const [loadStatus, setLoadStatus] = useState<"loading" | "loaded" | "error">("loading");

  // Load canvas state on mount
  useEffect(() => {
    let isActive = true;
    const loadCanvas = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/workspace`);
        if (!response.ok) {
          throw new Error(`Workspace load failed: ${response.status}`);
        }

        const data = await response.json();
        // Backend returns { nodes: [...], edges: [...] }
        if (Array.isArray(data.nodes)) {
          setNodes(data.nodes);
        }
        if (Array.isArray(data.edges)) {
          setEdges(data.edges);
        }
        if (isActive) {
          setLoadStatus("loaded");
        }
      } catch (error) {
        console.error("Failed to load canvas state:", error);
        if (isActive) {
          setLoadStatus("error");
        }
      }
    };

    loadCanvas();
    return () => {
      isActive = false;
    };
  }, [setNodes, setEdges]);

  // Save canvas state when nodes or edges change (debounced)
  useEffect(() => {
    if (nodes.length === 0 && edges.length === 0) return;

    const timeoutId = setTimeout(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/workspace`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ nodes, edges }),
        });

        if (!response.ok) {
          console.error("Failed to save canvas state");
        }
      } catch (error) {
        console.error("Failed to save canvas state:", error);
      }
    }, 500); // 500ms debounce

    return () => clearTimeout(timeoutId);
  }, [nodes, edges]);

  // Handle click on empty canvas area
  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    // Only clear selection if clicking directly on canvas (not on a node)
    if (e.target === e.currentTarget) {
      clearSelection();
    }
  }, [clearSelection]);

  const showEmptyState = loadStatus === "loaded" && nodes.length === 0 && edges.length === 0;

  return (
    <div
      onClick={handleCanvasClick}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "auto",
      }}
    >
      <EdgesLayer />
      {nodes.map((node) => (
        <Node key={node.id} node={node} />
      ))}
      {showEmptyState && (
        <div
          data-testid="empty-canvas-state"
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              maxWidth: "520px",
              padding: "20px 24px",
              borderRadius: "12px",
              backgroundColor: "rgba(15, 23, 42, 0.75)",
              border: "1px solid rgba(148, 163, 184, 0.2)",
              boxShadow: "0 12px 24px rgba(0, 0, 0, 0.35)",
              textAlign: "center",
            }}
          >
            <div
              style={{
                fontSize: "18px",
                fontWeight: 600,
                color: "#e2e8f0",
                marginBottom: "8px",
              }}
            >
              Your canvas is empty
            </div>
            <div
              style={{
                fontSize: "14px",
                color: "#94a3b8",
                lineHeight: 1.6,
              }}
            >
              Type a command in the box below to create your first node.
            </div>
            <div
              style={{
                marginTop: "10px",
                fontSize: "12px",
                color: "#64748b",
              }}
            >
              Try: /plan, /research, or &quot;Outline our next sprint&quot;
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
