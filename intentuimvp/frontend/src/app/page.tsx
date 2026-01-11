"use client";

import { Canvas, CanvasWorkspace } from "@/components/Canvas";
import { FloatingInput } from "@/components/ContextInput/FloatingInput";
import { AssumptionsPanel } from "@/components/Assumptions";
import type { Assumption } from "@/components/Assumptions";
import { useCanvasStore } from "@/state/canvasStore";
import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type CommandSubmissionLog = {
  id: string;
  text: string;
  attachments: string[];
};

export default function Home() {
  const [commands, setCommands] = useState<CommandSubmissionLog[]>([]);
  const [assumptions, setAssumptions] = useState<Assumption[]>([]);
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

  const handleCommandSubmit = async (value: string) => {
    setRoutingError(null);
    const attachmentsForSubmission = [...attachments];
    const selection = {
      selected_nodes: selectedNodeId ? [selectedNodeId] : [],
      selected_edges: [],
    };

    try {
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
    // Send resolutions to backend
    const accepted = assumptions.filter((a) => a.status === "accepted");
    const rejected = assumptions.filter((a) => a.status === "rejected");

    console.log("Assumptions confirmed:", { accepted, rejected });

    // TODO: Send to backend and proceed with execution
    setAssumptions([]);
  };

  const handleDismissAssumptions = () => {
    setAssumptions([]);
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
        {assumptions.length > 0 && (
          <AssumptionsPanel
            assumptions={assumptions}
            onAccept={handleAcceptAssumption}
            onReject={handleRejectAssumption}
            onConfirm={handleConfirmAssumptions}
            onDismiss={handleDismissAssumptions}
          />
        )}
      </Canvas>
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
