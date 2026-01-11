"use client";

import { useMemo } from "react";
import { useCanvasStore, CanvasEdge, CanvasNode } from "../../state/canvasStore";
import { getEdgeRelationLabel } from "./edgeRelations";

interface EdgeProps {
  edge: CanvasEdge;
  sourceNode: CanvasNode;
  targetNode: CanvasNode;
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
export function Edge({ edge, sourceNode, targetNode }: EdgeProps) {
  const { type = "solid" } = edge;
  const resolvedLabel = edge.label ?? getEdgeRelationLabel(edge.relationType) ?? undefined;

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

  return (
    <g style={{ pointerEvents: "none" }}>
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
      {resolvedLabel && (
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
          style={{ paintOrder: "stroke" }}
        >
          {resolvedLabel}
        </text>
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
export function EdgesLayer() {
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
        pointerEvents: "none",
        zIndex: 0, // Below nodes
      }}
      aria-hidden="true"
    >
      {validEdges.map((edge) => {
        const sourceNode = nodeMap.get(edge.sourceNodeId)!;
        const targetNode = nodeMap.get(edge.targetNodeId)!;
        return <Edge key={edge.id} edge={edge} sourceNode={sourceNode} targetNode={targetNode} />;
      })}
    </svg>
  );
}
