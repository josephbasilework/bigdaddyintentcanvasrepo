"use client";

import { CSSProperties, useState, useRef, useId, useCallback, useMemo } from "react";
import Draggable, { DraggableData } from "react-draggable";
import { useTransformComponent } from "react-zoom-pan-pinch";
import {
  useCanvasStore,
  CanvasNode,
  AUTO_EXPAND_ANIMATION_MS,
  AUTO_LAYOUT_ANIMATION_MS,
  DAGTask,
} from "../../state/canvasStore";
import { NodeContextMenu } from "./NodeContextMenu";
import { DeleteConfirmationDialog } from "./DeleteConfirmationDialog";
import { GraphAnnotation, GraphAnnotationDisplay } from "./GraphAnnotation";
import { DependencyEditor, DependencyDisplay } from "./DependencyEditor";
import { JobRoutingDialog } from "./JobRoutingDialog";
import { DocumentBlock } from "./DocumentBlock";
import { MarkdownPreview } from "./MarkdownPreview";
import { CalendarSyncDialog } from "./CalendarSyncDialog";
import { PerspectiveRerunDialog } from "./PerspectiveRerunDialog";
import { ReminderDialog } from "./ReminderDialog";
import {
  CalendarApprovalDialog,
  type PendingCalendarAction,
  type CalendarApprovalResult,
} from "./CalendarApprovalDialog";
import {
  applyCalendarSyncUpdates,
  buildCalendarSyncPayload,
  mergeDagMetadata,
  type CalendarSyncApiResponse,
  type CalendarSyncCandidate,
} from "../../utils/calendarSync";
import { getNodeTypeDefinition, type NodeRendererProps } from "../../nodeTypes";
import { getNodeDimensions } from "../../utils/nodeDimensions";
import {
  DEFAULT_CONTAINER_HEADER_HEIGHT,
  DEFAULT_CONTAINER_PADDING,
  buildContainerFrame,
  computeNodesBounds,
  getContainerSize,
  getNodeParentId,
  isContainerCollapsed,
  isContainerNode,
  updateContainerMetadata,
} from "../../utils/canvasHierarchy";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const MAX_DOCUMENT_PREVIEW_CHARS = 280;
const MAX_DOCUMENT_PREVIEW_LINES = 6;

