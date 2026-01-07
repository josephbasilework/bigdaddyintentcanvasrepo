"use client";

import { useMemo } from "react";

export interface TaskNode {
  id: string;
  title: string;
  status: "pending" | "in_progress" | "completed" | "blocked";
  assignee?: string;
  priority?: "P0" | "P1" | "P2" | "P3";
}

export interface TaskDependency {
  taskId: string;
  dependsOn: string; // ID of the blocking task
}

interface TaskDAGProps {
  tasks: TaskNode[];
  dependencies: TaskDependency[];
  width?: number;
  height?: number;
  onTaskClick?: (taskId: string) => void;
}

/**
 * TaskDAG component for visualizing tasks and their dependencies.
 *
 * Features:
 * - Hierarchical layout showing task dependencies
 * - Color-coded by status
 * - Priority indicators
 * - Assignee display
 * - Click interaction
 */
export function TaskDAG({
  tasks,
  dependencies,
  width = 600,
  height = 400,
  onTaskClick,
}: TaskDAGProps) {
  // Calculate layout positions using topological sort
  const layout = useMemo(() => {
    const taskMap = new Map(tasks.map((t) => [t.id, t]));
    const depMap = new Map<string, string[]>();

    // Build adjacency list for dependencies
    tasks.forEach((task) => {
      const blockers = dependencies
        .filter((d) => d.taskId === task.id)
        .map((d) => d.dependsOn);
      depMap.set(task.id, blockers);
    });

    // Topological sort to determine levels
    const visited = new Set<string>();
    const levels = new Map<string, number>();
    const inDegree = new Map<string, number>();

    // Initialize in-degrees
    tasks.forEach((task) => {
      inDegree.set(task.id, 0);
    });
    dependencies.forEach((dep) => {
      inDegree.set(dep.taskId, (inDegree.get(dep.taskId) || 0) + 1);
    });

    // BFS to assign levels
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

      // Find tasks that depend on this one
      dependencies
        .filter((d) => d.dependsOn === taskId)
        .forEach((dep) => {
          const newInDegree = (inDegree.get(dep.taskId) || 0) - 1;
          inDegree.set(dep.taskId, newInDegree);
          levels.set(dep.taskId, Math.max(levels.get(dep.taskId) || 0, currentLevel + 1));

          if (newInDegree === 0) {
            queue.push(dep.taskId);
          }
        });

      visited.add(taskId);
    }

    // Group tasks by level
    const levelGroups = new Map<number, string[]>();
    tasks.forEach((task) => {
      const level = levels.get(task.id) ?? 0;
      if (!levelGroups.has(level)) {
        levelGroups.set(level, []);
      }
      levelGroups.get(level)!.push(task.id);
    });

    // Calculate positions
    const positions = new Map<string, { x: number; y: number }>();
    const nodeWidth = 180;
    const nodeHeight = 80;
    const horizontalGap = 20;
    const verticalGap = 40;

    levelGroups.forEach((taskIds, level) => {
      const x = level * (nodeWidth + horizontalGap) + 40;
      taskIds.forEach((taskId, index) => {
        const y = index * (nodeHeight + verticalGap) + 40;
        positions.set(taskId, { x, y });
      });
    });

    // Calculate connections with waypoints
    const connections = dependencies.map((dep) => {
      const source = positions.get(dep.dependsOn);
      const target = positions.get(dep.taskId);
      if (!source || !target) return null;

      return {
        source,
        target,
        sourceId: dep.dependsOn,
        targetId: dep.taskId,
      };
    }).filter(Boolean) as Array<{
      source: { x: number; y: number };
      target: { x: number; y: number };
      sourceId: string;
      targetId: string;
    }>;

    return { positions, connections, maxLevel: Math.max(...Array.from(levels.values())) };
  }, [tasks, dependencies]);

  const getStatusColor = (status: TaskNode["status"]) => {
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

  const getStatusLabel = (status: TaskNode["status"]) => {
    switch (status) {
      case "pending":
        return "⏳";
      case "in_progress":
        return "🔄";
      case "completed":
        return "✅";
      case "blocked":
        return "🚫";
      default:
        return "⏳";
    }
  };

  const getPriorityColor = (priority?: TaskNode["priority"]) => {
    switch (priority) {
      case "P0":
        return "#f56565";
      case "P1":
        return "#ed8936";
      case "P2":
        return "#ecc94b";
      case "P3":
        return "#718096";
      default:
        return "#718096";
    }
  };

  // Generate path for curved connections
  const generatePath = (
    source: { x: number; y: number },
    target: { x: number; y: number }
  ) => {
    const sourceX = source.x + 180; // Right edge of source node
    const sourceY = source.y + 40; // Center of source node
    const targetX = target.x; // Left edge of target node
    const targetY = target.y + 40; // Center of target node

    const midX = (sourceX + targetX) / 2;

    return `M ${sourceX} ${sourceY} C ${midX} ${sourceY}, ${midX} ${targetY}, ${targetX} ${targetY}`;
  };

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#0a0a0a",
        borderRadius: "8px",
        overflow: "auto",
        position: "relative",
      }}
    >
      <svg
        width={width}
        height={height}
        style={{
          display: "block",
          minWidth: "100%",
          minHeight: "100%",
        }}
      >
        {/* Connections */}
        {layout.connections.map((conn, index) => (
          <g key={`conn-${index}`}>
            <path
              d={generatePath(conn.source, conn.target)}
              stroke="#4a5568"
              strokeWidth="2"
              fill="none"
              opacity="0.6"
            />
            {/* Arrow head */}
            <defs>
              <marker
                id={`arrow-${index}`}
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#4a5568" opacity="0.6" />
              </marker>
            </defs>
            <path
              d={generatePath(conn.source, conn.target)}
              stroke="#4a5568"
              strokeWidth="2"
              fill="none"
              opacity="0.6"
              markerEnd={`url(#arrow-${index})`}
            />
          </g>
        ))}

        {/* Nodes */}
        {tasks.map((task) => {
          const pos = layout.positions.get(task.id);
          if (!pos) return null;

          return (
            <g
              key={task.id}
              transform={`translate(${pos.x}, ${pos.y})`}
              style={{ cursor: onTaskClick ? "pointer" : "default" }}
              onClick={() => onTaskClick?.(task.id)}
            >
              {/* Node background */}
              <rect
                width="180"
                height="80"
                rx="8"
                fill="#1a202c"
                stroke={getStatusColor(task.status)}
                strokeWidth="2"
                opacity="0.9"
              />

              {/* Priority indicator (left border) */}
              <rect
                x="0"
                y="0"
                width="4"
                height="80"
                rx="2"
                fill={getPriorityColor(task.priority)}
              />

              {/* Status icon */}
              <text
                x="20"
                y="20"
                fontSize="16"
                fill="#e2e8f0"
              >
                {getStatusLabel(task.status)}
              </text>

              {/* Title */}
              <text
                x="20"
                y="40"
                fontSize="13"
                fontWeight="600"
                fill="#fff"
              >
                {task.title.length > 18 ? task.title.substring(0, 18) + "..." : task.title}
              </text>

              {/* Metadata */}
              <text
                x="20"
                y="60"
                fontSize="11"
                fill="#a0aec0"
              >
                {task.priority && `${task.priority} `}
                {task.assignee && `• ${task.assignee}`}
              </text>

              {/* ID badge */}
              <rect
                x="140"
                y="5"
                width="35"
                height="16"
                rx="3"
                fill="#2d3748"
              />
              <text
                x="157"
                y="16"
                fontSize="9"
                fill="#718096"
                textAnchor="middle"
              >
                {task.id.slice(-4)}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div
        style={{
          position: "absolute",
          bottom: "10px",
          right: "10px",
          backgroundColor: "rgba(26, 32, 44, 0.9)",
          padding: "8px 12px",
          borderRadius: "6px",
          border: "1px solid #2d3748",
          fontSize: "11px",
        }}
      >
        <div style={{ color: "#a0aec0", marginBottom: "4px", fontWeight: 600 }}>Status:</div>
        <div style={{ display: "flex", gap: "12px", color: "#718096" }}>
          <span>⏳ Pending</span>
          <span>🔄 In Progress</span>
          <span>✅ Complete</span>
          <span>🚫 Blocked</span>
        </div>
      </div>
    </div>
  );
}

/**
 * TaskDAGNode component - wrapper for task DAG-type nodes on the canvas.
 *
 * Displays an embedded task dependency visualization within a canvas node.
 */
interface TaskDAGNodeProps {
  tasks: TaskNode[];
  dependencies: TaskDependency[];
  onTaskClick?: (taskId: string) => void;
}

export function TaskDAGNode({ tasks, dependencies, onTaskClick }: TaskDAGNodeProps) {
  return (
    <div
      style={{
        width: "100%",
        height: "300px",
        marginTop: "8px",
        borderRadius: "4px",
        overflow: "hidden",
      }}
    >
      <TaskDAG
        tasks={tasks}
        dependencies={dependencies}
        onTaskClick={onTaskClick}
      />
    </div>
  );
}
