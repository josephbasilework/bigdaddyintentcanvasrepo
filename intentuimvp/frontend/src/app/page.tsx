"use client";

import { Canvas, CanvasWorkspace } from "@/components/Canvas";
import { FloatingInput } from "@/components/ContextInput/FloatingInput";
import { AssumptionsPanel } from "@/components/Assumptions";
import type { Assumption, AssumptionSet } from "@/components/Assumptions";
import { useCanvasStore } from "@/state/canvasStore";
import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
