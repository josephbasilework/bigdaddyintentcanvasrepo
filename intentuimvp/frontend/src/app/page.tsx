"use client";

import { Canvas, CanvasWorkspace } from "@/components/Canvas";
import { FloatingInput } from "@/components/ContextInput/FloatingInput";
import { AssumptionsPanel } from "@/components/Assumptions";
import type { Assumption } from "@/components/Assumptions";
import { useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [commands, setCommands] = useState<string[]>([]);
  const [assumptions, setAssumptions] = useState<Assumption[]>([]);
  const [routingError, setRoutingError] = useState<string | null>(null);

  const handleCommandSubmit = async (value: string) => {
    console.log("Command submitted:", value);
    setCommands((prev) => [...prev, value]);
    setRoutingError(null);

    try {
      // Call context API to route the command
      const response = await fetch(`${API_BASE_URL}/api/context`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: value }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      console.log("Routing response:", data);

      // Check if there are assumptions to resolve
      if (data.assumptions && data.assumptions.length > 0) {
        // Add status field to assumptions
        const assumptionsWithStatus: Assumption[] = data.assumptions.map(
          (a: Omit<Assumption, "status">) => ({
            ...a,
            status: "pending" as const,
          })
        );
        setAssumptions(assumptionsWithStatus);
      } else {
        // No assumptions, proceed with execution
        console.log(`Executing with handler: ${data.handler}`);
        // TODO: Execute the command via the handler
      }
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
    <Canvas>
      <CanvasWorkspace />
      <FloatingInput onSubmit={handleCommandSubmit} placeholder="Type a command..." />
      {commands.length > 0 && (
        <div style={{ position: "absolute", top: "20px", left: "20px", color: "#fff" }}>
          <h3>Commands:</h3>
          <ul>
            {commands.map((cmd, i) => (
              <li key={i}>{cmd}</li>
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
  );
}
