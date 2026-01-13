"use client";

import { useMemo } from "react";
import { useCanvasStore } from "../../state/canvasStore";

interface DashboardNodeProps {
  nodeId?: string;
}

type CountMap = Record<string, number>;

const formatLabel = (value: string) =>
  value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());

const countBy = <T,>(items: T[], getKey: (item: T) => string): CountMap =>
  items.reduce<CountMap>((acc, item) => {
    const key = getKey(item);
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

export function DashboardNode({ nodeId }: DashboardNodeProps) {
  const nodes = useCanvasStore((state) => state.nodes);
  const edges = useCanvasStore((state) => state.edges);
  const documents = useCanvasStore((state) => state.documents);
  const selectedNodeIds = useCanvasStore((state) => state.selectedNodeIds);
  const selectedNodeId = useCanvasStore((state) => state.selectedNodeId);

  const selectionCount =
    selectedNodeIds.length > 0
      ? selectedNodeIds.length
      : selectedNodeId
        ? 1
        : 0;

  const scopedNodes = useMemo(
    () => (nodeId ? nodes.filter((node) => node.id !== nodeId) : nodes),
    [nodeId, nodes]
  );

  const nodeTypeCounts = useMemo(
    () => countBy(scopedNodes, (node) => node.type),
    [scopedNodes]
  );

  const edgeRelationCounts = useMemo(
    () => countBy(edges, (edge) => edge.relationType ?? "untyped"),
    [edges]
  );

  const dagTasks = useMemo(
    () => scopedNodes.flatMap((node) => node.dagData?.tasks ?? []),
    [scopedNodes]
  );

  const dagStatusCounts = useMemo(() => countBy(dagTasks, (task) => task.status), [dagTasks]);

  const sortedTypeEntries = useMemo(
    () =>
      Object.entries(nodeTypeCounts).sort(([, a], [, b]) => b - a),
    [nodeTypeCounts]
  );

  const sortedRelationEntries = useMemo(
    () =>
      Object.entries(edgeRelationCounts).sort(([, a], [, b]) => b - a),
    [edgeRelationCounts]
  );

  const dagTotals = useMemo(
    () => ({
      total: dagTasks.length,
      pending: dagStatusCounts.pending ?? 0,
      in_progress: dagStatusCounts.in_progress ?? 0,
      completed: dagStatusCounts.completed ?? 0,
      blocked: dagStatusCounts.blocked ?? 0,
    }),
    [dagStatusCounts, dagTasks.length]
  );

  return (
    <div
      role="region"
      aria-label="Live dashboard"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        color: "#e2e8f0",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: "12px", letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8" }}>
          Workspace Pulse
        </div>
        <div
          style={{
            fontSize: "11px",
            color: "#38bdf8",
            backgroundColor: "rgba(14, 116, 144, 0.25)",
            border: "1px solid rgba(56, 189, 248, 0.4)",
            padding: "2px 8px",
            borderRadius: "999px",
          }}
        >
          Live
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: "8px",
        }}
      >
        {[
          { label: "Nodes", value: scopedNodes.length },
          { label: "Edges", value: edges.length },
          { label: "Docs", value: documents.length },
          { label: "Selected", value: selectionCount },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              backgroundColor: "rgba(15, 23, 42, 0.55)",
              border: "1px solid rgba(148, 163, 184, 0.25)",
              borderRadius: "8px",
              padding: "8px 10px",
            }}
          >
            <div style={{ fontSize: "11px", color: "#94a3b8" }}>{item.label}</div>
            <div style={{ fontSize: "18px", fontWeight: 600 }}>{item.value}</div>
          </div>
        ))}
      </div>

      <div>
        <div style={{ fontSize: "12px", color: "#a0aec0", marginBottom: "6px" }}>Node Types</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {sortedTypeEntries.length === 0 ? (
            <span style={{ fontSize: "12px", color: "#64748b" }}>No nodes yet</span>
          ) : (
            sortedTypeEntries.map(([type, count]) => (
              <span
                key={type}
                style={{
                  fontSize: "11px",
                  padding: "3px 8px",
                  borderRadius: "999px",
                  backgroundColor: "rgba(30, 41, 59, 0.7)",
                  border: "1px solid rgba(148, 163, 184, 0.25)",
                  color: "#e2e8f0",
                }}
              >
                {formatLabel(type)} · {count}
              </span>
            ))
          )}
        </div>
      </div>

      <div>
        <div style={{ fontSize: "12px", color: "#a0aec0", marginBottom: "6px" }}>Edge Signals</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {sortedRelationEntries.length === 0 ? (
            <span style={{ fontSize: "12px", color: "#64748b" }}>No edges yet</span>
          ) : (
            sortedRelationEntries.map(([relation, count]) => (
              <span
                key={relation}
                style={{
                  fontSize: "11px",
                  padding: "3px 8px",
                  borderRadius: "999px",
                  backgroundColor: "rgba(15, 23, 42, 0.6)",
                  border: "1px solid rgba(56, 189, 248, 0.35)",
                  color: "#bae6fd",
                }}
              >
                {formatLabel(relation)} · {count}
              </span>
            ))
          )}
        </div>
      </div>

      <div>
        <div style={{ fontSize: "12px", color: "#a0aec0", marginBottom: "6px" }}>
          DAG Task Flow
        </div>
        {dagTotals.total === 0 ? (
          <div style={{ fontSize: "12px", color: "#64748b" }}>
            No DAG tasks tracked yet.
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "6px" }}>
            {(
              [
                ["Pending", dagTotals.pending, "#94a3b8"],
                ["In Progress", dagTotals.in_progress, "#38bdf8"],
                ["Completed", dagTotals.completed, "#34d399"],
                ["Blocked", dagTotals.blocked, "#f87171"],
              ] as Array<[string, number, string]>
            ).map(([label, value, color]) => (
              <div
                key={label}
                style={{
                  backgroundColor: "rgba(15, 23, 42, 0.55)",
                  border: `1px solid ${color}66`,
                  borderRadius: "8px",
                  padding: "6px 8px",
                }}
              >
                <div style={{ fontSize: "10px", color }}>{label}</div>
                <div style={{ fontSize: "14px", fontWeight: 600 }}>{value}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
