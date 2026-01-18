"use client";

import { useMemo, useState, useCallback } from "react";
import { useCanvasStore, CanvasEdge, CanvasNode } from "../../state/canvasStore";
import { getEdgeRelationLabel } from "./edgeRelations";

interface EdgeProps {
  edge: CanvasEdge;
  sourceNode: CanvasNode;
  targetNode: CanvasNode;
  onAnnotate?: (edgeId: string) => void;
}

const DEFAULT_NODE_WIDTH = 200;
const DEFAULT_NODE_HEIGHT = 80;
const LABEL_OFFSET = 14;
const EDGE_STROKE = "#94a3b8";
const EDGE_LABEL_FILL = "#f8fafc";
const EDGE_LABEL_STROKE = "#0f172a";

/**
 * Edge component that renders a connection line between two nodes.
 *
 * Calculates the optimal connection points between nodes and renders
 * a styled SVG line with optional label.
 */
export function Edge({ edge, sourceNode, targetNode, onAnnotate }: EdgeProps) {
  const { type = "solid" } = edge;
  const resolvedLabel = edge.label ?? getEdgeRelationLabel(edge.relationType) ?? undefined;
  const defaultLabel = getEdgeRelationLabel(edge.relationType) ?? "";
  const updateEdge = useCanvasStore((state) => state.updateEdge);
  const [isEditingLabel, setIsEditingLabel] = useState(false);
  const [labelDraft, setLabelDraft] = useState(edge.label ?? resolvedLabel ?? "");
  const hasAnnotation = Boolean(
    edge.metadata &&
      typeof edge.metadata === "object" &&
      "annotation" in edge.metadata &&
      edge.metadata.annotation &&
      (edge.metadata.annotation.comment ||
        (Array.isArray(edge.metadata.annotation.tags) && edge.metadata.annotation.tags.length > 0) ||
        edge.metadata.annotation.status)
  );

  // Calculate connection points on nodes
  const { path, labelPosition } = useMemo(() => {
    const nodeWidth = DEFAULT_NODE_WIDTH;
    const nodeHeight = DEFAULT_NODE_HEIGHT;

    const sourceCenter = {
      x: sourceNode.x + nodeWidth / 2,
      y: sourceNode.y + nodeHeight / 2,
    };
    const targetCenter = {
      x: targetNode.x + nodeWidth / 2,
      y: targetNode.y + nodeHeight / 2,
    };

    const getAnchorPoint = (
      from: { x: number; y: number },
      to: { x: number; y: number },
      width: number,
      height: number
    ) => {
      const dx = to.x - from.x;
      const dy = to.y - from.y;
      if (dx === 0 && dy === 0) {
        return { x: from.x, y: from.y };
      }

      const halfWidth = width / 2;
      const halfHeight = height / 2;
      const scaleX = dx === 0 ? Number.POSITIVE_INFINITY : halfWidth / Math.abs(dx);
      const scaleY = dy === 0 ? Number.POSITIVE_INFINITY : halfHeight / Math.abs(dy);
      const scale = Math.min(scaleX, scaleY);
      return {
        x: from.x + dx * scale,
        y: from.y + dy * scale,
      };
    };

    const start = getAnchorPoint(sourceCenter, targetCenter, nodeWidth, nodeHeight);
    const end = getAnchorPoint(targetCenter, sourceCenter, nodeWidth, nodeHeight);

    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.hypot(dx, dy) || 1;
    const midX = start.x + dx / 2;
    const midY = start.y + dy / 2;
    const normalX = -dy / length;
    const normalY = dx / length;

    return {
      path: `M ${start.x} ${start.y} L ${end.x} ${end.y}`,
      labelPosition: {
        x: midX + normalX * LABEL_OFFSET,
        y: midY + normalY * LABEL_OFFSET,
      },
    };
  }, [sourceNode.x, sourceNode.y, targetNode.x, targetNode.y]);

  const strokeDashArray = type === "dashed" ? "5,5" : type === "dotted" ? "2,2" : undefined;

  const handleLabelEditStart = useCallback(
    (event: React.MouseEvent<SVGTextElement>) => {
      event.stopPropagation();
      setLabelDraft(edge.label ?? defaultLabel ?? "");
      setIsEditingLabel(true);
    },
    [defaultLabel, edge.label]
  );

  const handleLabelCommit = useCallback(() => {
    const trimmed = labelDraft.trim();
    const nextLabel = trimmed.length > 0 ? trimmed : undefined;
    const normalizedLabel =
      nextLabel && defaultLabel && nextLabel === defaultLabel ? undefined : nextLabel;

    if ((edge.label ?? undefined) !== normalizedLabel) {
      updateEdge(edge.id, { label: normalizedLabel });
    }
    setIsEditingLabel(false);
  }, [defaultLabel, edge.id, edge.label, labelDraft, updateEdge]);

  const handleLabelCancel = useCallback(() => {
    setLabelDraft(edge.label ?? defaultLabel ?? "");
    setIsEditingLabel(false);
  }, [defaultLabel, edge.label]);

  const handleLabelKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter") {
        event.preventDefault();
        handleLabelCommit();
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        handleLabelCancel();
      }
    },
    [handleLabelCancel, handleLabelCommit]
  );

  const handleAnnotateClick = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();
      event.preventDefault();
      if (onAnnotate) {
        onAnnotate(edge.id);
      }
    },
    [edge.id, onAnnotate]
  );

  const labelWidth = Math.min(240, Math.max(60, (resolvedLabel?.length ?? 8) * 7));
  const inputWidth = Math.min(
    260,
    Math.max(120, Math.max((isEditingLabel ? labelDraft : resolvedLabel ?? "").length, 8) * 8)
  );

  return (
    <g>
      {/* Edge line */}
      <path
        d={path}
        stroke={EDGE_STROKE}
        strokeWidth="2"
        fill="none"
        strokeDasharray={strokeDashArray}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.85"
        markerEnd={`url(#arrowhead-${edge.id})`}
        vectorEffect="non-scaling-stroke"
        pointerEvents="none"
      />

      {/* Arrow head */}
      <defs>
        <marker
          id={`arrowhead-${edge.id}`}
          markerWidth="10"
          markerHeight="7"
          refX="9"
          refY="3.5"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <polygon points="0 0, 10 3.5, 0 7" fill={EDGE_STROKE} opacity="0.8" />
        </marker>
      </defs>

      {/* Optional label */}
      {resolvedLabel && !isEditingLabel && (
        <text
          x={labelPosition.x}
          y={labelPosition.y}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="12"
          fontWeight="500"
          fill={EDGE_LABEL_FILL}
          stroke={EDGE_LABEL_STROKE}
          strokeWidth="4"
          style={{ paintOrder: "stroke", cursor: "text" }}
          onDoubleClick={handleLabelEditStart}
          role="button"
          aria-label="Edit edge label"
        >
          {resolvedLabel}
        </text>
      )}
      {isEditingLabel && (
        <foreignObject
          x={labelPosition.x - inputWidth / 2}
          y={labelPosition.y - 14}
          width={inputWidth}
          height={28}
        >
          <input
            type="text"
            value={labelDraft}
            onChange={(event) => setLabelDraft(event.target.value)}
            onBlur={handleLabelCommit}
            onKeyDown={handleLabelKeyDown}
            style={{
              width: "100%",
              height: "100%",
              borderRadius: "6px",
              border: "1px solid rgba(148, 163, 184, 0.8)",
              backgroundColor: "#0f172a",
              color: "#e2e8f0",
              fontSize: "12px",
              padding: "2px 8px",
              boxSizing: "border-box",
            }}
            autoFocus
          />
        </foreignObject>
      )}
      {!isEditingLabel && onAnnotate && (
        <foreignObject
          x={labelPosition.x + labelWidth / 2 + 6}
          y={labelPosition.y - 10}
          width={20}
          height={20}
        >
          <button
            type="button"
            onClick={handleAnnotateClick}
            aria-label="Annotate edge"
            style={{
              width: "20px",
              height: "20px",
              borderRadius: "999px",
              border: `1px solid ${hasAnnotation ? "#38bdf8" : "rgba(148, 163, 184, 0.6)"}`,
              backgroundColor: hasAnnotation ? "rgba(56, 189, 248, 0.25)" : "rgba(15, 23, 42, 0.8)",
              color: "#e2e8f0",
              cursor: "pointer",
              fontSize: "11px",
              lineHeight: "18px",
              textAlign: "center",
            }}
          >
            ✎
          </button>
        </foreignObject>
      )}
    </g>
  );
}

