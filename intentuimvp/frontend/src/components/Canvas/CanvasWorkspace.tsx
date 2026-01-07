"use client";

import { useEffect, useCallback } from "react";
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

  // Load canvas state on mount
  useEffect(() => {
    const loadCanvas = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/workspace`);
        if (response.ok) {
          const data = await response.json();
          // Backend returns { nodes: [...], edges: [...] }
          if (data.nodes && Array.isArray(data.nodes)) {
            setNodes(data.nodes);
          }
          if (data.edges && Array.isArray(data.edges)) {
            setEdges(data.edges);
          }
        }
      } catch (error) {
        console.error("Failed to load canvas state:", error);
      }
    };

    loadCanvas();
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
    </div>
  );
}
