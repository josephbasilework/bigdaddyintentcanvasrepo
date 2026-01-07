"use client";

import { Canvas } from "@/components/Canvas/Canvas";
import { FloatingInput } from "@/components/ContextInput/FloatingInput";
import { useState } from "react";

export default function Home() {
  const [commands, setCommands] = useState<string[]>([]);

  const handleCommandSubmit = (value: string) => {
    console.log("Command submitted:", value);
    setCommands((prev) => [...prev, value]);
  };

  return (
    <Canvas>
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
    </Canvas>
  );
}