/**
 * EdgesLayer component that renders all edges on the canvas.
 *
 * Uses an SVG overlay to draw connections between nodes.
 * Edges are rendered below nodes (z-index wise) so nodes appear on top.
 */
export function EdgesLayer({ onAnnotate }: { onAnnotate?: (edgeId: string) => void }) {
  const { edges, nodes } = useCanvasStore();

  // Create a map of nodes for quick lookup
  const nodeMap = useMemo(() => {
    const map = new Map<string, CanvasNode>();
    nodes.forEach((node) => map.set(node.id, node));
    return map;
  }, [nodes]);

  // Filter edges to only those where both nodes exist
  const validEdges = useMemo(() => {
    return edges.filter(
      (edge) => nodeMap.has(edge.sourceNodeId) && nodeMap.has(edge.targetNodeId)
    );
  }, [edges, nodeMap]);

  if (validEdges.length === 0) {
    return null;
  }

  return (
    <svg
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        overflow: "visible",
        pointerEvents: "auto",
        zIndex: 0, // Below nodes
      }}
      data-edge-layer="true"
      aria-hidden="true"
    >
      {validEdges.map((edge) => {
        const sourceNode = nodeMap.get(edge.sourceNodeId)!;
        const targetNode = nodeMap.get(edge.targetNodeId)!;
        return (
          <Edge
            key={edge.id}
            edge={edge}
            sourceNode={sourceNode}
            targetNode={targetNode}
            onAnnotate={onAnnotate}
          />
        );
      })}
    </svg>
  );
}
