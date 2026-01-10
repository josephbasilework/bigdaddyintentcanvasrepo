"use client";

import { useMemo } from "react";
import { useCanvasStore, CanvasEdge, CanvasNode } from "../../state/canvasStore";

interface EdgeProps {
  edge: CanvasEdge;
  sourceNode: CanvasNode;
  targetNode: CanvasNode;
}

/**
 * Edge component that renders a connection line between two nodes.
 *
 * Calculates the optimal connection points between nodes and renders
 * a styled SVG line with optional label.
 */
export function Edge({ edge, sourceNode, targetNode }: EdgeProps) {
  const { type = "solid" } = edge;

  // Calculate connection points on nodes
  const { path, labelPosition } = useMemo(() => {
    // Estimate node dimensions (default to 200x80 if not calculated)
    const nodeWidth = 200;
    const nodeHeight = 80;

    // Calculate centers
    const sourceCenterX = sourceNode.x + nodeWidth / 2;
    const sourceCenterY = sourceNode.y + nodeHeight / 2;
    const targetCenterX = targetNode.x + nodeWidth / 2;
    const targetCenterY = targetNode.y + nodeHeight / 2;

    // Simple straight line for now
    // TODO: Implement curved bezier lines for better visuals
    const dx = targetCenterX - sourceCenterX;
    const dy = targetCenterY - sourceCenterY;

    // Calculate edge position (from center to center)
    // The actual SVG coordinates will be relative to the canvas
    return {
      path: `M ${sourceCenterX} ${sourceCenterY} L ${targetCenterX} ${targetCenterY}`,
      labelPosition: {
        x: sourceCenterX + dx / 2,
        y: sourceCenterY + dy / 2,
      },
    };
  }, [sourceNode, targetNode]);

  const strokeDashArray = type === "dashed" ? "5,5" : type === "dotted" ? "2,2" : undefined;

  return (
    <g style={{ pointerEvents: "none" }}>
      {/* Edge line */}
      <path
        d={path}
        stroke="#4a5568"
        strokeWidth="2"
        fill="none"
        strokeDasharray={strokeDashArray}
        opacity="0.8"
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
        >
          <polygon points="0 0, 10 3.5, 0 7" fill="#4a5568" opacity="0.8" />
        </marker>
      </defs>

      {/* Optional label */}
      {edge.label && (
        <text
          x={labelPosition.x}
          y={labelPosition.y}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="12"
          fill="#a0aec0"
          style={{
            backgroundColor: "#1a202c",
            padding: "2px 6px",
            borderRadius: "4px",
          }}
        >
          {edge.label}
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
        pointerEvents: "none",
        zIndex: 0, // Below nodes
      }}
    >
      {validEdges.map((edge) => {
        const sourceNode = nodeMap.get(edge.sourceNodeId)!;
        const targetNode = nodeMap.get(edge.targetNodeId)!;
        return <Edge key={edge.id} edge={edge} sourceNode={sourceNode} targetNode={targetNode} />;
      })}
    </svg>
  );
}
