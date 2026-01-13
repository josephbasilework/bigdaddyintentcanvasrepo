"use client";

import { useMemo } from "react";
import type { DAGData, DAGTask } from "../../state/canvasStore";

interface DAGNodeProps {
  dag: DAGData;
  onTaskClick?: (taskId: string) => void;
}

/**
 * DAGNode component for visualizing task DAGs (Directed Acyclic Graphs).
 *
 * Features:
 * - Hierarchical layout showing task dependencies
 * - Color-coded by status
 * - Priority indicators
 * - Click interaction for task details
 */
export function DAGNode({ dag, onTaskClick }: DAGNodeProps) {
  const { tasks, dependencies = [] } = dag;

  const layout = useMemo(() => {
    const depMap = new Map<string, string[]>();

    tasks.forEach((task) => {
      const blockers = dependencies
        .filter((d) => d.taskId === task.id)
        .map((d) => d.dependsOnTaskId);
      depMap.set(task.id, blockers);
    });

    const levels = new Map<string, number>();
    const inDegree = new Map<string, number>();

    tasks.forEach((task) => {
      inDegree.set(task.id, 0);
    });
    dependencies.forEach((dep) => {
      inDegree.set(dep.taskId, (inDegree.get(dep.taskId) || 0) + 1);
    });

    const queue: string[] = [];
    tasks.forEach((task) => {
      if (inDegree.get(task.id) === 0) {
        queue.push(task.id);
        levels.set(task.id, 0);
      }
    });

    while (queue.length > 0) {
      const taskId = queue.shift()!;
      const currentLevel = levels.get(taskId)!;

      dependencies
        .filter((d) => d.dependsOnTaskId === taskId)
        .forEach((dep) => {
          const newInDegree = (inDegree.get(dep.taskId) || 0) - 1;
          inDegree.set(dep.taskId, newInDegree);
          levels.set(dep.taskId, Math.max(levels.get(dep.taskId) || 0, currentLevel + 1));

          if (newInDegree === 0) {
            queue.push(dep.taskId);
          }
        });
    }

    const levelGroups = new Map<number, string[]>();
    tasks.forEach((task) => {
      const level = levels.get(task.id) ?? 0;
      if (!levelGroups.has(level)) {
        levelGroups.set(level, []);
      }
      levelGroups.get(level)!.push(task.id);
    });

    const positions = new Map<string, { x: number; y: number }>();
    const nodeWidth = 160;
    const nodeHeight = 70;
    const horizontalGap = 20;
    const verticalGap = 16;

    levelGroups.forEach((taskIds, level) => {
      const x = level * (nodeWidth + horizontalGap) + 20;
      taskIds.forEach((taskId, index) => {
        const y = index * (nodeHeight + verticalGap) + 20;
        positions.set(taskId, { x, y });
      });
    });

    const connections = dependencies
      .map((dep) => {
        const source = positions.get(dep.dependsOnTaskId);
        const target = positions.get(dep.taskId);
        if (!source || !target) return null;

        return {
          source,
          target,
          sourceId: dep.dependsOnTaskId,
          targetId: dep.taskId,
          type: dep.type || "hard",
        };
      })
      .filter(Boolean) as Array<{
      source: { x: number; y: number };
      target: { x: number; y: number };
      sourceId: string;
      targetId: string;
      type: string;
    }>;

    const maxLevel = Math.max(0, ...Array.from(levels.values()));
    const maxInLevel = Math.max(0, ...Array.from(levelGroups.values()).map((g) => g.length));
    const width = (maxLevel + 1) * (nodeWidth + horizontalGap) + 40;
    const height = maxInLevel * (nodeHeight + verticalGap) + 40;

    return { positions, connections, width, height };
  }, [tasks, dependencies]);

  const getStatusColor = (status: DAGTask["status"]) => {
    switch (status) {
      case "pending":
        return "#718096";
      case "in_progress":
        return "#4299e1";
      case "completed":
        return "#48bb78";
      case "blocked":
        return "#f56565";
      default:
        return "#718096";
    }
  };

  const getStatusIcon = (status: DAGTask["status"]) => {
    switch (status) {
      case "pending":
        return "○";
      case "in_progress":
        return "◐";
      case "completed":
        return "●";
      case "blocked":
        return "⊘";
      default:
        return "○";
    }
  };

  const getPriorityColor = (priority?: DAGTask["priority"]) => {
    switch (priority) {
      case "high":
        return "#f56565";
      case "medium":
        return "#ed8936";
      case "low":
        return "#48bb78";
      default:
        return "#718096";
    }
  };

  const generatePath = (
    source: { x: number; y: number },
    target: { x: number; y: number }
  ) => {
    const nodeWidth = 160;
    const nodeHeight = 70;
    const sourceX = source.x + nodeWidth;
    const sourceY = source.y + nodeHeight / 2;
    const targetX = target.x;
    const targetY = target.y + nodeHeight / 2;
    const midX = (sourceX + targetX) / 2;

    return `M ${sourceX} ${sourceY} C ${midX} ${sourceY}, ${midX} ${targetY}, ${targetX} ${targetY}`;
  };

  const handleTaskKeyDown = (e: React.KeyboardEvent<SVGGElement>, taskId: string) => {
    if (!onTaskClick) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onTaskClick(taskId);
    }
  };

  if (tasks.length === 0) {
    return (
      <div
        style={{
          padding: "16px",
          color: "#94a3b8",
          textAlign: "center",
          fontSize: "13px",
        }}
      >
        No tasks in this DAG
      </div>
    );
  }

  return (
    <div
      style={{
        width: "100%",
        minHeight: "200px",
        maxHeight: "400px",
        backgroundColor: "#0a0a0a",
        borderRadius: "6px",
        overflow: "auto",
        marginTop: "8px",
      }}
      role="region"
      aria-label={`Task DAG with ${tasks.length} tasks`}
    >
      <svg
        width={layout.width}
        height={layout.height}
        style={{ display: "block" }}
        role="group"
      >
        {/* Arrow marker definition */}
        <defs>
          <marker
            id="dag-arrow"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#4a5568" opacity="0.8" />
          </marker>
          <marker
            id="dag-arrow-soft"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#4a5568" opacity="0.4" />
          </marker>
        </defs>

        {/* Connections */}
        {layout.connections.map((conn, index) => (
          <path
            key={`conn-${index}`}
            d={generatePath(conn.source, conn.target)}
            stroke="#4a5568"
            strokeWidth={conn.type === "soft" ? "1" : "2"}
            strokeDasharray={conn.type === "soft" ? "4,4" : undefined}
            fill="none"
            opacity={conn.type === "soft" ? "0.5" : "0.7"}
            markerEnd={
              conn.type === "soft" ? "url(#dag-arrow-soft)" : "url(#dag-arrow)"
            }
          />
        ))}

        {/* Task nodes */}
        {tasks.map((task) => {
          const pos = layout.positions.get(task.id);
          if (!pos) return null;

          return (
            <g
              key={task.id}
              transform={`translate(${pos.x}, ${pos.y})`}
              style={{ cursor: onTaskClick ? "pointer" : "default" }}
              onClick={() => onTaskClick?.(task.id)}
              onKeyDown={(e) => handleTaskKeyDown(e, task.id)}
              tabIndex={onTaskClick ? 0 : -1}
              role={onTaskClick ? "button" : "group"}
              aria-label={`Task: ${task.title}, Status: ${task.status}${task.priority ? `, Priority: ${task.priority}` : ""}`}
            >
              {/* Node background */}
              <rect
                width="160"
                height="70"
                rx="6"
                fill="#1a202c"
                stroke={getStatusColor(task.status)}
                strokeWidth="2"
              />

              {/* Priority indicator */}
              <rect
                x="0"
                y="0"
                width="4"
                height="70"
                rx="2"
                fill={getPriorityColor(task.priority)}
              />

              {/* Status icon */}
              <text
                x="16"
                y="22"
                fontSize="14"
                fill={getStatusColor(task.status)}
              >
                {getStatusIcon(task.status)}
              </text>

              {/* Title */}
              <text
                x="32"
                y="22"
                fontSize="12"
                fontWeight="600"
                fill="#fff"
              >
                {task.title.length > 14 ? task.title.substring(0, 14) + "…" : task.title}
              </text>

              {/* Description (truncated) */}
              {task.description && (
                <text
                  x="12"
                  y="42"
                  fontSize="10"
                  fill="#94a3b8"
                >
                  {task.description.length > 22
                    ? task.description.substring(0, 22) + "…"
                    : task.description}
                </text>
              )}

              {/* Effort badge */}
              {task.estimatedEffort && (
                <g>
                  <rect
                    x="12"
                    y="52"
                    width="60"
                    height="14"
                    rx="3"
                    fill="rgba(72, 187, 120, 0.2)"
                  />
                  <text
                    x="16"
                    y="62"
                    fontSize="9"
                    fill="#48bb78"
                  >
                    {task.estimatedEffort.length > 10
                      ? task.estimatedEffort.substring(0, 10)
                      : task.estimatedEffort}
                  </text>
                </g>
              )}

              {/* Priority label */}
              {task.priority && (
                <g>
                  <rect
                    x="130"
                    y="5"
                    width="24"
                    height="14"
                    rx="3"
                    fill={getPriorityColor(task.priority)}
                    opacity="0.2"
                  />
                  <text
                    x="142"
                    y="15"
                    fontSize="8"
                    fill={getPriorityColor(task.priority)}
                    textAnchor="middle"
                  >
                    {task.priority.charAt(0).toUpperCase()}
                  </text>
                </g>
              )}
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div
        style={{
          padding: "8px 12px",
          borderTop: "1px solid #2d3748",
          fontSize: "10px",
          display: "flex",
          gap: "12px",
          color: "#94a3b8",
          flexWrap: "wrap",
        }}
      >
        <span>○ Pending</span>
        <span style={{ color: "#4299e1" }}>◐ In Progress</span>
        <span style={{ color: "#48bb78" }}>● Complete</span>
        <span style={{ color: "#f56565" }}>⊘ Blocked</span>
      </div>
    </div>
  );
}
