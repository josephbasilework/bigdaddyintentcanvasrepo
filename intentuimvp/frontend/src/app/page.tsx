"use client";

import { Canvas, CanvasWorkspace } from "@/components/Canvas";
import { FloatingInput } from "@/components/ContextInput/FloatingInput";
import { AssumptionsPanel } from "@/components/Assumptions";
import type { Assumption, AssumptionSet } from "@/components/Assumptions";
import { useCanvasStore, type CanvasNode } from "@/state/canvasStore";
import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const MAX_NODE_TITLE_LENGTH = 72;
const DEFAULT_NODE_TYPE: CanvasNode["type"] = "text";
const COMMAND_NODE_TYPES: Record<string, CanvasNode["type"]> = {
  "/research": "document",
  "/judge": "document",
  "/plan": "graph",
  "/dashboard": "graph",
  "/graph": "graph",
  "/export": "document",
};
const COMMAND_LABELS: Record<string, string> = {
  "/research": "Research",
  "/judge": "Judge",
  "/plan": "Plan",
  "/dashboard": "Dashboard",
  "/graph": "Graph",
  "/export": "Export",
};

const truncateText = (value: string, maxLength: number): string => {
  if (value.length <= maxLength) {
    return value;
  }
  const sliceLength = Math.max(0, maxLength - 3);
  return `${value.slice(0, sliceLength).trimEnd()}...`;
};

const getViewportCenter = (): { x: number; y: number } => {
  if (typeof window === "undefined") {
    return { x: 160, y: 120 };
  }
  const x = Math.max(40, Math.round(window.innerWidth / 2) - 120);
  const y = Math.max(40, Math.round(window.innerHeight / 2) - 80);
  return { x, y };
};

const getNextNodePosition = (
  nodes: CanvasNode[],
  selectedNodeId: string | null
): { x: number; y: number; z: number } => {
  const maxZ = nodes.reduce((max, node) => Math.max(max, node.z), 0);
  const selectedNode = selectedNodeId
    ? nodes.find((node) => node.id === selectedNodeId)
    : undefined;

  if (selectedNode) {
    return {
      x: selectedNode.x + 240,
      y: selectedNode.y,
      z: maxZ + 1,
    };
  }

  if (nodes.length > 0) {
    const lastNode = nodes[nodes.length - 1];
    return {
      x: lastNode.x + 48,
      y: lastNode.y + 48,
      z: maxZ + 1,
    };
  }

  const fallback = getViewportCenter();
  return {
    x: fallback.x,
    y: fallback.y,
    z: maxZ + 1,
  };
};

type CommandSubmissionLog = {
  id: string;
  text: string;
  attachments: string[];
};

type SelectionScope = {
  selected_nodes: string[];
  selected_edges: string[];
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
  text: assumption.text,
  confidence: assumption.confidence,
  category: normalizeCategory(assumption.category),
  status: "pending",
  explanation: assumption.explanation ?? undefined,
});

export default function Home() {
  const [commands, setCommands] = useState<CommandSubmissionLog[]>([]);
  const [assumptions, setAssumptions] = useState<Assumption[]>([]);
  const [assumptionSet, setAssumptionSet] = useState<AssumptionSet | null>(null);
  const [pendingCommand, setPendingCommand] = useState<PendingCommand | null>(null);
  const [routingError, setRoutingError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("Ready for commands.");
  const [attachments, setAttachments] = useState<string[]>([]);
  const nodes = useCanvasStore((state) => state.nodes);
  const addNode = useCanvasStore((state) => state.addNode);
  const selectNode = useCanvasStore((state) => state.selectNode);
  const selectedNodeId = useCanvasStore((state) => state.selectedNodeId);

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

  const createNodeFromCommand = (value: string, attachmentsForSubmission: string[]) => {
    const trimmed = value.trim();
    if (!trimmed) return;

    const [commandToken, ...restTokens] = trimmed.split(/\s+/);
    const isSlashCommand = commandToken.startsWith("/");
    const commandKey = isSlashCommand ? commandToken.toLowerCase() : null;
    const commandLabel = commandKey ? COMMAND_LABELS[commandKey] : undefined;
    const commandType = commandKey ? COMMAND_NODE_TYPES[commandKey] : undefined;
    const body = isSlashCommand ? restTokens.join(" ").trim() : trimmed;

    const titleBase = isSlashCommand && commandLabel
      ? body
        ? `${commandLabel}: ${body}`
        : commandLabel
      : body || trimmed;
    const title = truncateText(titleBase, MAX_NODE_TITLE_LENGTH);
    const content = isSlashCommand ? (body || undefined) : (
      trimmed.length > MAX_NODE_TITLE_LENGTH ? trimmed : undefined
    );

    const metadata: Record<string, unknown> = {};
    if (commandKey) {
      metadata.command = commandKey;
    }
    if (attachmentsForSubmission.length > 0) {
      metadata.attachments = attachmentsForSubmission;
    }

    const { x, y, z } = getNextNodePosition(nodes, selectedNodeId);
    const nodeId = addNode({
      type: commandType ?? DEFAULT_NODE_TYPE,
      x,
      y,
      z,
      title,
      content,
      metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
    });
    selectNode(nodeId);
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
    createNodeFromCommand(value, attachmentsForSubmission);
    console.log("Command queued:", data);
  };

  const handleCommandSubmit = async (value: string) => {
    setRoutingError(null);
    const attachmentsForSubmission = [...attachments];
    const selection: SelectionScope = {
      selected_nodes: selectedNodeId ? [selectedNodeId] : [],
      selected_edges: [],
    };

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

      if (assumptionData.assumptions.length > 0) {
        setAssumptions(assumptionData.assumptions.map(mapAssumptionResponse));
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

  const handleConfirmAssumptions = async () => {
    const accepted = assumptions.filter((a) => a.status === "accepted");
    const rejected = assumptions.filter((a) => a.status === "rejected");
    const commandToSend = pendingCommand;

    console.log("Assumptions confirmed:", {
      accepted,
      rejected,
      sessionId: assumptionSet?.sessionId,
    });

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
      {assumptions.length > 0 && (
        <AssumptionsPanel
          assumptions={assumptions}
          assumptionSet={assumptionSet ?? undefined}
          onAccept={handleAcceptAssumption}
          onReject={handleRejectAssumption}
          onConfirm={handleConfirmAssumptions}
          onDismiss={handleDismissAssumptions}
        />
      )}
      <FloatingInput
        onSubmit={handleCommandSubmit}
        onFilesDrop={handleFilesDrop}
        attachments={attachments}
        onRemoveAttachment={handleRemoveAttachment}
        placeholder="Type a command..."
      />
    </>
  );
}
