"use client";

import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  useCanvasStore,
  type LayoutDirection,
  type LayoutType,
} from "../../state/canvasStore";

const LAYOUT_OPTIONS: Array<{ value: LayoutType; label: string }> = [
  { value: "grid", label: "Grid" },
  { value: "tree", label: "Tree" },
  { value: "hierarchy", label: "Hierarchy" },
  { value: "force", label: "Force" },
];

const DIRECTION_OPTIONS: Array<{ value: LayoutDirection; label: string }> = [
  { value: "down", label: "Down" },
  { value: "right", label: "Right" },
];

export function CanvasLayoutControls() {
  const nodes = useCanvasStore((state) => state.nodes);
  const selectedNodeId = useCanvasStore((state) => state.selectedNodeId);
  const selectedNodeIds = useCanvasStore((state) => state.selectedNodeIds);
  const applyLayout = useCanvasStore((state) => state.applyLayout);

  const selectedIds = useMemo(() => {
    if (selectedNodeIds.length > 0) {
      return Array.from(new Set(selectedNodeIds));
    }
    return selectedNodeId ? [selectedNodeId] : [];
  }, [selectedNodeId, selectedNodeIds]);

  const hasSelection = selectedIds.length > 0;
  const [layout, setLayout] = useState<LayoutType>("grid");
  const [direction, setDirection] = useState<LayoutDirection>("down");
  const [scope, setScope] = useState<"selection" | "canvas">(
    hasSelection ? "selection" : "canvas"
  );
  const [lockLayout, setLockLayout] = useState(false);

  const resolvedScope = hasSelection ? scope : "canvas";

  const targetIds =
    resolvedScope === "selection" ? selectedIds : nodes.map((node) => node.id);
  const canApply = targetIds.length > 0;

  const handleApply = () => {
    if (!canApply) return;
    applyLayout(
      {
        layout,
        direction,
        nodeIds: targetIds,
        lock: lockLayout,
      },
      { source: "user" }
    );
  };

  if (typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div
      aria-label="Canvas layout controls"
      style={{
        position: "fixed",
        top: "88px",
        right: "24px",
        zIndex: 10020,
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        border: "1px solid rgba(148, 163, 184, 0.25)",
        borderRadius: "12px",
        padding: "12px",
        color: "#e2e8f0",
        width: "200px",
        boxShadow: "0 18px 40px rgba(0, 0, 0, 0.35)",
        backdropFilter: "blur(10px)",
      }}
    >
      <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>
        Auto-layout
      </div>
      <label style={{ display: "block", fontSize: "11px", marginBottom: "4px" }}>
        Layout
      </label>
      <select
        aria-label="Layout algorithm"
        value={layout}
        onChange={(event) => setLayout(event.target.value as LayoutType)}
        style={{
          width: "100%",
          padding: "6px 8px",
          borderRadius: "8px",
          border: "1px solid rgba(148, 163, 184, 0.4)",
          backgroundColor: "rgba(15, 23, 42, 0.65)",
          color: "#e2e8f0",
          marginBottom: "8px",
        }}
      >
        {LAYOUT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <label style={{ display: "block", fontSize: "11px", marginBottom: "4px" }}>
        Direction
      </label>
      <select
        aria-label="Layout direction"
        value={direction}
        onChange={(event) => setDirection(event.target.value as LayoutDirection)}
        style={{
          width: "100%",
          padding: "6px 8px",
          borderRadius: "8px",
          border: "1px solid rgba(148, 163, 184, 0.4)",
          backgroundColor: "rgba(15, 23, 42, 0.65)",
          color: "#e2e8f0",
          marginBottom: "8px",
        }}
      >
        {DIRECTION_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <label style={{ display: "block", fontSize: "11px", marginBottom: "4px" }}>
        Scope
      </label>
      <select
        aria-label="Layout scope"
        value={resolvedScope}
        onChange={(event) => setScope(event.target.value as "selection" | "canvas")}
        style={{
          width: "100%",
          padding: "6px 8px",
          borderRadius: "8px",
          border: "1px solid rgba(148, 163, 184, 0.4)",
          backgroundColor: "rgba(15, 23, 42, 0.65)",
          color: "#e2e8f0",
          marginBottom: "8px",
        }}
      >
        <option value="selection" disabled={!hasSelection}>
          Selection
        </option>
        <option value="canvas">Canvas</option>
      </select>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          fontSize: "11px",
          marginBottom: "10px",
        }}
      >
        <input
          type="checkbox"
          checked={lockLayout}
          onChange={(event) => setLockLayout(event.target.checked)}
          aria-label="Lock layout"
        />
        Lock layout
      </label>
      <button
        type="button"
        onClick={handleApply}
        disabled={!canApply}
        style={{
          width: "100%",
          padding: "7px 10px",
          borderRadius: "8px",
          border: "1px solid rgba(148, 163, 184, 0.4)",
          backgroundColor: canApply ? "rgba(59, 130, 246, 0.8)" : "rgba(148, 163, 184, 0.2)",
          color: "#f8fafc",
          fontWeight: 600,
          cursor: canApply ? "pointer" : "not-allowed",
        }}
      >
        Apply layout
      </button>
    </div>,
    document.body
  );
}