const buildDocumentPreview = (content?: string): string => {
  if (!content) return "";
  const lines = content.split(/\r?\n/).slice(0, MAX_DOCUMENT_PREVIEW_LINES);
  let preview = lines.join("\n").trim();
  if (preview.length > MAX_DOCUMENT_PREVIEW_CHARS) {
    preview = `${preview.slice(0, MAX_DOCUMENT_PREVIEW_CHARS).trimEnd()}...`;
  }
  return preview;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

interface NodeProps {
  node: CanvasNode;
  onStartConnect?: (nodeId: string) => void;
  onStartConnectDrag?: (nodeId: string, event: React.PointerEvent<HTMLButtonElement>) => void;
  connectSourceNodeId?: string | null;
  onConnectTarget?: (nodeId: string) => void;
}

/**
 * Node component for rendering canvas nodes with drag functionality.
 *
 * Displays a node with its title and content, supports drag-to-move,
 * and handles selection state.
 */
export function Node({
  node,
  onStartConnect,
  onStartConnectDrag,
  connectSourceNodeId,
  onConnectTarget,
}: NodeProps) {
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
  const allNodes = useCanvasStore((state) => state.nodes);
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
  const isTextNode = node.type === "text";
  const isDocumentNode = node.type === "document";
  const isContainerNodeType = isContainerNode(node);
  const nodeTypeDefinition = getNodeTypeDefinition(node.type);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isEditingDocument, setIsEditingDocument] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState<{
    nodeIds: string[];
    edgeCount: number;
    documentCount: number;
  } | null>(null);
  const [editTitle, setEditTitle] = useState(node.title);
  const [editContent, setEditContent] = useState(node.content || "");
  // Graph annotation state for graph-type nodes
  const [isEditingAnnotation, setIsEditingAnnotation] = useState(false);
  // Dependency editor state
  const [isEditingDependencies, setIsEditingDependencies] = useState(false);
  const [isCalendarSyncOpen, setIsCalendarSyncOpen] = useState(false);
  const [pendingCalendarApproval, setPendingCalendarApproval] = useState<{
    selectedCandidates: CalendarSyncCandidate[];
    pendingAction: PendingCalendarAction | null;
    isFirstAction: boolean;
  } | null>(null);
  const [isPerspectiveRerunOpen, setIsPerspectiveRerunOpen] = useState(false);
  const [isJobRoutingOpen, setIsJobRoutingOpen] = useState(false);
  const [isReminderOpen, setIsReminderOpen] = useState(false);
  const nodeRef = useRef<HTMLDivElement>(null);
  const focusFromPointerRef = useRef(false);
  const skipTitleCommitRef = useRef(false);
  const scale = useTransformComponent(({ state }) => state.scale);
  const isAutoExpanding = useCanvasStore((state) => state.isAutoExpanding);
  const isAutoLayoutAnimating = useCanvasStore((state) => state.isAutoLayoutAnimating);
  const descriptionId = useId();
  const editTitleId = useId();
  const editContentId = useId();
  const editDialogTitleId = useId();

  const documentPreview = useMemo(
    () => buildDocumentPreview(node.content),
    [node.content]
  );

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
  const selectionIds = selectedNodeIds.length > 0
    ? selectedNodeIds
    : selectedNodeId
      ? [selectedNodeId]
      : [];
  const containerChildren = useMemo(
    () => allNodes.filter((candidate) => getNodeParentId(candidate) === node.id),
    [allNodes, node.id]
  );
  const containerChildCount = containerChildren.length;
  const containerCollapsed = isContainerNodeType && isContainerCollapsed(node);
  const containerSize = isContainerNodeType
    ? getContainerSize(node) ?? getNodeDimensions({ type: node.type })
    : null;
  const canCreateContainer = selectionIds.length > 1 && selectionIds.includes(node.id);


  const handleDragStart = () => {
    setIsDragging(true);
  };

  const handleDrag = (e: unknown, data: DraggableData) => {
    // Update node position in store when dragging
    updateNodePosition(node.id, data.x, data.y, undefined, {
      log: false,
      recordHistory: false,
    });
  };

  const handleDragStop = (e: unknown, data: DraggableData) => {
    // Final position update when drag stops
    updateNodePosition(node.id, data.x, data.y, undefined, {
      log: true,
      resolveContainerParent: true,
    });
    setIsDragging(false);
  };

  const handleClick = (e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation();
    }
    focusFromPointerRef.current = false;
    if (connectSourceNodeId && onConnectTarget && connectSourceNodeId !== node.id) {
      onConnectTarget(node.id);
    }
    const toggleSelection = e?.metaKey || e?.ctrlKey;
    const additiveSelection = !toggleSelection && e?.shiftKey;
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

  const openExpanded = useCallback(() => {
    setIsExpanded(true);
    setEditContent(node.content || "");
  }, [node.content, setEditContent, setIsExpanded]);

  const closeExpanded = useCallback(() => {
    skipTitleCommitRef.current = true;
    setIsExpanded(false);
    setIsEditingTitle(false);
    setEditTitle(node.title);
    setEditContent(node.content || "");
  }, [node.content, node.title, setEditContent, setEditTitle, setIsEditingTitle, setIsExpanded]);

  const handleEdit = () => {
    setEditTitle(node.title);
    setEditContent(node.content || "");
    if (isTextNode) {
      openExpanded();
      setIsEditingTitle(true);
      return;
    }
    if (isDocumentNode) {
      setIsEditingDocument(true);
      return;
    }
    setIsEditing(true);
  };

  const handleSaveEdit = () => {
    const trimmed = editTitle.trim();
    const nextTitle = trimmed.length > 0 ? trimmed : "Untitled";
    updateNode(node.id, { title: nextTitle, content: editContent });
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
  };

  const handleTitleEditStart = useCallback(
    (event?: React.MouseEvent) => {
      if (event) {
        event.stopPropagation();
      }
      if (!isTextNode) return;
      setEditTitle(node.title);
      openExpanded();
      setIsEditingTitle(true);
    },
    [isTextNode, node.title, openExpanded, setEditTitle, setIsEditingTitle]
  );

  const commitTitle = useCallback(() => {
    if (skipTitleCommitRef.current) {
      skipTitleCommitRef.current = false;
      return;
    }
    const trimmed = editTitle.trim();
    const nextTitle = trimmed.length > 0 ? trimmed : "Untitled";
    if (nextTitle !== node.title) {
      updateNode(node.id, { title: nextTitle });
    }
    setIsEditingTitle(false);
  }, [editTitle, node.id, node.title, updateNode]);

  const cancelTitle = useCallback(() => {
    skipTitleCommitRef.current = true;
    setEditTitle(node.title);
    setIsEditingTitle(false);
  }, [node.title, setEditTitle, setIsEditingTitle]);

  const handleTitleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commitTitle();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      cancelTitle();
    }
  };

  const handleContentSave = useCallback(() => {
    if ((node.content || "") !== editContent) {
      updateNode(node.id, { content: editContent });
    }
  }, [editContent, node.content, node.id, updateNode]);

  const handleContentClose = useCallback(() => {
    closeExpanded();
  }, [closeExpanded]);

  const handleContentKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      handleContentClose();
      return;
    }
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleContentSave();
    }
  };

  const handleExpandToggle = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();
      if (isExpanded) {
        handleContentClose();
        return;
      }
      openExpanded();
    },
    [handleContentClose, isExpanded, openExpanded]
  );

  const handleContainerToggle = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();
      const nextCollapsed = !containerCollapsed;
      updateNode(node.id, {
        metadata: updateContainerMetadata(node.metadata, { collapsed: nextCollapsed }),
      });
    },
    [containerCollapsed, node.id, node.metadata, updateNode]
  );

  const handleDocumentOpen = useCallback((event?: React.MouseEvent<HTMLButtonElement>) => {
    if (event) {
      event.stopPropagation();
    }
    setIsEditingDocument(true);
  }, []);

  const handleDocumentCancel = useCallback(() => {
    setIsEditingDocument(false);
  }, []);

  const handleDocumentSave = useCallback(
    (nodeId: string, title: string, content: string) => {
      const trimmed = title.trim();
      const nextTitle = trimmed.length > 0 ? trimmed : "Untitled";
      const baseMetadata = isRecord(node.metadata) ? node.metadata : {};
      const documentMetadata = isRecord(baseMetadata.document) ? baseMetadata.document : {};
      const nextMetadata = {
        ...baseMetadata,
        document: {
          ...documentMetadata,
          format: "markdown",
          lastEditedAt: new Date().toISOString(),
        },
      };
      updateNode(nodeId, { title: nextTitle, content, metadata: nextMetadata });
      setIsEditingDocument(false);
    },
    [node.metadata, updateNode]
  );

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

  const handleCreateContainer = () => {
    if (!canCreateContainer) return;
    const selectedNodes = allNodes.filter((candidate) => selectionIds.includes(candidate.id));
    const bounds = computeNodesBounds(selectedNodes);
    if (!bounds) {
      return;
    }
    const minSize = getNodeDimensions({ type: "container" });
    const frame = buildContainerFrame(bounds, {
      padding: DEFAULT_CONTAINER_PADDING,
      headerHeight: DEFAULT_CONTAINER_HEADER_HEIGHT,
      minSize,
    });
    const parentIds = new Set(
      selectedNodes.map((candidate) => getNodeParentId(candidate)).filter(Boolean)
    );
    const commonParentId = parentIds.size === 1 ? Array.from(parentIds)[0] : null;
    const parentNode = commonParentId
      ? allNodes.find((candidate) => candidate.id === commonParentId)
      : null;
    const containerMetadata = updateContainerMetadata(undefined, {
      collapsed: false,
      padding: DEFAULT_CONTAINER_PADDING,
      size: { width: frame.width, height: frame.height },
      ...(commonParentId && parentNode
        ? {
            parentId: commonParentId,
            offset: { x: frame.x - parentNode.x, y: frame.y - parentNode.y },
          }
        : {}),
    });
    const minZ = Math.min(...selectedNodes.map((candidate) => candidate.z ?? 0), 0);
    const containerId = addNode({
      type: "container",
      x: frame.x,
      y: frame.y,
      z: minZ - 1,
      title: "New container",
      metadata: containerMetadata,
    });
    selectedNodes.forEach((child) => {
      const offset = { x: child.x - frame.x, y: child.y - frame.y };
      updateNode(child.id, {
        metadata: updateContainerMetadata(child.metadata, {
          parentId: containerId,
          offset,
        }),
      });
    });
    selectNode(containerId);
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

  const handleConnectPointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (!onStartConnectDrag) return;
    onStartConnectDrag(node.id, event);
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

  // FR-012: Multi-Judge Compute - Rerun with more compute handlers
  const handleRerunWithMoreCompute = () => {
    setIsPerspectiveRerunOpen(true);
  };

  const handlePerspectiveRerunClose = () => {
    setIsPerspectiveRerunOpen(false);
  };

  const handlePerspectiveRerunCreated = (jobId: string) => {
    console.log("Perspective analysis job created:", jobId);
    // Optionally add the new job node to the canvas here
  };

  const originNodeId = useMemo(() => {
    if (!node.jobData?.data || typeof node.jobData.data !== "object") {
      return null;
    }
    const data = node.jobData.data as Record<string, unknown>;
    const candidate =
      data.origin_node_id ?? data.originNodeId ?? data.node_id ?? data.nodeId;
    if (typeof candidate === "string") {
      return candidate;
    }
    if (typeof candidate === "number" && Number.isFinite(candidate)) {
      return String(candidate);
    }
    return null;
  }, [node.jobData]);

  const handleJobRoutingSaved = useCallback(
    (destinations: Array<Record<string, unknown>>) => {
      if (!node.jobData) {
        return;
      }
      const existingData = node.jobData.data ?? {};
      const nextData = {
        ...existingData,
        result_destinations: destinations,
      };
      updateNode(
        node.id,
        {
          jobData: {
            ...node.jobData,
            data: nextData,
          },
        },
        { source: "system", log: false, recordHistory: false }
      );
    },
    [node, updateNode]
  );

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
        // Extract pending actions from the response for approval dialog
        const pendingActions = (result as unknown as { pending_actions?: PendingCalendarAction[] }).pending_actions ?? [];
        const firstPendingAction = pendingActions.length > 0 ? pendingActions[0] : null;

        if (firstPendingAction) {
          // Store the pending approval state and show approval dialog
          setPendingCalendarApproval({
            selectedCandidates,
            pendingAction: firstPendingAction,
            isFirstAction: true,
          });
          return { success: false, error: "" }; // Empty error to avoid showing alert
        }

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

  const handleCalendarApprovalClose = useCallback(() => {
    setPendingCalendarApproval(null);
    setIsCalendarSyncOpen(false);
  }, []);

  const handleCalendarApprovalConfirm = useCallback(
    async (action: PendingCalendarAction): Promise<CalendarApprovalResult> => {
      if (!pendingCalendarApproval || !node.dagData) {
        return { success: false, approved: false, error: "Missing approval context or DAG data." };
      }

      const { selectedCandidates } = pendingCalendarApproval;

      // Retry sync with user_confirmed=true
      const payload = buildCalendarSyncPayload(selectedCandidates, {
        calendarId: action.calendar_id ?? "primary",
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
        return { success: false, approved: false, error: `Calendar sync failed: ${message}` };
      }

      let result: CalendarSyncApiResponse | null = null;
      try {
        result = (await response.json()) as CalendarSyncApiResponse;
      } catch {
        result = null;
      }

      if (!response.ok || !result?.success) {
        const message =
          result?.error ?? result?.message ?? `Calendar sync failed (${response.status}).`;
        return { success: false, approved: true, error: message };
      }

      // Apply successful calendar updates to the DAG
      if (result.created_events) {
        const updatedDag = applyCalendarSyncUpdates(node.dagData, result.created_events);
        if (updatedDag !== node.dagData) {
          const updatedMetadata = mergeDagMetadata(node.metadata, updatedDag);
          updateNode(node.id, { dagData: updatedDag, metadata: updatedMetadata });
        }
      }

      return {
        success: true,
        approved: true,
        message: result.message ?? "Calendar event(s) created successfully.",
      };
    },
    [node.dagData, node.id, node.metadata, pendingCalendarApproval, updateNode]
  );

  const handleDagStatusChange = useCallback(
    (taskId: string, nextStatus: DAGTask["status"]) => {
      if (!node.dagData) return;
      let didChange = false;
      const updatedTasks = node.dagData.tasks.map((task) => {
        if (task.id !== taskId) return task;
        if (task.status === nextStatus) return task;
        didChange = true;
        return { ...task, status: nextStatus };
      });

      if (!didChange) return;
      const updatedDag = { ...node.dagData, tasks: updatedTasks };
      const updatedMetadata = mergeDagMetadata(node.metadata, updatedDag);

      updateNode(node.id, { dagData: updatedDag, metadata: updatedMetadata });

      void fetch(`${API_BASE_URL}/api/nodes/${node.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ metadata: updatedMetadata }),
      }).catch((error) => {
        console.error("Failed to persist DAG task status change:", error);
      });
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

  // Get node style based on type
  const getNodeStyle = (): CSSProperties => {
    const transitionParts: string[] = [];
    if (!isDragging) {
      if (isAutoLayoutAnimating) {
        transitionParts.push(`transform ${AUTO_LAYOUT_ANIMATION_MS}ms ease-in-out`);
      } else if (isAutoExpanding) {
        transitionParts.push(`transform ${AUTO_EXPAND_ANIMATION_MS}ms ease-out`);
      }
    }
    if (isSelected) {
      transitionParts.push("box-shadow 0.2s");
    }
    const transition = transitionParts.length > 0 ? transitionParts.join(", ") : "none";

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
      transition,
    };
    const containerStyle: CSSProperties =
      isContainerNodeType && containerSize
        ? {
            ...baseStyle,
            width: `${containerSize.width}px`,
            height: `${containerSize.height}px`,
            maxWidth: "none",
            boxSizing: "border-box",
          }
        : baseStyle;
    const nodeStyle = nodeTypeDefinition.style;
    if (!nodeStyle) {
      return containerStyle;
    }

    return {
      ...containerStyle,
      backgroundColor: nodeStyle.backgroundColor,
      border: isSelected
        ? `2px solid ${nodeStyle.selectedBorderColor}`
        : `1px solid ${nodeStyle.borderColor}`,
      boxShadow: isSelected
        ? `0 0 20px ${nodeStyle.selectedShadowColor}`
        : `0 4px 6px ${nodeStyle.shadowColor}`,
      ...(isContainerNodeType ? { borderStyle: "dashed" } : {}),
    };
  };

  const getIconForType = () => nodeTypeDefinition.icon ?? "📦";

  const renderDefaultContent = () => {
    if (isContainerNodeType) {
      return (
        <div style={{ fontSize: "12px", color: "#94a3b8" }}>
          {containerChildCount > 0
            ? `${containerChildCount} node${containerChildCount === 1 ? "" : "s"} ${
                containerCollapsed ? "hidden" : "inside"
              }`
            : "Add nodes to organize them here."}
        </div>
      );
    }

    if (isDocumentNode) {
      return documentPreview ? (
        <div
          style={{
            maxHeight: "140px",
            overflow: "hidden",
            padding: "8px",
            borderRadius: "8px",
            border: "1px solid rgba(148, 163, 184, 0.2)",
            backgroundColor: "rgba(15, 23, 42, 0.5)",
          }}
        >
          <MarkdownPreview content={documentPreview} variant="compact" />
        </div>
      ) : (
        <div style={{ fontSize: "12px", color: "#94a3b8" }}>
          No document content yet.
        </div>
      );
    }

    if (isTextNode) {
      if (isExpanded) {
        return (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <label htmlFor={editContentId} style={{ color: "#a0aec0", fontSize: "12px" }}>
              Content
            </label>
            <textarea
              id={editContentId}
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              onKeyDown={handleContentKeyDown}
              onMouseDown={(event) => event.stopPropagation()}
              onTouchStart={(event) => event.stopPropagation()}
              onFocus={() => selectNode(node.id)}
              rows={6}
              className="canvas-node__textarea"
              style={{
                width: "100%",
                padding: "8px 12px",
                backgroundColor: "rgba(15, 23, 42, 0.6)",
                border: "1px solid rgba(148, 163, 184, 0.5)",
                borderRadius: "6px",
                color: "#e2e8f0",
                fontSize: "13px",
                boxSizing: "border-box",
                resize: "vertical",
              }}
              placeholder="Add details..."
            />
            <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={handleContentClose}
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
                className="canvas-node__button"
                style={{
                  padding: "6px 12px",
                  backgroundColor: "rgba(148, 163, 184, 0.2)",
                  border: "1px solid rgba(148, 163, 184, 0.4)",
                  borderRadius: "6px",
                  color: "#e2e8f0",
                  cursor: "pointer",
                  fontSize: "12px",
                }}
              >
                Close
              </button>
              <button
                type="button"
                onClick={handleContentSave}
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
                className="canvas-node__button"
                style={{
                  padding: "6px 12px",
                  backgroundColor: "rgba(66, 153, 225, 0.7)",
                  border: "1px solid rgba(66, 153, 225, 0.9)",
                  borderRadius: "6px",
                  color: "#fff",
                  cursor: "pointer",
                  fontSize: "12px",
                }}
              >
                Save
              </button>
            </div>
          </div>
        );
      }

      return node.content ? (
        <div style={{ fontSize: "12px", color: "#94a3b8" }}>
          Expand to view content.
        </div>
      ) : null;
    }

    if (node.content) {
      return (
        <div
          style={{
            fontSize: "13px",
            color: "#aaa",
            lineHeight: "1.5",
            maxHeight: "200px",
            overflow: "auto",
            wordBreak: "break-word",
          }}
        >
          {node.content}
        </div>
      );
    }

    return null;
  };

  const rendererProps: NodeRendererProps = {
    node,
    isSelected,
    documentPreview,
    onSelect: handleClick,
    onDagTaskStatusChange: handleDagStatusChange,
    onRerunWithMoreCompute:
      node.jobData?.jobType === "perspective_analysis"
        ? handleRerunWithMoreCompute
        : undefined,
    onRouteResults: () => setIsJobRoutingOpen(true),
  };

  const CustomRenderer = nodeTypeDefinition.render;
  const renderedContent = CustomRenderer
    ? <CustomRenderer {...rendererProps} />
    : renderDefaultContent();

  return (
    <>
      <Draggable
        nodeRef={nodeRef}
        position={{ x: node.x, y: node.y }}
        onStart={handleDragStart}
        onDrag={handleDrag}
        onStop={handleDragStop}
        scale={scale}
        cancel=".canvas-node__input,.canvas-node__textarea,.canvas-node__button"
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
            {isTextNode && isEditingTitle ? (
              <input
                id={editTitleId}
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={handleTitleKeyDown}
                onBlur={commitTitle}
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
                onFocus={() => selectNode(node.id)}
                aria-label="Edit node title"
                className="canvas-node__input"
                style={{
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "#fff",
                  backgroundColor: "rgba(15, 23, 42, 0.6)",
                  border: "1px solid rgba(148, 163, 184, 0.5)",
                  borderRadius: "6px",
                  padding: "4px 8px",
                  flex: 1,
                }}
                autoFocus
              />
            ) : (
              <span
                style={{
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "#fff",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  flex: 1,
                }}
                onDoubleClick={isTextNode ? handleTitleEditStart : undefined}
              >
                {node.title}
              </span>
            )}
            {isTextNode && (
              <button
                type="button"
                onClick={handleExpandToggle}
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
                aria-label={`${isExpanded ? "Collapse" : "Expand"} ${node.title} content`}
                className="canvas-node__button"
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
                {isExpanded ? "Collapse" : "Expand"}
              </button>
            )}
            {isContainerNodeType && (
              <button
                type="button"
                onClick={handleContainerToggle}
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
                aria-label={`${containerCollapsed ? "Expand" : "Collapse"} ${node.title}`}
                className="canvas-node__button"
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
                {containerCollapsed ? "Expand" : "Collapse"}
              </button>
            )}
            {isDocumentNode && (
              <button
                type="button"
                onClick={handleDocumentOpen}
                onMouseDown={(event) => event.stopPropagation()}
                onTouchStart={(event) => event.stopPropagation()}
                aria-label={`Open ${node.title} document`}
                className="canvas-node__button"
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
                Open
              </button>
            )}
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
                onPointerDown={handleConnectPointerDown}
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
          {renderedContent}

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
          onCreateContainer={canCreateContainer ? handleCreateContainer : undefined}
          onConnect={onStartConnect ? handleConnect : undefined}
          onAnnotate={node.type === "graph" ? handleEditAnnotation : undefined}
          onEditDependencies={handleEditDependencies}
          onSetReminder={() => setIsReminderOpen(true)}
        />
      )}

      {isEditingDocument && (
        <DocumentBlock
          nodeId={node.id}
          title={node.title}
          content={node.content || ""}
          onSave={handleDocumentSave}
          onCancel={handleDocumentCancel}
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

      <CalendarApprovalDialog
        isOpen={pendingCalendarApproval !== null}
        pendingAction={pendingCalendarApproval?.pendingAction ?? null}
        onCancel={handleCalendarApprovalClose}
        onConfirm={handleCalendarApprovalConfirm}
      />

      <ReminderDialog
        isOpen={isReminderOpen}
        nodeId={node.id}
        nodeTitle={node.title}
        onCancel={() => setIsReminderOpen(false)}
      />

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

      {/* FR-012: Multi-Judge Compute - Rerun with more compute dialog */}
      <PerspectiveRerunDialog
        isOpen={isPerspectiveRerunOpen}
        onClose={handlePerspectiveRerunClose}
        topic={node.title}
        targetNodeId={node.id}
        onJobCreated={handlePerspectiveRerunCreated}
      />

      {node.type === "job" && node.jobData && (
        <JobRoutingDialog
          isOpen={isJobRoutingOpen}
          jobId={node.jobData.jobId}
          jobType={node.jobData.jobType}
          nodes={allNodes}
          defaultTargetNodeId={originNodeId}
          onClose={() => setIsJobRoutingOpen(false)}
          onSaved={handleJobRoutingSaved}
        />
      )}
    </>
  );
}
