"use client";

import { CSSProperties, useState, useRef, useId, useCallback } from "react";
import Draggable, { DraggableData } from "react-draggable";
import { useTransformComponent } from "react-zoom-pan-pinch";
import { useCanvasStore, CanvasNode } from "../../state/canvasStore";
import { NodeContextMenu } from "./NodeContextMenu";
import { DeleteConfirmationDialog } from "./DeleteConfirmationDialog";
import { AudioCapture, AudioRecording } from "./AudioCapture";
import { GraphAnnotation, GraphAnnotationDisplay } from "./GraphAnnotation";
import { DependencyEditor, DependencyDisplay } from "./DependencyEditor";
import { PlanNode } from "./PlanNode";
import { DAGNode } from "./DAGNode";
import { DashboardNode } from "./DashboardNode";
import { CalendarSyncDialog } from "./CalendarSyncDialog";
import {
  applyCalendarSyncUpdates,
  buildCalendarSyncPayload,
  mergeDagMetadata,
  type CalendarSyncApiResponse,
  type CalendarSyncCandidate,
} from "../../utils/calendarSync";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  const hasCalendarSuggestions = Boolean(
    node.type === "dag" &&
      node.dagData?.tasks.some(
        (task) =>
          task.calendarSuggestion &&
          !task.calendarEventId &&
          !task.calendarEventUrl
      )
  );
  const showCalendarSyncButton = isSelected && hasCalendarSuggestions;
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState<{
    nodeIds: string[];
    edgeCount: number;
    documentCount: number;
  } | null>(null);
  const [editTitle, setEditTitle] = useState(node.title);
  const [editContent, setEditContent] = useState(node.content || "");
  // Audio recording state for audio-type nodes
  const [audioRecording, setAudioRecording] = useState<AudioRecording | null>(
    node.metadata?.audioRecording as AudioRecording | null ?? null
  );
  // Graph annotation state for graph-type nodes
  const [isEditingAnnotation, setIsEditingAnnotation] = useState(false);
  // Dependency editor state
  const [isEditingDependencies, setIsEditingDependencies] = useState(false);
  const [isCalendarSyncOpen, setIsCalendarSyncOpen] = useState(false);
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

  const handleCalendarSyncOpen = () => {
    if (!hasCalendarSuggestions) return;
    setIsCalendarSyncOpen(true);
  };

  const handleCalendarSyncClose = () => {
    setIsCalendarSyncOpen(false);
  };

  const handleCalendarSyncClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    event.preventDefault();
    handleCalendarSyncOpen();
  };

  const handleCalendarSyncConfirm = useCallback(
    async (selectedCandidates: CalendarSyncCandidate[]) => {
      if (!node.dagData) {
        return { success: false, error: "No task DAG available for calendar sync." };
      }

      const payload = buildCalendarSyncPayload(selectedCandidates, {
        calendarId: "primary",
        userConfirmed: true,
      });

      let response: Response;
      try {
        response = await fetch(`${API_BASE_URL}/api/mcp/calendar/sync`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Network error";
        return { success: false, error: `Calendar sync failed: ${message}` };
      }

      let result: CalendarSyncApiResponse | null = null;
      try {
        result = (await response.json()) as CalendarSyncApiResponse;
      } catch {
        result = null;
      }

      if (!response.ok) {
        const message =
          result?.error ??
          result?.message ??
          `Calendar sync failed (${response.status}).`;
        return { success: false, error: message };
      }

      if (result?.created_events) {
        const updatedDag = applyCalendarSyncUpdates(node.dagData, result.created_events);
        if (updatedDag !== node.dagData) {
          const updatedMetadata = mergeDagMetadata(node.metadata, updatedDag);
          updateNode(node.id, { dagData: updatedDag, metadata: updatedMetadata });
        }
      }

      if (result?.requires_confirmation) {
        return {
          success: false,
          error: result.message ?? "Calendar sync requires confirmation.",
        };
      }

      if (result?.success) {
        return { success: true, message: result.message ?? undefined };
      }

      return {
        success: false,
        error: result?.error ?? result?.message ?? "Calendar sync failed.",
      };
    },
    [node.dagData, node.id, node.metadata, updateNode]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleEdit();
    }
  };

  // Graph annotation handlers
  const handleEditAnnotation = () => {
    setIsEditingAnnotation(true);
  };

  const handleSaveAnnotation = useCallback((annotation: { bullets?: string[]; tags?: string[]; status?: "active" | "archived" | "draft" | "review" }) => {
    updateNode(node.id, { graphAnnotation: annotation });
    setIsEditingAnnotation(false);
  }, [node.id, updateNode]);

  const handleCancelAnnotation = () => {
    setIsEditingAnnotation(false);
  };

  // Dependency editor handlers
  const handleEditDependencies = () => {
    setIsEditingDependencies(true);
  };

  const handleCloseDependencies = () => {
    setIsEditingDependencies(false);
  };

  // Handle audio recording completion
  const handleRecordingComplete = useCallback((recording: AudioRecording) => {
    setAudioRecording(recording);
    // Store recording reference in node metadata
    updateNode(node.id, {
      metadata: {
        ...node.metadata,
        audioRecording: {
          url: recording.url,
          duration: recording.duration,
          createdAt: recording.createdAt.toISOString(),
        },
      },
      content: `Audio recording (${Math.floor(recording.duration / 1000)}s)`,
    });
  }, [node.id, node.metadata, updateNode]);

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
      case "plan":
        return {
          ...baseStyle,
          backgroundColor: "#132a2d",
          border: isSelected ? "2px solid #38b2ac" : "1px solid #285e61",
          boxShadow: isSelected ? "0 0 20px rgba(56, 178, 172, 0.3)" : "0 4px 6px rgba(0, 0, 0, 0.3)",
        };
      case "dag":
        return {
          ...baseStyle,
          backgroundColor: "#241a2d",
          border: isSelected ? "2px solid #9f7aea" : "1px solid #553c9a",
          boxShadow: isSelected ? "0 0 20px rgba(159, 122, 234, 0.3)" : "0 4px 6px rgba(0, 0, 0, 0.3)",
        };
      case "dashboard":
        return {
          ...baseStyle,
          backgroundColor: "#141c2f",
          border: isSelected ? "2px solid #38bdf8" : "1px solid #1e3a5f",
          boxShadow: isSelected ? "0 0 20px rgba(56, 189, 248, 0.3)" : "0 4px 6px rgba(0, 0, 0, 0.3)",
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
      case "plan":
        return "🧭";
      case "dag":
        return "🧩";
      case "dashboard":
        return "📈";
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
            {showCalendarSyncButton && (
              <button
                type="button"
                onClick={handleCalendarSyncClick}
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
                aria-label={`Sync ${node.title} tasks to calendar`}
                style={{
                  border: "1px solid rgba(56, 189, 248, 0.6)",
                  backgroundColor: "rgba(14, 116, 144, 0.2)",
                  color: "#e2e8f0",
                  borderRadius: "999px",
                  padding: "4px 10px",
                  fontSize: "11px",
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                }}
              >
                Sync calendar
              </button>
            )}
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
          {node.type === "audio" ? (
            <AudioCapture
              onRecordingComplete={handleRecordingComplete}
              existingRecording={audioRecording}
              style={{
                minWidth: "280px",
              }}
              aria-label={`Audio capture for ${node.title}`}
            />
          ) : node.type === "plan" && node.planData ? (
            <PlanNode plan={node.planData} />
          ) : node.type === "dag" && node.dagData ? (
            <DAGNode dag={node.dagData} />
          ) : node.type === "dashboard" ? (
            <DashboardNode nodeId={node.id} />
          ) : node.content && (
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

          {/* Graph annotation display for graph-type nodes */}
          {node.type === "graph" && (
            <GraphAnnotationDisplay
              annotation={node.graphAnnotation}
              onEdit={handleEditAnnotation}
            />
          )}

          {/* Dependencies display for all nodes */}
          <DependencyDisplay
            nodeId={node.id}
            onEdit={handleEditDependencies}
          />
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
          onAnnotate={node.type === "graph" ? handleEditAnnotation : undefined}
          onEditDependencies={handleEditDependencies}
        />
      )}

      {node.type === "dag" && node.dagData && (
        <CalendarSyncDialog
          isOpen={isCalendarSyncOpen}
          dag={node.dagData}
          onCancel={handleCalendarSyncClose}
          onConfirm={handleCalendarSyncConfirm}
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

      {/* Graph annotation dialog */}
      {isEditingAnnotation && (
        <GraphAnnotation
          annotation={node.graphAnnotation}
          onSave={handleSaveAnnotation}
          onCancel={handleCancelAnnotation}
        />
      )}

      {/* Dependency editor dialog */}
      {isEditingDependencies && (
        <DependencyEditor
          nodeId={node.id}
          onClose={handleCloseDependencies}
        />
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
