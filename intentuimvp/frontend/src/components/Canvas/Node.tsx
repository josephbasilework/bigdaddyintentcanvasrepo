"use client";

import { CSSProperties, useState, useRef } from "react";
import Draggable, { DraggableData } from "react-draggable";
import { useCanvasStore, CanvasNode } from "../../state/canvasStore";
import { NodeContextMenu } from "./NodeContextMenu";

interface NodeProps {
  node: CanvasNode;
  onStartConnect?: (nodeId: string) => void;
}

/**
 * Node component for rendering canvas nodes with drag functionality.
 *
 * Displays a node with its title and content, supports drag-to-move,
 * and handles selection state.
 */
export function Node({ node, onStartConnect }: NodeProps) {
  const { selectNode, selectedNodeId, updateNodePosition, removeNode, updateNode, addNode } = useCanvasStore();
  const isSelected = selectedNodeId === node.id;
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(node.title);
  const [editContent, setEditContent] = useState(node.content || "");
  const nodeRef = useRef<HTMLDivElement>(null);

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

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY });
  };

  const handleEdit = () => {
    setEditTitle(node.title);
    setEditContent(node.content || "");
    setIsEditing(true);
  };

  const handleSaveEdit = () => {
    updateNode(node.id, { title: editTitle, content: editContent });
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
  };

  const handleDelete = () => {
    removeNode(node.id);
  };

  const handleDuplicate = () => {
    const newNode = {
      type: node.type,
      x: node.x + 20,
      y: node.y + 20,
      z: node.z,
      title: `${node.title} (copy)`,
      content: node.content,
      metadata: node.metadata,
    };
    addNode(newNode);
  };

  const handleConnect = () => {
    if (onStartConnect) {
      onStartConnect(node.id);
    }
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
    <>
      <Draggable
        position={{ x: node.x, y: node.y }}
        onDrag={handleDrag}
        onStop={handleDragStop}
      >
        <div
          ref={nodeRef}
          style={getNodeStyle()}
          onClick={handleClick}
          onContextMenu={handleContextMenu}
        >
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

      {/* Context menu */}
      {contextMenu && (
        <NodeContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onClose={() => setContextMenu(null)}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onDuplicate={handleDuplicate}
          onConnect={onStartConnect ? handleConnect : undefined}
        />
      )}

      {/* Edit modal */}
      {isEditing && (
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
          onClick={handleCancelEdit}
        >
          <div
            style={{
              backgroundColor: "#1a202c",
              border: "1px solid #2d3748",
              borderRadius: "8px",
              padding: "20px",
              minWidth: "400px",
              maxWidth: "600px",
              maxHeight: "80vh",
              overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginTop: 0, marginBottom: "16px", color: "#fff" }}>Edit Node</h3>

            <div style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px" }}>
                Title
              </label>
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  backgroundColor: "#2d3748",
                  border: "1px solid #4a5568",
                  borderRadius: "4px",
                  color: "#fff",
                  fontSize: "14px",
                  boxSizing: "border-box",
                }}
                autoFocus
              />
            </div>

            <div style={{ marginBottom: "20px" }}>
              <label style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px" }}>
                Content
              </label>
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={8}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  backgroundColor: "#2d3748",
                  border: "1px solid #4a5568",
                  borderRadius: "4px",
                  color: "#fff",
                  fontSize: "14px",
                  boxSizing: "border-box",
                  resize: "vertical",
                }}
              />
            </div>

            <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
              <button
                onClick={handleCancelEdit}
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
                onClick={handleSaveEdit}
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
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
