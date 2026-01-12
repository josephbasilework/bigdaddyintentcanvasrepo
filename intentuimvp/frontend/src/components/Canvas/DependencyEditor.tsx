"use client";

import { useState, useCallback, useId, useMemo } from "react";
import {
  useCanvasStore,
  CanvasEdge,
  CanvasEdgeRelationType,
  CanvasNode,
} from "../../state/canvasStore";
import { EDGE_RELATION_OPTIONS, getEdgeRelationLabel } from "./edgeRelations";

interface DependencyEditorProps {
  nodeId: string;
  onClose: () => void;
}

type EdgeDirection = "outgoing" | "incoming";

interface EditableEdge {
  edge: CanvasEdge;
  direction: EdgeDirection;
  otherNode: CanvasNode;
}

/**
 * DependencyEditor component for editing node dependencies (edges).
 *
 * Provides UI for:
 * - Viewing all incoming and outgoing dependencies
 * - Adding new dependencies to other nodes
 * - Removing existing dependencies
 * - Editing edge properties (relation type, label)
 */
export function DependencyEditor({ nodeId, onClose }: DependencyEditorProps) {
  const { nodes, edges, addEdge, removeEdge, updateEdge } = useCanvasStore();
  const [selectedTargetId, setSelectedTargetId] = useState<string>("");
  const [newRelationType, setNewRelationType] = useState<CanvasEdgeRelationType>("depends_on");
  const [newLabel, setNewLabel] = useState("");

  const titleId = useId();
  const outgoingId = useId();
  const incomingId = useId();
  const addDependencyId = useId();

  const currentNode = useMemo(
    () => nodes.find((n) => n.id === nodeId),
    [nodes, nodeId]
  );

  // Get all edges connected to this node
  const { outgoingEdges, incomingEdges } = useMemo(() => {
    const outgoing: EditableEdge[] = [];
    const incoming: EditableEdge[] = [];

    edges.forEach((edge) => {
      if (edge.sourceNodeId === nodeId) {
        const targetNode = nodes.find((n) => n.id === edge.targetNodeId);
        if (targetNode) {
          outgoing.push({ edge, direction: "outgoing", otherNode: targetNode });
        }
      } else if (edge.targetNodeId === nodeId) {
        const sourceNode = nodes.find((n) => n.id === edge.sourceNodeId);
        if (sourceNode) {
          incoming.push({ edge, direction: "incoming", otherNode: sourceNode });
        }
      }
    });

    return { outgoingEdges: outgoing, incomingEdges: incoming };
  }, [edges, nodes, nodeId]);

  // Get available nodes that can be connected to (excluding self and already connected)
  const availableTargets = useMemo(() => {
    const connectedIds = new Set([
      nodeId,
      ...outgoingEdges.map((e) => e.otherNode.id),
    ]);
    return nodes.filter((n) => !connectedIds.has(n.id));
  }, [nodes, nodeId, outgoingEdges]);

  const handleAddDependency = useCallback(() => {
    if (!selectedTargetId) return;

    const label = newLabel.trim() || getEdgeRelationLabel(newRelationType) || undefined;
    addEdge({
      sourceNodeId: nodeId,
      targetNodeId: selectedTargetId,
      relationType: newRelationType,
      label,
    });

    setSelectedTargetId("");
    setNewLabel("");
    setNewRelationType("depends_on");
  }, [addEdge, nodeId, selectedTargetId, newRelationType, newLabel]);

  const handleRemoveEdge = useCallback(
    (edgeId: string) => {
      removeEdge(edgeId);
    },
    [removeEdge]
  );

  const handleUpdateEdgeRelation = useCallback(
    (edgeId: string, relationType: CanvasEdgeRelationType) => {
      const edge = edges.find((e) => e.id === edgeId);
      if (!edge) return;
      // Update the edge with new relation type and auto-update label if not custom
      const newLabelValue = getEdgeRelationLabel(relationType) || undefined;
      updateEdge(edgeId, { relationType, label: newLabelValue });
    },
    [edges, updateEdge]
  );

  const getRelationColor = (relationType?: CanvasEdgeRelationType) => {
    switch (relationType) {
      case "depends_on":
        return "#f97316"; // orange
      case "references":
        return "#3b82f6"; // blue
      case "supports":
        return "#22c55e"; // green
      case "conflicts":
        return "#ef4444"; // red
      case "derived_from":
        return "#a855f7"; // purple
      case "critiques":
        return "#eab308"; // yellow
      default:
        return "#94a3b8"; // gray
    }
  };

  if (!currentNode) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10001,
      }}
      onClick={onClose}
      role="presentation"
    >
      <div
        style={{
          backgroundColor: "#1a202c",
          border: "1px solid #2d3748",
          borderRadius: "8px",
          padding: "20px",
          minWidth: "500px",
          maxWidth: "650px",
          maxHeight: "80vh",
          overflow: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <h3
          style={{ marginTop: 0, marginBottom: "4px", color: "#fff" }}
          id={titleId}
        >
          Edit Dependencies
        </h3>
        <p style={{ marginTop: 0, marginBottom: "20px", color: "#94a3b8", fontSize: "13px" }}>
          Node: <strong style={{ color: "#e2e8f0" }}>{currentNode.title}</strong>
        </p>

        {/* Add new dependency */}
        <div style={{ marginBottom: "24px" }}>
          <label
            htmlFor={addDependencyId}
            style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px", fontWeight: 600 }}
          >
            Add Dependency
          </label>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            <select
              id={addDependencyId}
              value={selectedTargetId}
              onChange={(e) => setSelectedTargetId(e.target.value)}
              style={{
                flex: "1 1 180px",
                padding: "8px 12px",
                backgroundColor: "#2d3748",
                border: "1px solid #4a5568",
                borderRadius: "4px",
                color: "#fff",
                fontSize: "13px",
              }}
            >
              <option value="">Select a node...</option>
              {availableTargets.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.title}
                </option>
              ))}
            </select>
            <select
              value={newRelationType}
              onChange={(e) => setNewRelationType(e.target.value as CanvasEdgeRelationType)}
              style={{
                flex: "0 0 140px",
                padding: "8px 12px",
                backgroundColor: "#2d3748",
                border: "1px solid #4a5568",
                borderRadius: "4px",
                color: "#fff",
                fontSize: "13px",
              }}
            >
              {EDGE_RELATION_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleAddDependency}
              disabled={!selectedTargetId}
              style={{
                padding: "8px 16px",
                backgroundColor: selectedTargetId ? "#4299e1" : "#4a5568",
                border: "none",
                borderRadius: "4px",
                color: "#fff",
                cursor: selectedTargetId ? "pointer" : "not-allowed",
                fontSize: "13px",
                opacity: selectedTargetId ? 1 : 0.6,
              }}
            >
              Add
            </button>
          </div>
        </div>

        {/* Outgoing dependencies */}
        <div style={{ marginBottom: "24px" }}>
          <label
            id={outgoingId}
            style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px", fontWeight: 600 }}
          >
            Outgoing Dependencies ({outgoingEdges.length})
          </label>
          {outgoingEdges.length === 0 ? (
            <p style={{ color: "#718096", fontSize: "12px", fontStyle: "italic", margin: 0 }}>
              No outgoing dependencies
            </p>
          ) : (
            <ul
              aria-labelledby={outgoingId}
              style={{ margin: 0, padding: 0, listStyle: "none" }}
            >
              {outgoingEdges.map(({ edge, otherNode }) => (
                <li
                  key={edge.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "8px 10px",
                    marginBottom: "6px",
                    backgroundColor: "#2d3748",
                    borderRadius: "4px",
                    borderLeft: `3px solid ${getRelationColor(edge.relationType)}`,
                  }}
                >
                  <span style={{ color: "#e2e8f0", fontSize: "13px", flex: 1 }}>
                    {otherNode.title}
                  </span>
                  <select
                    value={edge.relationType || "depends_on"}
                    onChange={(e) =>
                      handleUpdateEdgeRelation(edge.id, e.target.value as CanvasEdgeRelationType)
                    }
                    style={{
                      padding: "4px 8px",
                      backgroundColor: "#1a202c",
                      border: "1px solid #4a5568",
                      borderRadius: "3px",
                      color: "#cbd5e0",
                      fontSize: "11px",
                    }}
                  >
                    {EDGE_RELATION_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => handleRemoveEdge(edge.id)}
                    aria-label={`Remove dependency to ${otherNode.title}`}
                    style={{
                      padding: "4px 8px",
                      backgroundColor: "#e53e3e",
                      border: "none",
                      borderRadius: "3px",
                      color: "#fff",
                      cursor: "pointer",
                      fontSize: "11px",
                    }}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Incoming dependencies */}
        <div style={{ marginBottom: "24px" }}>
          <label
            id={incomingId}
            style={{ display: "block", marginBottom: "8px", color: "#a0aec0", fontSize: "13px", fontWeight: 600 }}
          >
            Incoming Dependencies ({incomingEdges.length})
          </label>
          {incomingEdges.length === 0 ? (
            <p style={{ color: "#718096", fontSize: "12px", fontStyle: "italic", margin: 0 }}>
              No incoming dependencies
            </p>
          ) : (
            <ul
              aria-labelledby={incomingId}
              style={{ margin: 0, padding: 0, listStyle: "none" }}
            >
              {incomingEdges.map(({ edge, otherNode }) => (
                <li
                  key={edge.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "8px 10px",
                    marginBottom: "6px",
                    backgroundColor: "#2d3748",
                    borderRadius: "4px",
                    borderLeft: `3px solid ${getRelationColor(edge.relationType)}`,
                  }}
                >
                  <span style={{ color: "#e2e8f0", fontSize: "13px", flex: 1 }}>
                    {otherNode.title}
                  </span>
                  <span
                    style={{
                      padding: "4px 8px",
                      backgroundColor: `${getRelationColor(edge.relationType)}33`,
                      color: getRelationColor(edge.relationType),
                      fontSize: "10px",
                      borderRadius: "3px",
                      textTransform: "uppercase",
                      fontWeight: 600,
                    }}
                  >
                    {getEdgeRelationLabel(edge.relationType) || "linked"}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemoveEdge(edge.id)}
                    aria-label={`Remove dependency from ${otherNode.title}`}
                    style={{
                      padding: "4px 8px",
                      backgroundColor: "#e53e3e",
                      border: "none",
                      borderRadius: "3px",
                      color: "#fff",
                      cursor: "pointer",
                      fontSize: "11px",
                    }}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "8px 16px",
              backgroundColor: "#48bb78",
              border: "none",
              borderRadius: "4px",
              color: "#fff",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * DependencyDisplay component for displaying dependencies on a node.
 */
interface DependencyDisplayProps {
  nodeId: string;
  onEdit: () => void;
}

export function DependencyDisplay({ nodeId, onEdit }: DependencyDisplayProps) {
  const { edges } = useCanvasStore();

  const { outgoingCount, incomingCount, totalCount } = useMemo(() => {
    let outgoing = 0;
    let incoming = 0;

    edges.forEach((edge) => {
      if (edge.sourceNodeId === nodeId) {
        outgoing++;
      } else if (edge.targetNodeId === nodeId) {
        incoming++;
      }
    });

    return {
      outgoingCount: outgoing,
      incomingCount: incoming,
      totalCount: outgoing + incoming,
    };
  }, [edges, nodeId]);

  if (totalCount === 0) return null;

  return (
    <div
      style={{
        marginTop: "12px",
        paddingTop: "8px",
        borderTop: "1px solid rgba(255, 255, 255, 0.1)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
        <span
          style={{
            fontSize: "10px",
            color: "#94a3b8",
            textTransform: "uppercase",
            fontWeight: 600,
          }}
        >
          Dependencies
        </span>
        {outgoingCount > 0 && (
          <span
            style={{
              padding: "2px 6px",
              borderRadius: "3px",
              backgroundColor: "rgba(249, 115, 22, 0.2)",
              color: "#f97316",
              fontSize: "10px",
            }}
          >
            {outgoingCount} out
          </span>
        )}
        {incomingCount > 0 && (
          <span
            style={{
              padding: "2px 6px",
              borderRadius: "3px",
              backgroundColor: "rgba(59, 130, 246, 0.2)",
              color: "#3b82f6",
              fontSize: "10px",
            }}
          >
            {incomingCount} in
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={onEdit}
        style={{
          marginTop: "8px",
          padding: "4px 8px",
          backgroundColor: "transparent",
          border: "1px solid #4a5568",
          borderRadius: "3px",
          color: "#718096",
          cursor: "pointer",
          fontSize: "10px",
        }}
      >
        Edit Dependencies
      </button>
    </div>
  );
}
