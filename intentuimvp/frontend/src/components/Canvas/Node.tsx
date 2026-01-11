"use client";

import { CSSProperties, useState, useRef, useId } from "react";
import Draggable, { DraggableData } from "react-draggable";
import { useTransformComponent } from "react-zoom-pan-pinch";
import { useCanvasStore, CanvasNode } from "../../state/canvasStore";
import { NodeContextMenu } from "./NodeContextMenu";
import { DeleteConfirmationDialog } from "./DeleteConfirmationDialog";

interface NodeProps {
  node: CanvasNode;
  onStartConnect?: (nodeId: string) => void;
  connectSourceNodeId?: string | null;
  onConnectTarget?: (nodeId: string) => void;
}

/**
 * Node component for rendering canvas nodes with drag functionality.
 *
 * Displays a node with its title and content, supports drag-to-move,
 * and handles selection state.
 */
export function Node({ node, onStartConnect, connectSourceNodeId, onConnectTarget }: NodeProps) {
  const {
    selectNode,
    selectedNodeId,
    selectedNodeIds,
    updateNodePosition,
    removeNode,
    removeNodes,
    updateNode,
    addNode,
  } = useCanvasStore();
  const isSelected = selectedNodeIds.length > 0
    ? selectedNodeIds.includes(node.id)
    : selectedNodeId === node.id;
  const showConnectButton = Boolean(onStartConnect) && isSelected && !connectSourceNodeId;
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState<{
    nodeIds: string[];
    edgeCount: number;
    documentCount: number;
  } | null>(null);
  const [editTitle, setEditTitle] = useState(node.title);
  const [editContent, setEditContent] = useState(node.content || "");
  const nodeRef = useRef<HTMLDivElement>(null);
  const focusFromPointerRef = useRef(false);
  const scale = useTransformComponent(({ state }) => state.scale);
  const descriptionId = useId();
  const editTitleId = useId();
  const editContentId = useId();
  const editDialogTitleId = useId();

  const contentSummary = node.content
    ? node.content.length > 140
      ? `${node.content.slice(0, 137).trimEnd()}...`
      : node.content
    : null;
  const metadataKeys = node.metadata ? Object.keys(node.metadata) : [];
  const descriptionParts = [
    `Type: ${node.type}.`,
    contentSummary ? `Content: ${contentSummary}.` : null,
    metadataKeys.length > 0 ? `Metadata keys: ${metadataKeys.join(", ")}.` : null,
  ].filter(Boolean);
  const descriptionText = descriptionParts.join(" ");

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
    focusFromPointerRef.current = false;
    if (connectSourceNodeId && onConnectTarget && connectSourceNodeId !== node.id) {
      onConnectTarget(node.id);
    }
    const toggleSelection = e.metaKey || e.ctrlKey;
    const additiveSelection = !toggleSelection && e.shiftKey;
    if (toggleSelection) {
      selectNode(node.id, { toggle: true });
      return;
    }
    if (additiveSelection) {
      selectNode(node.id, { additive: true });
      return;
    }
    selectNode(node.id);
  };

  const handlePointerDown = () => {
    focusFromPointerRef.current = true;
  };

  const handlePointerUp = () => {
    focusFromPointerRef.current = false;
  };

  const handleFocus = () => {
    if (focusFromPointerRef.current) {
      focusFromPointerRef.current = false;
      return;
    }
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
    const selectedIds = selectedNodeIds.length > 1 && selectedNodeIds.includes(node.id)
      ? selectedNodeIds
      : [node.id];
    const { edges, documents } = useCanvasStore.getState();
    const idsToRemove = new Set(selectedIds);
    const edgeCount = edges.filter(
      (edge) => idsToRemove.has(edge.sourceNodeId) || idsToRemove.has(edge.targetNodeId)
    ).length;
    const documentCount = documents.filter((doc) => idsToRemove.has(doc.nodeId)).length;
    const needsConfirmation = selectedIds.length > 1 || edgeCount > 0 || documentCount > 0;

    if (needsConfirmation) {
      setDeleteDialog({
        nodeIds: selectedIds,
        edgeCount,
        documentCount,
      });
      return;
    }

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

  const handleCancelDelete = () => {
    setDeleteDialog(null);
  };

  const handleConfirmDelete = () => {
    if (!deleteDialog) return;
    removeNodes(deleteDialog.nodeIds);
    setDeleteDialog(null);
  };

  const handleConnect = () => {
    if (onStartConnect) {
      onStartConnect(node.id);
    }
  };

  const handleConnectClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    event.preventDefault();
    handleConnect();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleEdit();
    }
  };

  // Get node style based on type
  const getNodeStyle = (): CSSProperties => {
    const baseStyle: CSSProperties = {
      position: "absolute",
      left: 0,
      top: 0,
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
        nodeRef={nodeRef}
        position={{ x: node.x, y: node.y }}
        onDrag={handleDrag}
        onStop={handleDragStop}
        scale={scale}
      >
        <div
          ref={nodeRef}
          style={getNodeStyle()}
          className="canvas-node"
          data-node-id={node.id}
          onPointerDown={handlePointerDown}
          onMouseDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          onMouseUp={handlePointerUp}
          onClick={handleClick}
          onFocus={handleFocus}
          onKeyDown={handleKeyDown}
          onContextMenu={handleContextMenu}
          role="button"
          tabIndex={0}
          aria-label={`${node.title} ${node.type} node`}
          aria-describedby={descriptionText ? descriptionId : undefined}
          aria-haspopup="menu"
          aria-expanded={Boolean(contextMenu)}
          aria-roledescription="canvas node"
          aria-pressed={isSelected}
        >
          {descriptionText && (
            <span id={descriptionId} className="sr-only">
              {descriptionText}
            </span>
          )}
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
            {showConnectButton && (
              <button
                type="button"
                onClick={handleConnectClick}
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
                aria-label={`Connect from ${node.title}`}
                style={{
                  border: "1px solid rgba(148, 163, 184, 0.5)",
                  backgroundColor: "rgba(15, 23, 42, 0.6)",
                  color: "#e2e8f0",
                  borderRadius: "999px",
                  padding: "4px 10px",
                  fontSize: "11px",
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                }}
              >
                Connect
              </button>
            )}
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
              color: "#94a3b8",
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
            role="dialog"
            aria-modal="true"
            aria-labelledby={editDialogTitleId}
          >
            <h3
              style={{ marginTop: 0, marginBottom: "16px", color: "#fff" }}
              id={editDialogTitleId}
            >
              Edit Node
            </h3>

            <div style={{ marginBottom: "16px" }}>
              <label
                htmlFor={editTitleId}
                style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px" }}
              >
                Title
              </label>
              <input
                id={editTitleId}
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
              <label
                htmlFor={editContentId}
                style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px" }}
              >
                Content
              </label>
              <textarea
                id={editContentId}
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

      <DeleteConfirmationDialog
        isOpen={Boolean(deleteDialog)}
        nodeCount={deleteDialog?.nodeIds.length ?? 0}
        edgeCount={deleteDialog?.edgeCount ?? 0}
        documentCount={deleteDialog?.documentCount ?? 0}
        onCancel={handleCancelDelete}
        onConfirm={handleConfirmDelete}
      />
    </>
  );
}
