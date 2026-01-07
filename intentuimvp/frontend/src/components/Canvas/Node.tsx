"use client";

import { CSSProperties, useState } from "react";
import Draggable, { DraggableData } from "react-draggable";
import { useCanvasStore, CanvasNode } from "../../state/canvasStore";

interface NodeProps {
  node: CanvasNode;
}

/**
 * Node component for rendering canvas nodes with drag functionality.
 *
 * Displays a node with its title and content, supports drag-to-move,
 * and handles selection state.
 */
export function Node({ node }: NodeProps) {
  const { selectNode, selectedNodeId, updateNodePosition } = useCanvasStore();
  const isSelected = selectedNodeId === node.id;

  const handleDrag = (e: unknown, data: DraggableData) => {
    // Update node position in store when dragging
    updateNodePosition(node.id, data.x, data.y);
  };

  const handleDragStop = (e: unknown, data: DraggableData) => {
    // Final position update when drag stops
    updateNodePosition(node.id, data.x, data.y);
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    selectNode(node.id);
  };

  // Get node style based on type
  const getNodeStyle = (): CSSProperties => {
    const baseStyle: CSSProperties = {
      position: "absolute",
      left: node.x,
      top: node.y,
      zIndex: node.z,
      minWidth: "200px",
      maxWidth: "400px",
      padding: "12px",
      borderRadius: "8px",
      cursor: "move",
      userSelect: "none",
      transition: isSelected ? "box-shadow 0.2s" : "none",
    };

    // Type-specific styles
    switch (node.type) {
      case "text":
        return {
          ...baseStyle,
          backgroundColor: "#1a1a2e",
          border: isSelected ? "2px solid #4a9eff" : "1px solid #333",
          boxShadow: isSelected ? "0 0 20px rgba(74, 158, 255, 0.3)" : "0 4px 6px rgba(0, 0, 0, 0.3)",
        };
      case "document":
        return {
          ...baseStyle,
          backgroundColor: "#16213e",
          border: isSelected ? "2px solid #00d4aa" : "1px solid #1a3a5a",
          boxShadow: isSelected ? "0 0 20px rgba(0, 212, 170, 0.3)" : "0 4px 6px rgba(0, 0, 0, 0.3)",
        };
      case "audio":
        return {
          ...baseStyle,
          backgroundColor: "#1f1f3a",
          border: isSelected ? "2px solid #ff6b6b" : "1px solid #3a2a2a",
          boxShadow: isSelected ? "0 0 20px rgba(255, 107, 107, 0.3)" : "0 4px 6px rgba(0, 0, 0, 0.3)",
        };
      case "graph":
        return {
          ...baseStyle,
          backgroundColor: "#1a1a3a",
          border: isSelected ? "2px solid #ffd93d" : "1px solid #3a2a3a",
          boxShadow: isSelected ? "0 0 20px rgba(255, 217, 61, 0.3)" : "0 4px 6px rgba(0, 0, 0, 0.3)",
        };
      default:
        return baseStyle;
    }
  };

  const getIconForType = () => {
    switch (node.type) {
      case "text":
        return "📝";
      case "document":
        return "📄";
      case "audio":
        return "🎙️";
      case "graph":
        return "📊";
      default:
        return "📦";
    }
  };

  return (
    <Draggable
      position={{ x: node.x, y: node.y }}
      onDrag={handleDrag}
      onStop={handleDragStop}
    >
      <div style={getNodeStyle()} onClick={handleClick}>
        {/* Node header */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginBottom: "8px",
          paddingBottom: "8px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
        }}>
          <span style={{ fontSize: "16px" }}>{getIconForType()}</span>
          <span style={{
            fontSize: "14px",
            fontWeight: 600,
            color: "#fff",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            flex: 1,
          }}>
            {node.title}
          </span>
        </div>

        {/* Node content */}
        {node.content && (
          <div style={{
            fontSize: "13px",
            color: "#aaa",
            lineHeight: "1.5",
            maxHeight: "200px",
            overflow: "auto",
            wordBreak: "break-word",
          }}>
            {node.content}
          </div>
        )}

        {/* Node metadata indicator */}
        {node.metadata && Object.keys(node.metadata).length > 0 && (
          <div style={{
            marginTop: "8px",
            fontSize: "11px",
            color: "#666",
            display: "flex",
            gap: "4px",
            flexWrap: "wrap",
          }}>
            {Object.keys(node.metadata).map((key) => (
              <span
                key={key}
                style={{
                  padding: "2px 6px",
                  borderRadius: "4px",
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                }}
              >
                {key}
              </span>
            ))}
          </div>
        )}
      </div>
    </Draggable>
  );
}
