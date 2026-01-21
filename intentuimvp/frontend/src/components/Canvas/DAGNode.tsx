"use client";

import { useMemo, useState, useEffect, useRef, useCallback } from "react";
import type { DAGData, DAGTask } from "../../state/canvasStore";

interface DAGNodeProps {
  dag: DAGData;
  onTaskClick?: (taskId: string) => void;
  onTaskStatusChange?: (taskId: string, nextStatus: DAGTask["status"]) => void;
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
const EMPTY_DEPENDENCIES: NonNullable<DAGData["dependencies"]> = [];

export function DAGNode({ dag, onTaskClick, onTaskStatusChange }: DAGNodeProps) {
  const tasks = dag.tasks;
  const dependencies = dag.dependencies ?? EMPTY_DEPENDENCIES;

  const STATUS_CYCLE: DAGTask["status"][] = [
    "pending",
    "in_progress",
    "completed",
    "blocked",
  ];

  const [expandedPhases, setExpandedPhases] = useState<Set<string>>(new Set());
  const prevRootIdsRef = useRef<string[]>([]);

  const dagIndex = useMemo(() => {
    const tasksById = new Map(tasks.map((task) => [task.id, task]));
    const adjacency = new Map<string, string[]>();
    const inDegree = new Map<string, number>();

    tasks.forEach((task) => {
      adjacency.set(task.id, []);
      inDegree.set(task.id, 0);
    });

    dependencies.forEach((dep) => {
      if (!adjacency.has(dep.dependsOnTaskId)) {
        adjacency.set(dep.dependsOnTaskId, []);
      }
      adjacency.get(dep.dependsOnTaskId)!.push(dep.taskId);
      inDegree.set(dep.taskId, (inDegree.get(dep.taskId) || 0) + 1);
    });

    const rootIds = tasks
      .filter((task) => (inDegree.get(task.id) ?? 0) === 0)
      .map((task) => task.id);

    const resolvedRoots = rootIds.length > 0 ? rootIds : tasks.map((task) => task.id);

    const descendantsByRoot = new Map<string, Set<string>>();
    const taskToRoots = new Map<string, Set<string>>();

    resolvedRoots.forEach((rootId) => {
      const visited = new Set<string>();
      const queue = [rootId];
      visited.add(rootId);

      while (queue.length > 0) {
        const current = queue.shift()!;
        const neighbors = adjacency.get(current) ?? [];
        for (const next of neighbors) {
          if (visited.has(next)) continue;
          visited.add(next);
          queue.push(next);
        }
      }

      descendantsByRoot.set(rootId, visited);
      for (const taskId of visited) {
        const rootSet = taskToRoots.get(taskId) ?? new Set<string>();
        rootSet.add(rootId);
        taskToRoots.set(taskId, rootSet);
      }
    });

    return {
      tasksById,
      adjacency,
      inDegree,
      rootIds: resolvedRoots,
      descendantsByRoot,
      taskToRoots,
    };
  }, [tasks, dependencies]);

  useEffect(() => {
    setExpandedPhases((prev) => {
      if (prev.size === 0) {
        return new Set(dagIndex.rootIds);
      }
      const prevRoots = new Set(prevRootIdsRef.current);
      const next = new Set<string>();
      dagIndex.rootIds.forEach((rootId) => {
        if (prev.has(rootId)) {
          next.add(rootId);
          return;
        }
        if (!prevRoots.has(rootId)) {
          next.add(rootId);
        }
      });
      return next;
    });
    prevRootIdsRef.current = dagIndex.rootIds;
  }, [dagIndex.rootIds]);

  const togglePhase = useCallback((rootId: string) => {
    setExpandedPhases((prev) => {
      const next = new Set(prev);
      if (next.has(rootId)) {
        next.delete(rootId);
      } else {
        next.add(rootId);
      }
      return next;
    });
  }, []);

  const expandAll = useCallback(() => {
    setExpandedPhases(new Set(dagIndex.rootIds));
  }, [dagIndex.rootIds]);

  const collapseAll = useCallback(() => {
    setExpandedPhases(new Set());
  }, []);

  const visibleTaskIds = useMemo(() => {
    const visible = new Set<string>();
    if (dagIndex.rootIds.length === 0) {
      tasks.forEach((task) => visible.add(task.id));
      return visible;
    }

    const rootSet = new Set(dagIndex.rootIds);
    dagIndex.rootIds.forEach((rootId) => visible.add(rootId));

    tasks.forEach((task) => {
      if (rootSet.has(task.id)) return;
      const rootIds = dagIndex.taskToRoots.get(task.id);
      if (!rootIds || rootIds.size === 0) {
        visible.add(task.id);
        return;
      }
      for (const rootId of rootIds) {
        if (expandedPhases.has(rootId)) {
          visible.add(task.id);
          break;
        }
      }
    });

    return visible;
  }, [dagIndex.rootIds, dagIndex.taskToRoots, expandedPhases, tasks]);

  const visibleTasks = useMemo(
    () => tasks.filter((task) => visibleTaskIds.has(task.id)),
    [tasks, visibleTaskIds]
  );
  const visibleDependencies = useMemo(
    () =>
      dependencies.filter(
        (dep) => visibleTaskIds.has(dep.taskId) && visibleTaskIds.has(dep.dependsOnTaskId)
      ),
    [dependencies, visibleTaskIds]
  );

  const readyTaskIds = useMemo(() => {
    const ready = new Set<string>();
    const blockersByTask = new Map<string, string[]>();

    dependencies.forEach((dep) => {
      if (!blockersByTask.has(dep.taskId)) {
        blockersByTask.set(dep.taskId, []);
      }
      blockersByTask.get(dep.taskId)!.push(dep.dependsOnTaskId);
    });

    tasks.forEach((task) => {
      if (task.status !== "pending") return;
      const blockers = blockersByTask.get(task.id) ?? [];
      if (blockers.length === 0) {
        ready.add(task.id);
        return;
      }
      const allComplete = blockers.every((id) => {
        const blocker = dagIndex.tasksById.get(id);
        return blocker?.status === "completed";
      });
      if (allComplete) {
        ready.add(task.id);
      }
    });

    return ready;
  }, [dependencies, dagIndex.tasksById, tasks]);

  const layout = useMemo(() => {
    const depMap = new Map<string, string[]>();

    visibleTasks.forEach((task) => {
      const blockers = visibleDependencies
        .filter((d) => d.taskId === task.id)
        .map((d) => d.dependsOnTaskId);
      depMap.set(task.id, blockers);
    });

    const levels = new Map<string, number>();
    const inDegree = new Map<string, number>();

    visibleTasks.forEach((task) => {
      inDegree.set(task.id, 0);
    });
    visibleDependencies.forEach((dep) => {
      inDegree.set(dep.taskId, (inDegree.get(dep.taskId) || 0) + 1);
    });

    const queue: string[] = [];
    visibleTasks.forEach((task) => {
      if (inDegree.get(task.id) === 0) {
        queue.push(task.id);
        levels.set(task.id, 0);
      }
    });

    while (queue.length > 0) {
      const taskId = queue.shift()!;
      const currentLevel = levels.get(taskId)!;

      visibleDependencies
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
    visibleTasks.forEach((task) => {
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

    const connections = visibleDependencies
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
  }, [visibleTasks, visibleDependencies]);

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

  const getStatusText = (status: DAGTask["status"]) => status.replace("_", " ");

  const getNextStatus = (status: DAGTask["status"]) => {
    const index = STATUS_CYCLE.indexOf(status);
    const nextIndex = index >= 0 ? (index + 1) % STATUS_CYCLE.length : 0;
    return STATUS_CYCLE[nextIndex];
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

  const handleStatusToggle = (
    e: React.MouseEvent<SVGGElement> | React.KeyboardEvent<SVGGElement>,
    task: DAGTask
  ) => {
    if (!onTaskStatusChange) return;
    e.stopPropagation();
    if ("type" in e && e.type === "keydown") {
      if ("key" in e && e.key !== "Enter" && e.key !== " ") {
        return;
      }
    }
    const nextStatus = getNextStatus(task.status);
    onTaskStatusChange(task.id, nextStatus);
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
      <div
        style={{
          padding: "10px 12px 0",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: "12px", color: "#94a3b8", fontWeight: 600 }}>
            Phases
          </div>
          <div style={{ display: "flex", gap: "6px" }}>
            <button
              type="button"
              onClick={expandAll}
              style={{
                border: "1px solid rgba(148, 163, 184, 0.4)",
                backgroundColor: "rgba(15, 23, 42, 0.6)",
                color: "#e2e8f0",
                borderRadius: "999px",
                padding: "2px 8px",
                fontSize: "10px",
                cursor: "pointer",
              }}
            >
              Expand all
            </button>
            <button
              type="button"
              onClick={collapseAll}
              style={{
                border: "1px solid rgba(148, 163, 184, 0.4)",
                backgroundColor: "rgba(15, 23, 42, 0.6)",
                color: "#e2e8f0",
                borderRadius: "999px",
                padding: "2px 8px",
                fontSize: "10px",
                cursor: "pointer",
              }}
            >
              Collapse all
            </button>
          </div>
        </div>
        <div style={{ display: "grid", gap: "6px" }}>
          {dagIndex.rootIds.map((rootId) => {
            const phaseTasks = dagIndex.descendantsByRoot.get(rootId) ?? new Set([rootId]);
            const phaseTaskList = Array.from(phaseTasks)
              .map((taskId) => dagIndex.tasksById.get(taskId))
              .filter(Boolean) as DAGTask[];
            const total = phaseTaskList.length;
            const pendingCount = phaseTaskList.filter((task) => task.status === "pending").length;
            const inProgressCount = phaseTaskList.filter((task) => task.status === "in_progress").length;
            const completedCount = phaseTaskList.filter((task) => task.status === "completed").length;
            const blockedCount = phaseTaskList.filter((task) => task.status === "blocked").length;
            const rootTask = dagIndex.tasksById.get(rootId);
            const title = rootTask?.title ?? "Phase";
            const isExpanded = expandedPhases.has(rootId);

            return (
              <button
                key={rootId}
                type="button"
                onClick={() => togglePhase(rootId)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  border: "1px solid rgba(148, 163, 184, 0.2)",
                  backgroundColor: "rgba(15, 23, 42, 0.4)",
                  borderRadius: "8px",
                  padding: "6px 10px",
                  color: "#e2e8f0",
                  cursor: "pointer",
                }}
                aria-expanded={isExpanded}
                aria-label={`${isExpanded ? "Collapse" : "Expand"} phase ${title}`}
              >
                <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px" }}>
                  <span style={{ color: "#94a3b8", fontSize: "12px" }}>
                    {isExpanded ? "▼" : "▶"}
                  </span>
                  <span>{title}</span>
                </span>
                <span style={{ fontSize: "10px", color: "#94a3b8" }}>
                  {total} · {pendingCount}/{inProgressCount}/{completedCount}/{blockedCount}
                </span>
              </button>
            );
          })}
        </div>
      </div>
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
        {visibleTasks.map((task) => {
          const pos = layout.positions.get(task.id);
          if (!pos) return null;
          const calendarStatus =
            task.calendarEventId || task.calendarEventUrl
              ? "linked"
              : task.calendarSuggestion
              ? "suggested"
              : null;
          const calendarLabel = calendarStatus
            ? calendarStatus === "linked"
              ? "Calendar linked"
              : "Calendar suggested"
            : null;
          const calendarBadgeColor = calendarStatus === "linked" ? "#48bb78" : "#63b3ed";
          const calendarBadgeBackground =
            calendarStatus === "linked"
              ? "rgba(72, 187, 120, 0.2)"
              : "rgba(99, 179, 237, 0.2)";
          const isReady = readyTaskIds.has(task.id);
          const nextStatus = getNextStatus(task.status);
          const readyBadgeX = task.priority ? 92 : 120;

          return (
            <g
              key={task.id}
              transform={`translate(${pos.x}, ${pos.y})`}
              style={{ cursor: onTaskClick ? "pointer" : "default" }}
              onClick={() => onTaskClick?.(task.id)}
              onKeyDown={(e) => handleTaskKeyDown(e, task.id)}
              tabIndex={onTaskClick ? 0 : -1}
              role={onTaskClick ? "button" : "group"}
              aria-label={`Task: ${task.title}, Status: ${task.status}${
                task.priority ? `, Priority: ${task.priority}` : ""
              }${isReady ? ", Ready" : ""}${calendarLabel ? `, ${calendarLabel}` : ""}`}
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

              {onTaskStatusChange && (
                <g
                  transform="translate(132, 24)"
                  role="button"
                  tabIndex={0}
                  onClick={(event) => handleStatusToggle(event, task)}
                  onKeyDown={(event) => handleStatusToggle(event, task)}
                  aria-label={`Advance status for ${task.title} to ${getStatusText(nextStatus)}`}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width="18"
                    height="18"
                    rx="4"
                    fill="rgba(148, 163, 184, 0.15)"
                    stroke="rgba(148, 163, 184, 0.4)"
                  />
                  <text
                    x="9"
                    y="12"
                    fontSize="10"
                    fill="#cbd5f5"
                    textAnchor="middle"
                  >
                    &gt;
                  </text>
                </g>
              )}

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

              {calendarStatus && (
                <g>
                  <rect
                    x="110"
                    y="52"
                    width="38"
                    height="14"
                    rx="3"
                    fill={calendarBadgeBackground}
                  />
                  <text
                    x="129"
                    y="62"
                    fontSize="8"
                    fill={calendarBadgeColor}
                    textAnchor="middle"
                  >
                    CAL
                  </text>
                </g>
              )}

              {isReady && (
                <g>
                  <rect
                    x={readyBadgeX}
                    y="5"
                    width="34"
                    height="14"
                    rx="3"
                    fill="rgba(251, 191, 36, 0.2)"
                  />
                  <text
                    x={readyBadgeX + 17}
                    y="15"
                    fontSize="8"
                    fill="#facc15"
                    textAnchor="middle"
                  >
                    READY
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
