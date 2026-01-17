"use client";

import { Canvas, CanvasWorkspace } from "@/components/Canvas";
import { FloatingInput } from "@/components/ContextInput/FloatingInput";
import { ChatViewPanel } from "@/components/ChatView";
import { EventsViewPanel } from "@/components/EventsView";
import { WheelViewPanel } from "@/components/WheelView";
import { AssumptionsPanel } from "@/components/Assumptions";
import type {
  Assumption,
  AssumptionSet,
  IntentWorkflowRound,
} from "@/components/Assumptions";
import { useCanvasStore, type CanvasNode } from "@/state/canvasStore";
import { useConversationStore } from "@/state/conversationStore";
import { useEffect, useState, useCallback, useMemo } from "react";
import { useChatTurns } from "@/hooks/useChatTurns";
import { useTurns } from "@/hooks/useTurns";
import { useWebSocketEnhanced, type WebSocketMessage } from "@/hooks/useWebSocketEnhanced";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Derive WebSocket URL from API base URL
const getWebSocketUrl = (): string => {
  const url = new URL(API_BASE_URL);
  const protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${url.host}/ws`;
};
const WS_URL = getWebSocketUrl();

type CommandSubmissionLog = {
  id: string;
  text: string;
  attachments: string[];
};

/**
 * Node context for contextual conversation.
 * When a node is selected, its content becomes primary context for agent interaction.
 */
type NodeContext = {
  id: string;
  title: string;
  node_type: string;
  content?: string;
  metadata?: Record<string, unknown>;
};

type SelectionScope = {
  selected_nodes: string[];
  selected_edges: string[];
  node_context?: NodeContext[];
};

type WorkflowRound = IntentWorkflowRound & {
  selection: SelectionScope;
};

const getSelectionIds = (
  selectedNodeIds: string[],
  selectedNodeId: string | null
): string[] => {
  if (selectedNodeIds.length > 0) {
    return selectedNodeIds;
  }
  return selectedNodeId ? [selectedNodeId] : [];
};

const getSelectionScopeItems = (
  selectionIds: string[],
  nodes: CanvasNode[]
): Array<{ id: string; label: string; hasContent?: boolean }> => {
  if (selectionIds.length === 0) {
    return [];
  }
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  return selectionIds.map((id) => {
    const node = nodeById.get(id);
    return {
      id,
      label: node?.title ?? "Unknown node",
      hasContent: Boolean(node?.content),
    };
  });
};

/**
 * Build node context array from selected nodes.
 * Includes node content for contextual conversation with agent.
 */
const buildNodeContext = (
  selectionIds: string[],
  nodes: CanvasNode[]
): NodeContext[] => {
  if (selectionIds.length === 0) {
    return [];
  }
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  return selectionIds
    .map((id) => {
      const node = nodeById.get(id);
      if (!node) return null;
      const context: NodeContext = {
        id: node.id,
        title: node.title,
        node_type: node.type,
      };
      if (node.content) {
        context.content = node.content;
      }
      if (node.metadata) {
        context.metadata = node.metadata;
      }
      return context;
    })
    .filter((ctx): ctx is NodeContext => ctx !== null);
};

type AssumptionResponse = {
  id: string;
  text: string;
  confidence: number;
  category: string;
  explanation?: string | null;
};

type AssumptionSetResponse = {
  intent: string;
  intent_description?: string | null;
  confidence: number;
  alternatives: Array<{
    name: string;
    confidence: number;
    description: string;
  }>;
  assumptions: AssumptionResponse[];
  reasoning: string;
  should_auto_execute: boolean;
  session_id?: string | null;
  clarifying_questions?: string[] | null;
};

type AssumptionResolutionPayload = {
  assumption_id: string;
  action: "accept" | "reject" | "edit";
  edited_text?: string | null;
  original_text?: string | null;
  category?: string | null;
};

type AssumptionResolutionBatch = {
  session_id?: string | null;
  resolutions: AssumptionResolutionPayload[];
};

const normalizeCategory = (category: string): Assumption["category"] => {
  switch (category) {
    case "context":
    case "intent":
    case "parameter":
    case "other":
      return category;
    default:
      return "other";
  }
};

const mapAssumptionResponse = (assumption: AssumptionResponse): Assumption => ({
  id: assumption.id,
  originalText: assumption.text,
  text: assumption.text,
  confidence: assumption.confidence,
  category: normalizeCategory(assumption.category),
  status: "pending",
  explanation: assumption.explanation ?? undefined,
});

const createRoundId = (): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `round-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const buildClarifyingQuestions = (
  assumptionData: AssumptionSetResponse
): string[] => {
  if (
    assumptionData.clarifying_questions &&
    assumptionData.clarifying_questions.length > 0
  ) {
    return assumptionData.clarifying_questions;
  }
  if (assumptionData.assumptions.length > 0 || assumptionData.should_auto_execute) {
    return [];
  }
  if (assumptionData.alternatives.length > 0) {
    return ["Which of these intents best matches your goal?"];
  }
  return ["Can you clarify what you want to accomplish?"];
};

const createWorkflowRound = (
  assumptionData: AssumptionSetResponse,
  commandText: string,
  attachments: string[],
  selection: SelectionScope,
  options: { force?: boolean } = {}
): WorkflowRound | null => {
  const mappedAssumptions = assumptionData.assumptions.map(mapAssumptionResponse);
  const clarifyingQuestions = buildClarifyingQuestions(assumptionData);
  const shouldCreate =
    options.force || mappedAssumptions.length > 0 || clarifyingQuestions.length > 0;

  if (!shouldCreate) {
    return null;
  }

  const assumptionSet: AssumptionSet = {
    intent: assumptionData.intent,
    intentDescription: assumptionData.intent_description ?? undefined,
    confidence: assumptionData.confidence,
    reasoning: assumptionData.reasoning,
    alternatives: assumptionData.alternatives ?? [],
    sessionId: assumptionData.session_id ?? undefined,
  };

  return {
    id: assumptionData.session_id ?? createRoundId(),
    createdAt: new Date().toISOString(),
    commandText,
    attachments,
    selection,
    assumptions: mappedAssumptions,
    assumptionSet,
    clarifyingQuestions,
    status: "reviewing",
  };
};

const buildRevisionPrompt = (round: WorkflowRound, note?: string): string => {
  const lines: string[] = [
    "Please revise the proposal and assumptions based on the feedback below.",
    "",
    `Original request: ${round.commandText}`,
  ];

  if (round.assumptionSet?.intent) {
    lines.push(`Current proposal: ${round.assumptionSet.intent}`);
  }
  if (round.assumptionSet?.intentDescription) {
    lines.push(`Proposal details: ${round.assumptionSet.intentDescription}`);
  }

  if (round.assumptions.length > 0) {
    lines.push("", "Assumption feedback:");
    for (const assumption of round.assumptions) {
      const normalizedText = assumption.text.trim();
      const normalizedOriginal = assumption.originalText.trim();
      if (
        assumption.status === "accepted" &&
        normalizedText !== normalizedOriginal
      ) {
        lines.push(`- edited: \"${normalizedOriginal}\" -> \"${normalizedText}\"`);
        continue;
      }
      lines.push(`- ${assumption.status}: ${normalizedText}`);
    }
  }

  if (note) {
    lines.push("", `User clarification: ${note}`);
  }

  lines.push("", "Return an updated proposal with any remaining assumptions.");
  return lines.join("\n");
};

const buildAssumptionResolutions = (
  assumptions: Assumption[]
): AssumptionResolutionPayload[] =>
  assumptions
    .filter((assumption) => assumption.status !== "pending")
    .map((assumption) => {
      const normalizedText = assumption.text.trim();
      const normalizedOriginal = assumption.originalText.trim();
      const isEdited = normalizedText !== normalizedOriginal;
      const base = {
        assumption_id: assumption.id,
        original_text: assumption.originalText,
        category: assumption.category,
      };

      if (assumption.status === "rejected") {
        return { ...base, action: "reject" };
      }

      if (isEdited) {
        return {
          ...base,
          action: "edit",
          edited_text: normalizedText,
        };
      }

      return { ...base, action: "accept" };
    });

const persistAssumptionResolutions = async (
  payload: AssumptionResolutionBatch
): Promise<void> => {
  if (payload.resolutions.length === 0) {
    return;
  }

  const response = await fetch(`${API_BASE_URL}/api/context/assumptions/batch-resolve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(
      `Assumption resolution error: ${response.status} ${response.statusText}`
    );
  }
};

const completeAssumptionSession = async (
  sessionId?: string | null
): Promise<void> => {
  if (!sessionId) {
    return;
  }

  const response = await fetch(
    `${API_BASE_URL}/api/context/sessions/${sessionId}/complete`,
    {
      method: "POST",
    }
  );

  if (!response.ok) {
    throw new Error(
      `Assumption session completion error: ${response.status} ${response.statusText}`
    );
  }
};

export default function Home() {
  const [commands, setCommands] = useState<CommandSubmissionLog[]>([]);
  const [workflowRounds, setWorkflowRounds] = useState<WorkflowRound[]>([]);
  const [activeRoundId, setActiveRoundId] = useState<string | null>(null);
  const [routingError, setRoutingError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("Ready for commands.");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [activeView, setActiveView] = useState<"chat" | "wheel" | "events" | null>(
    null
  );
  const nodes = useCanvasStore((state) => state.nodes);
  const addNode = useCanvasStore((state) => state.addNode);
  const updateNodePosition = useCanvasStore((state) => state.updateNodePosition);
  const updateNode = useCanvasStore((state) => state.updateNode);
  const selectNode = useCanvasStore((state) => state.selectNode);
  const clearSelection = useCanvasStore((state) => state.clearSelection);
  const selectedNodeId = useCanvasStore((state) => state.selectedNodeId);
  const selectedNodeIds = useCanvasStore((state) => state.selectedNodeIds);
  const conversationScope = useConversationStore((state) => state.scope);
  const setNodeScope = useConversationStore((state) => state.setNodeScope);
  const setGlobalScope = useConversationStore((state) => state.setGlobalScope);
  const selectionIds = getSelectionIds(selectedNodeIds, selectedNodeId);
  const selectionItems = getSelectionScopeItems(selectionIds, nodes);
  const nodeContext = buildNodeContext(selectionIds, nodes);
  const selectionScope: SelectionScope = {
    selected_nodes: selectionIds,
    selected_edges: [],
    node_context: nodeContext.length > 0 ? nodeContext : undefined,
  };

  // Sync conversation scope with primary selected node
  useEffect(() => {
    if (selectedNodeId) {
      const node = nodes.find((n) => n.id === selectedNodeId);
      if (node) {
        setNodeScope(node.id, node.title, Boolean(node.content));
      }
    } else {
      setGlobalScope();
    }
  }, [selectedNodeId, nodes, setNodeScope, setGlobalScope]);

  // Handler to clear node context (also clears selection)
  const handleClearContext = useCallback(() => {
    clearSelection();
    setGlobalScope();
  }, [clearSelection, setGlobalScope]);

  const currentRound = useMemo(() => {
    if (!activeRoundId) {
      return null;
    }
    return workflowRounds.find((round) => round.id === activeRoundId) ?? null;
  }, [activeRoundId, workflowRounds]);

  const previousRounds = useMemo(() => {
    if (!activeRoundId) {
      return workflowRounds;
    }
    return workflowRounds.filter((round) => round.id !== activeRoundId);
  }, [activeRoundId, workflowRounds]);

  // Handle WebSocket messages for real-time node updates from backend
  const handleWebSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      if (message.type === "node.created" && message.payload) {
        const payload = message.payload as {
          id: string;
          type: string;
          title: string;
          content?: string;
          x: number;
          y: number;
          z: number;
          metadata?: Record<string, unknown>;
        };
        const nodeId = String(payload.id);
        console.log("DEBUG: Received node.created from backend:", payload);
        // Check if node already exists (to avoid duplicates from local creation)
        const existingNode = nodes.find((n) => n.id === nodeId);
        if (!existingNode) {
          addNode({
            id: nodeId,
            type: (payload.type as CanvasNode["type"]) || "text",
            x: payload.x,
            y: payload.y,
            z: payload.z,
            title: payload.title,
            content: payload.content,
            metadata: payload.metadata,
          });
          console.log("DEBUG: Added backend-created node:", payload.id);
          if (!selectedNodeId && selectedNodeIds.length === 0) {
            selectNode(nodeId);
          }
        } else {
          console.log("DEBUG: Node already exists, skipping:", payload.id);
        }
      }
      if (message.type === "node.updated" && message.payload) {
        const payload = message.payload as {
          id: string;
          type?: string;
          title?: string;
          content?: string;
          x?: number;
          y?: number;
          z?: number;
          previous?: {
            x: number;
            y: number;
            z?: number;
          };
          metadata?: Record<string, unknown>;
        };
        let nodeId = String(payload.id);
        let targetNode = nodes.find((node) => node.id === nodeId);
        if (!targetNode && payload.previous) {
          targetNode = nodes.find((node) =>
            node.x === payload.previous?.x &&
            node.y === payload.previous?.y &&
            (payload.previous?.z === undefined || node.z === payload.previous.z)
          );
          if (targetNode) {
            nodeId = targetNode.id;
          }
        }
        if (!targetNode) {
          console.warn("DEBUG: node.updated for missing node:", nodeId);
          return;
        }
        if (payload.x !== undefined && payload.y !== undefined) {
          updateNodePosition(nodeId, payload.x, payload.y, payload.z);
        }
        const updates: Partial<CanvasNode> = {};
        if (payload.type !== undefined) updates.type = payload.type as CanvasNode["type"];
        if (payload.title !== undefined) updates.title = payload.title;
        if (payload.content !== undefined) updates.content = payload.content;
        if (payload.metadata !== undefined) updates.metadata = payload.metadata;
        if (Object.keys(updates).length > 0) {
          updateNode(nodeId, updates);
        }
      }
    },
    [nodes, addNode, updateNodePosition, updateNode, selectNode, selectedNodeId, selectedNodeIds]
  );

  // Connect to WebSocket for real-time updates
  const { sessionId: wsSessionId } = useWebSocketEnhanced({
    url: WS_URL,
    onMessage: handleWebSocketMessage,
  });

  const chatSessionIds = useMemo(() => {
    const ids = new Set<string>();
    if (wsSessionId) {
      ids.add(wsSessionId);
    }
    for (const round of workflowRounds) {
      const sessionId = round.assumptionSet?.sessionId;
      if (sessionId) {
        ids.add(sessionId);
      }
    }
    return Array.from(ids);
  }, [wsSessionId, workflowRounds]);

  const isChatOpen = activeView === "chat";
  const isWheelOpen = activeView === "wheel";
  const isEventsOpen = activeView === "events";
  const isTurnsOpen = isWheelOpen || isEventsOpen;

  const {
    turns: chatTurns,
    isLoading: isChatLoading,
    error: chatError,
  } = useChatTurns({
    sessionIds: chatSessionIds,
    enabled: isChatOpen,
  });

  const {
    turns: timelineTurns,
    isLoading: isTurnsLoading,
    error: turnsError,
  } = useTurns({
    sessionIds: chatSessionIds,
    enabled: isTurnsOpen,
  });

  useEffect(() => {
    if (routingError) {
      setStatusMessage(`Routing error: ${routingError}`);
      return;
    }
    if (currentRound && currentRound.status === "reviewing") {
      if ((currentRound.clarifyingQuestions?.length ?? 0) > 0) {
        setStatusMessage("Clarification needed.");
        return;
      }
      const pendingCount = currentRound.assumptions.filter(
        (assumption) => assumption.status === "pending"
      ).length;
      if (pendingCount > 0) {
        setStatusMessage(`${pendingCount} assumptions need review.`);
        return;
      }
      setStatusMessage("Review the proposal.");
      return;
    }
    if (commands.length > 0) {
      setStatusMessage("Command queued.");
      return;
    }
    setStatusMessage("Ready for commands.");
  }, [commands.length, currentRound, routingError]);

  useEffect(() => {
    if (!activeRoundId) {
      return;
    }
    if (!workflowRounds.some((round) => round.id === activeRoundId)) {
      setActiveRoundId(null);
    }
  }, [activeRoundId, workflowRounds]);

  const handleFilesDrop = (files: File[]) => {
    const names = files.map((file) => file.name).filter(Boolean);
    if (names.length === 0) return;
    setAttachments((prev) => {
      const next = [...prev];
      for (const name of names) {
        if (!next.includes(name)) {
          next.push(name);
        }
      }
      return next;
    });
  };

  const handleRemoveAttachment = (name: string) => {
    setAttachments((prev) => prev.filter((item) => item !== name));
  };

  const updateRound = useCallback(
    (roundId: string, updater: (round: WorkflowRound) => WorkflowRound) => {
      setWorkflowRounds((prev) =>
        prev.map((round) => (round.id === roundId ? updater(round) : round))
      );
    },
    []
  );

  const queueCommand = async (
    value: string,
    attachmentsForSubmission: string[],
    selection: SelectionScope
  ) => {
    const response = await fetch(`${API_BASE_URL}/api/commands`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        command: value,
        attachments: attachmentsForSubmission,
        selection,
        session_id: wsSessionId,
      }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data: { correlation_id: string; status: string } = await response.json();
    setCommands((prev) => [
      ...prev,
      { id: data.correlation_id, text: value, attachments: attachmentsForSubmission },
    ]);
    setAttachments([]);
    // Node creation is now handled by the backend via WebSocket broadcast
    // The handleWebSocketMessage callback will add the node when it receives "node.created"
  };

  const handleCommandSubmit = async (value: string) => {
    setRoutingError(null);
    const normalizedValue = value.trim().toLowerCase();
    if (normalizedValue === "close all panels") {
      setActiveView(null);
      setStatusMessage("Panels closed.");
      return;
    }
    const attachmentsForSubmission = [...attachments];
    const selection = selectionScope;

    // Clear selection immediately after capturing it for the command
    // This allows new nodes (created via WebSocket) to be auto-selected
    clearSelection();

    try {
      const assumptionResponse = await fetch(`${API_BASE_URL}/api/context/assumptions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: value,
          attachments: attachmentsForSubmission,
        }),
      });

      if (!assumptionResponse.ok) {
        throw new Error(
          `Assumptions API error: ${assumptionResponse.status} ${assumptionResponse.statusText}`
        );
      }

      const assumptionData: AssumptionSetResponse = await assumptionResponse.json();
      const nextRound = createWorkflowRound(
        assumptionData,
        value,
        attachmentsForSubmission,
        selection
      );

      if (nextRound) {
        setWorkflowRounds((prev) => [...prev, nextRound]);
        setActiveRoundId(nextRound.id);
        setAttachments([]);
        return;
      }
    } catch (error) {
      console.error("Assumptions check failed:", error);
    }

    try {
      await queueCommand(value, attachmentsForSubmission, selection);
    } catch (error) {
      console.error("Routing failed:", error);
      setRoutingError(error instanceof Error ? error.message : "Unknown error");
    }
  };

  const handleAcceptAssumption = (id: string) => {
    if (!activeRoundId || currentRound?.status !== "reviewing") {
      return;
    }
    updateRound(activeRoundId, (round) => ({
      ...round,
      assumptions: round.assumptions.map((assumption) =>
        assumption.id === id
          ? { ...assumption, status: "accepted" as const }
          : assumption
      ),
    }));
  };

  const handleRejectAssumption = (id: string) => {
    if (!activeRoundId || currentRound?.status !== "reviewing") {
      return;
    }
    updateRound(activeRoundId, (round) => ({
      ...round,
      assumptions: round.assumptions.map((assumption) =>
        assumption.id === id
          ? { ...assumption, status: "rejected" as const }
          : assumption
      ),
    }));
  };

  const handleEditAssumption = (id: string, text: string) => {
    if (!activeRoundId || currentRound?.status !== "reviewing") {
      return;
    }
    updateRound(activeRoundId, (round) => ({
      ...round,
      assumptions: round.assumptions.map((assumption) =>
        assumption.id === id
          ? { ...assumption, text, status: "accepted" as const }
          : assumption
      ),
    }));
  };

  const handleConfirmAssumptions = async () => {
    if (!currentRound || currentRound.status !== "reviewing") {
      return;
    }
    if ((currentRound.clarifyingQuestions?.length ?? 0) > 0) {
      return;
    }
    const roundId = currentRound.id;
    const resolutions = buildAssumptionResolutions(currentRound.assumptions);

    try {
      await persistAssumptionResolutions({
        session_id: currentRound.assumptionSet?.sessionId ?? undefined,
        resolutions,
      });
    } catch (error) {
      console.error("Failed to store assumption resolutions:", error);
    }

    try {
      await completeAssumptionSession(currentRound.assumptionSet?.sessionId ?? undefined);
    } catch (error) {
      console.error("Failed to mark assumption session complete:", error);
    }

    updateRound(roundId, (round) => ({ ...round, status: "resolved" }));

    try {
      await queueCommand(
        currentRound.commandText,
        currentRound.attachments,
        currentRound.selection
      );
      updateRound(roundId, (round) => ({ ...round, status: "executed" }));
    } catch (error) {
      console.error("Routing failed:", error);
      setRoutingError(error instanceof Error ? error.message : "Unknown error");
    }
  };

  const requestFollowupRound = async (note?: string) => {
    if (!currentRound || currentRound.status !== "reviewing") {
      return;
    }
    setRoutingError(null);
    const resolutions = buildAssumptionResolutions(currentRound.assumptions);
    if (resolutions.length > 0) {
      try {
        await persistAssumptionResolutions({
          session_id: currentRound.assumptionSet?.sessionId ?? undefined,
          resolutions,
        });
      } catch (error) {
        console.error("Failed to store assumption revisions:", error);
      }
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/context/assumptions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: buildRevisionPrompt(currentRound, note),
          attachments: currentRound.attachments,
        }),
      });

      if (!response.ok) {
        throw new Error(
          `Assumptions API error: ${response.status} ${response.statusText}`
        );
      }

      const assumptionData: AssumptionSetResponse = await response.json();
      const nextRound = createWorkflowRound(
        assumptionData,
        currentRound.commandText,
        currentRound.attachments,
        currentRound.selection,
        { force: true }
      );

      if (!nextRound) {
        return;
      }

      setWorkflowRounds((prev) =>
        prev
          .map((round) =>
            round.id === currentRound.id
              ? {
                  ...round,
                  status: "superseded" as const,
                  clarificationResponse: note ?? round.clarificationResponse,
                }
              : round
          )
          .concat(nextRound)
      );
      setActiveRoundId(nextRound.id);
    } catch (error) {
      console.error("Assumptions follow-up failed:", error);
      setRoutingError(error instanceof Error ? error.message : "Unknown error");
    }
  };

  const handleRequestRevision = () => {
    void requestFollowupRound();
  };

  const handleClarificationSubmit = (note: string) => {
    void requestFollowupRound(note);
  };

  const handleDismissAssumptions = () => {
    if (!activeRoundId) {
      return;
    }
    updateRound(activeRoundId, (round) => ({ ...round, status: "dismissed" }));
    setActiveRoundId(null);
  };

  const handleViewToggle = (view: "chat" | "wheel" | "events") => {
    setActiveView((prev) => (prev === view ? null : view));
  };

  const chatPanel = isChatOpen ? (
    <ChatViewPanel
      id="chat-view-panel"
      turns={chatTurns}
      isLoading={isChatLoading}
      error={chatError}
    />
  ) : null;

  const eventsPanel = isEventsOpen ? (
    <EventsViewPanel
      id="events-view-panel"
      turns={timelineTurns}
      isLoading={isTurnsLoading}
      error={turnsError}
    />
  ) : null;

  const wheelPanel = isWheelOpen ? (
    <WheelViewPanel
      id="wheel-view-panel"
      turns={timelineTurns}
      isLoading={isTurnsLoading}
      error={turnsError}
    />
  ) : null;

  const visiblePreviousRounds = previousRounds.filter(
    (round) => round.status !== "dismissed"
  );

  const workflowPanel =
    currentRound || visiblePreviousRounds.length > 0 ? (
      <AssumptionsPanel
        key={currentRound?.id ?? "intent-workflow"}
        id="intent-workflow-panel"
        currentRound={currentRound}
        previousRounds={visiblePreviousRounds}
        onAccept={handleAcceptAssumption}
        onReject={handleRejectAssumption}
        onEdit={handleEditAssumption}
        onConfirm={handleConfirmAssumptions}
        onDismiss={handleDismissAssumptions}
        onRequestRevision={handleRequestRevision}
        onClarificationSubmit={handleClarificationSubmit}
      />
    ) : null;

  const viewPanel = isChatOpen
    ? chatPanel
    : isWheelOpen
      ? wheelPanel
      : isEventsOpen
        ? eventsPanel
        : null;

  const panelContent =
    workflowPanel || viewPanel ? (
      <>
        {workflowPanel}
        {viewPanel}
      </>
    ) : null;

  return (
    <>
      <Canvas>
        <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
          {statusMessage}
        </div>
        <CanvasWorkspace />
        {commands.length > 0 && (
          <div style={{ position: "absolute", top: "20px", left: "20px", color: "#fff" }}>
            <h3>Commands:</h3>
            <ul>
              {commands.map((cmd) => (
                <li key={cmd.id}>
                  <div>{cmd.text}</div>
                  <div style={{ fontSize: "12px", color: "#cbd5f5" }}>
                    ID: {cmd.id}
                  </div>
                  {cmd.attachments.length > 0 && (
                    <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                      Attachments: {cmd.attachments.join(", ")}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {routingError && (
          <div
            style={{
              position: "absolute",
              bottom: "100px",
              left: "50%",
              transform: "translateX(-50%)",
              padding: "1rem",
              backgroundColor: "#7f1d1d",
              border: "1px solid #ef4444",
              borderRadius: "0.5rem",
              color: "#fecaca",
            }}
            role="alert"
            aria-live="assertive"
          >
            Error: {routingError}
          </div>
        )}
      </Canvas>
      <FloatingInput
        onSubmit={handleCommandSubmit}
        onFilesDrop={handleFilesDrop}
        attachments={attachments}
        selection={selectionItems}
        onRemoveAttachment={handleRemoveAttachment}
        onClearSelection={clearSelection}
        placeholder="Type a command..."
        panelContent={panelContent}
        conversationScope={conversationScope}
        onClearContext={handleClearContext}
        panelToggles={[
          {
            label: "Chat",
            isOpen: isChatOpen,
            onToggle: () => handleViewToggle("chat"),
            ariaControls: "chat-view-panel",
          },
          {
            label: "Wheel",
            isOpen: isWheelOpen,
            onToggle: () => handleViewToggle("wheel"),
            ariaControls: "wheel-view-panel",
          },
          {
            label: "Events",
            isOpen: isEventsOpen,
            onToggle: () => handleViewToggle("events"),
            ariaControls: "events-view-panel",
          },
        ]}
      />
    </>
  );
}
