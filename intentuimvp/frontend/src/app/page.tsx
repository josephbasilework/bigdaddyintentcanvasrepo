"use client";

import { Canvas, CanvasWorkspace } from "@/components/Canvas";
import { FloatingInput } from "@/components/ContextInput/FloatingInput";
import { ChatViewPanel } from "@/components/ChatView";
import { EventsViewPanel } from "@/components/EventsView";
import { AssumptionsPanel } from "@/components/Assumptions";
import type { Assumption, AssumptionSet } from "@/components/Assumptions";
import { useCanvasStore, type CanvasNode } from "@/state/canvasStore";
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

type SelectionScope = {
  selected_nodes: string[];
  selected_edges: string[];
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
): Array<{ id: string; label: string }> => {
  if (selectionIds.length === 0) {
    return [];
  }
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  return selectionIds.map((id) => {
    const node = nodeById.get(id);
    return {
      id,
      label: node?.title ?? "Unknown node",
    };
  });
};

type PendingCommand = {
  text: string;
  attachments: string[];
  selection: SelectionScope;
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

export default function Home() {
  const [commands, setCommands] = useState<CommandSubmissionLog[]>([]);
  const [assumptions, setAssumptions] = useState<Assumption[]>([]);
  const [assumptionSet, setAssumptionSet] = useState<AssumptionSet | null>(null);
  const [pendingCommand, setPendingCommand] = useState<PendingCommand | null>(null);
  const [routingError, setRoutingError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("Ready for commands.");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [activeView, setActiveView] = useState<"chat" | "events" | null>(null);
  const nodes = useCanvasStore((state) => state.nodes);
  const addNode = useCanvasStore((state) => state.addNode);
  const updateNodePosition = useCanvasStore((state) => state.updateNodePosition);
  const updateNode = useCanvasStore((state) => state.updateNode);
  const selectNode = useCanvasStore((state) => state.selectNode);
  const selectedNodeId = useCanvasStore((state) => state.selectedNodeId);
  const selectedNodeIds = useCanvasStore((state) => state.selectedNodeIds);
  const selectionIds = getSelectionIds(selectedNodeIds, selectedNodeId);
  const selectionItems = getSelectionScopeItems(selectionIds, nodes);
  const selectionScope: SelectionScope = {
    selected_nodes: selectionIds,
    selected_edges: [],
  };

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
    const ids = [wsSessionId, assumptionSet?.sessionId].filter(Boolean) as string[];
    return Array.from(new Set(ids));
  }, [wsSessionId, assumptionSet?.sessionId]);

  const isChatOpen = activeView === "chat";
  const isEventsOpen = activeView === "events";

  const {
    turns: chatTurns,
    isLoading: isChatLoading,
    error: chatError,
  } = useChatTurns({
    sessionIds: chatSessionIds,
    enabled: isChatOpen,
  });

  const {
    turns: eventTurns,
    isLoading: isEventsLoading,
    error: eventsError,
  } = useTurns({
    sessionIds: chatSessionIds,
    enabled: isEventsOpen,
  });

  useEffect(() => {
    if (routingError) {
      setStatusMessage(`Routing error: ${routingError}`);
      return;
    }
    if (assumptions.length > 0) {
      setStatusMessage(`${assumptions.length} assumptions need review.`);
      return;
    }
    if (commands.length > 0) {
      setStatusMessage("Command queued.");
      return;
    }
    setStatusMessage("Ready for commands.");
  }, [assumptions.length, commands.length, routingError]);

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

  const clearAssumptions = () => {
    setAssumptions([]);
    setAssumptionSet(null);
    setPendingCommand(null);
  };

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
    console.log("Command queued:", data);
  };

  const handleCommandSubmit = async (value: string) => {
    setRoutingError(null);
    const attachmentsForSubmission = [...attachments];
    const selection = selectionScope;

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
      console.log("DEBUG: Assumptions API response:", assumptionData);
      console.log("DEBUG: Assumptions count:", assumptionData.assumptions?.length ?? 0);

      if (assumptionData.assumptions.length > 0) {
        const mapped = assumptionData.assumptions.map(mapAssumptionResponse);
        console.log("DEBUG: Setting assumptions state:", mapped);
        setAssumptions(mapped);
        setAssumptionSet({
          intent: assumptionData.intent,
          intentDescription: assumptionData.intent_description ?? undefined,
          confidence: assumptionData.confidence,
          reasoning: assumptionData.reasoning,
          alternatives: assumptionData.alternatives ?? [],
          sessionId: assumptionData.session_id ?? undefined,
        });
        setPendingCommand({
          text: value,
          attachments: attachmentsForSubmission,
          selection,
        });
        setAttachments([]);
        console.log("DEBUG: State updated, returning early (should show panel)");
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
    setAssumptions((prev) =>
      prev.map((a) => (a.id === id ? { ...a, status: "accepted" as const } : a))
    );
  };

  const handleRejectAssumption = (id: string) => {
    setAssumptions((prev) =>
      prev.map((a) => (a.id === id ? { ...a, status: "rejected" as const } : a))
    );
  };

  const handleEditAssumption = (id: string, text: string) => {
    setAssumptions((prev) =>
      prev.map((a) => (a.id === id ? { ...a, text } : a))
    );
  };

  const handleConfirmAssumptions = async () => {
    const accepted = assumptions.filter((a) => a.status === "accepted");
    const rejected = assumptions.filter((a) => a.status === "rejected");
    const commandToSend = pendingCommand;
    const resolutions = buildAssumptionResolutions(assumptions);

    console.log("Assumptions confirmed:", {
      accepted,
      rejected,
      sessionId: assumptionSet?.sessionId,
    });

    try {
      await persistAssumptionResolutions({
        session_id: assumptionSet?.sessionId ?? undefined,
        resolutions,
      });
    } catch (error) {
      console.error("Failed to store assumption resolutions:", error);
    }

    clearAssumptions();

    if (!commandToSend) {
      return;
    }

    try {
      await queueCommand(
        commandToSend.text,
        commandToSend.attachments,
        commandToSend.selection
      );
    } catch (error) {
      console.error("Routing failed:", error);
      setRoutingError(error instanceof Error ? error.message : "Unknown error");
    }
  };

  const handleDismissAssumptions = () => {
    clearAssumptions();
  };

  const handleViewToggle = (view: "chat" | "events") => {
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
      turns={eventTurns}
      isLoading={isEventsLoading}
      error={eventsError}
    />
  ) : null;

  const panelContent = isChatOpen ? chatPanel : isEventsOpen ? eventsPanel : null;

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
      {console.log("DEBUG: Render check - assumptions.length:", assumptions.length)}
      {assumptions.length > 0 && (
        <AssumptionsPanel
          assumptions={assumptions}
          assumptionSet={assumptionSet ?? undefined}
          onAccept={handleAcceptAssumption}
          onReject={handleRejectAssumption}
          onEdit={handleEditAssumption}
          onConfirm={handleConfirmAssumptions}
          onDismiss={handleDismissAssumptions}
        />
      )}
      <FloatingInput
        onSubmit={handleCommandSubmit}
        onFilesDrop={handleFilesDrop}
        attachments={attachments}
        selection={selectionItems}
        onRemoveAttachment={handleRemoveAttachment}
        placeholder="Type a command..."
        panelContent={panelContent}
        panelToggles={[
          {
            label: "Chat view",
            activeLabel: "Hide chat",
            isOpen: isChatOpen,
            onToggle: () => handleViewToggle("chat"),
            ariaControls: "chat-view-panel",
          },
          {
            label: "Events view",
            activeLabel: "Hide events",
            isOpen: isEventsOpen,
            onToggle: () => handleViewToggle("events"),
            ariaControls: "events-view-panel",
          },
        ]}
      />
    </>
  );
}
