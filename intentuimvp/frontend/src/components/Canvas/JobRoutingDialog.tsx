"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import type { CanvasNode } from "../../state/canvasStore";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type DestinationType =
  | "canvas_node"
  | "document_insert"
  | "user_storage"
  | "node_artifact"
  | "custom";

type InsertMode = "append" | "prepend" | "replace";

type ResultDestination = {
  type: DestinationType;
  node_id?: string | number;
  origin_node_id?: string | number;
  target_node_id?: string | number;
  document_node_id?: string | number;
  insert_mode?: InsertMode;
  label?: string;
};

type JobRoutingDialogProps = {
  isOpen: boolean;
  jobId: string;
  jobType: string;
  nodes: CanvasNode[];
  defaultTargetNodeId?: string | null;
  onClose: () => void;
  onSaved?: (destinations: ResultDestination[]) => void;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const normalizeDestinations = (metadata: string | null): ResultDestination[] => {
  if (!metadata) return [];
  try {
    const parsed = JSON.parse(metadata);
    if (!isRecord(parsed)) return [];
    const raw =
      parsed.result_destinations ??
      parsed.resultDestinations ??
      parsed.result_destination ??
      parsed.resultDestination;
    if (Array.isArray(raw)) {
      return raw.filter(isRecord) as ResultDestination[];
    }
    if (isRecord(raw)) {
      return [raw as ResultDestination];
    }
  } catch (error) {
    console.warn("Failed to parse job metadata:", error);
  }
  return [];
};

const coerceId = (value?: string | number | null): string => {
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
};

export function JobRoutingDialog({
  isOpen,
  jobId,
  jobType,
  nodes,
  defaultTargetNodeId,
  onClose,
  onSaved,
}: JobRoutingDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [routeCanvasNode, setRouteCanvasNode] = useState(false);
  const [routeUserStorage, setRouteUserStorage] = useState(false);
  const [routeDocumentInsert, setRouteDocumentInsert] = useState(false);
  const [documentNodeId, setDocumentNodeId] = useState("");
  const [insertMode, setInsertMode] = useState<InsertMode>("append");
  const [routeNodeArtifact, setRouteNodeArtifact] = useState(false);
  const [artifactNodeId, setArtifactNodeId] = useState("");
  const [routeCustom, setRouteCustom] = useState(false);
  const [customLabel, setCustomLabel] = useState("");

  const documentNodes = useMemo(
    () => nodes.filter((node) => node.type === "document"),
    [nodes]
  );

  useEffect(() => {
    if (!isOpen) return;
    setIsLoading(true);
    setError(null);

    const fallbackId = coerceId(defaultTargetNodeId);
    setDocumentNodeId(fallbackId);
    setArtifactNodeId(fallbackId);

    const loadRouting = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
        if (!response.ok) {
          throw new Error(`Failed to load job metadata (${response.status})`);
        }
        const data = await response.json();
        const destinations = normalizeDestinations(
          typeof data.metadata === "string" ? data.metadata : null
        );

        setRouteCanvasNode(false);
        setRouteUserStorage(false);
        setRouteDocumentInsert(false);
        setRouteNodeArtifact(false);
        setRouteCustom(false);
        setInsertMode("append");
        setCustomLabel("");

        destinations.forEach((destination) => {
          switch (destination.type) {
            case "canvas_node":
              setRouteCanvasNode(true);
              break;
            case "user_storage":
              setRouteUserStorage(true);
              break;
            case "document_insert":
              setRouteDocumentInsert(true);
              setDocumentNodeId(
                coerceId(
                  destination.node_id ??
                    destination.document_node_id ??
                    destination.target_node_id
                )
              );
              if (
                destination.insert_mode === "append" ||
                destination.insert_mode === "prepend" ||
                destination.insert_mode === "replace"
              ) {
                setInsertMode(destination.insert_mode);
              }
              break;
            case "node_artifact":
              setRouteNodeArtifact(true);
              setArtifactNodeId(
                coerceId(
                  destination.node_id ??
                    destination.origin_node_id ??
                    destination.target_node_id
                )
              );
              break;
            case "custom":
              setRouteCustom(true);
              if (destination.label) {
                setCustomLabel(destination.label);
              }
              break;
            default:
              break;
          }
        });
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load job routing";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    };

    void loadRouting();
  }, [defaultTargetNodeId, isOpen, jobId]);

  const handleSave = async () => {
    if (isSaving) return;
    setError(null);

    const destinations: ResultDestination[] = [];
    if (routeCanvasNode) {
      destinations.push({ type: "canvas_node" });
    }
    if (routeUserStorage) {
      destinations.push({ type: "user_storage" });
    }
    if (routeDocumentInsert) {
      if (!documentNodeId) {
        setError("Select a document node for insertion.");
        return;
      }
      destinations.push({
        type: "document_insert",
        node_id: documentNodeId,
        insert_mode: insertMode,
      });
    }
    if (routeNodeArtifact) {
      if (!artifactNodeId) {
        setError("Select a node to attach the artifact.");
        return;
      }
      destinations.push({ type: "node_artifact", node_id: artifactNodeId });
    }
    if (routeCustom) {
      destinations.push({
        type: "custom",
        label: customLabel.trim() || "custom",
      });
    }

    if (destinations.length === 0) {
      setError("Select at least one destination.");
      return;
    }

    setIsSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/routing`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ result_destinations: destinations }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `Routing update failed (${response.status})`);
      }
      onSaved?.(destinations);
      onClose();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to save routing settings";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10020,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "rgba(2, 6, 23, 0.72)",
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget && !isSaving) {
          onClose();
        }
      }}
    >
      <div
        style={{
          backgroundColor: "#0f172a",
          border: "1px solid rgba(148, 163, 184, 0.3)",
          borderRadius: "16px",
          padding: "24px",
          maxWidth: "520px",
          width: "calc(100% - 32px)",
          maxHeight: "90vh",
          overflow: "auto",
          boxShadow: "0 24px 48px rgba(0, 0, 0, 0.55)",
          color: "#e2e8f0",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <div>
          <div
            style={{
              fontSize: "12px",
              textTransform: "uppercase",
              letterSpacing: "0.2em",
              color: "#94a3b8",
            }}
          >
            Job routing
          </div>
          <h2
            id={titleId}
            style={{ margin: "6px 0 0 0", fontSize: "20px", fontWeight: 600 }}
          >
            Route results for {jobType.replace(/_/g, " ")}
          </h2>
          <p id={descriptionId} style={{ margin: "8px 0 0 0", color: "#cbd5f5" }}>
            Choose where outputs from this job should land.
          </p>
          <div
            style={{
              marginTop: "10px",
              fontSize: "12px",
              color: "#94a3b8",
            }}
          >
            Job ID: {jobId}
          </div>
        </div>

        {isLoading ? (
          <div style={{ color: "#94a3b8", fontSize: "14px" }}>
            Loading routing settings...
          </div>
        ) : (
          <>
            <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <input
                type="checkbox"
                checked={routeCanvasNode}
                onChange={(event) => setRouteCanvasNode(event.target.checked)}
              />
              Create a new canvas node for the result
            </label>
            <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <input
                type="checkbox"
                checked={routeUserStorage}
                onChange={(event) => setRouteUserStorage(event.target.checked)}
              />
              Persist in storage only (artifact)
            </label>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={routeDocumentInsert}
                  onChange={(event) => setRouteDocumentInsert(event.target.checked)}
                />
                Insert into an existing document
              </label>
              {routeDocumentInsert && (
                <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                  <select
                    value={documentNodeId}
                    onChange={(event) => setDocumentNodeId(event.target.value)}
                    style={{
                      flex: "1 1 200px",
                      padding: "8px 10px",
                      backgroundColor: "#1e293b",
                      border: "1px solid rgba(148, 163, 184, 0.4)",
                      borderRadius: "8px",
                      color: "#e2e8f0",
                    }}
                  >
                    <option value="">Select document node</option>
                    {documentNodes.map((node) => (
                      <option key={node.id} value={node.id}>
                        {node.title} ({node.id})
                      </option>
                    ))}
                  </select>
                  <select
                    value={insertMode}
                    onChange={(event) =>
                      setInsertMode(event.target.value as InsertMode)
                    }
                    style={{
                      flex: "0 1 140px",
                      padding: "8px 10px",
                      backgroundColor: "#1e293b",
                      border: "1px solid rgba(148, 163, 184, 0.4)",
                      borderRadius: "8px",
                      color: "#e2e8f0",
                    }}
                  >
                    <option value="append">Append</option>
                    <option value="prepend">Prepend</option>
                    <option value="replace">Replace</option>
                  </select>
                </div>
              )}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={routeNodeArtifact}
                  onChange={(event) => setRouteNodeArtifact(event.target.checked)}
                />
                Attach artifact to a node
              </label>
              {routeNodeArtifact && (
                <select
                  value={artifactNodeId}
                  onChange={(event) => setArtifactNodeId(event.target.value)}
                  style={{
                    padding: "8px 10px",
                    backgroundColor: "#1e293b",
                    border: "1px solid rgba(148, 163, 184, 0.4)",
                    borderRadius: "8px",
                    color: "#e2e8f0",
                  }}
                >
                  <option value="">Select node</option>
                  {nodes.map((node) => (
                    <option key={node.id} value={node.id}>
                      {node.title} ({node.type})
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={routeCustom}
                  onChange={(event) => setRouteCustom(event.target.checked)}
                />
                Custom destination tag
              </label>
              {routeCustom && (
                <input
                  type="text"
                  value={customLabel}
                  onChange={(event) => setCustomLabel(event.target.value)}
                  placeholder="E.g. notify ops pipeline"
                  style={{
                    padding: "8px 10px",
                    backgroundColor: "#1e293b",
                    border: "1px solid rgba(148, 163, 184, 0.4)",
                    borderRadius: "8px",
                    color: "#e2e8f0",
                  }}
                />
              )}
            </div>
          </>
        )}

        {error && (
          <div
            style={{
              padding: "10px 12px",
              borderRadius: "10px",
              backgroundColor: "rgba(127, 29, 29, 0.45)",
              border: "1px solid rgba(239, 68, 68, 0.4)",
              color: "#fecaca",
              fontSize: "13px",
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            style={{
              padding: "8px 14px",
              borderRadius: "999px",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              backgroundColor: "transparent",
              color: "#cbd5f5",
              cursor: isSaving ? "not-allowed" : "pointer",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving || isLoading}
            style={{
              padding: "8px 16px",
              borderRadius: "999px",
              border: "1px solid rgba(251, 191, 36, 0.6)",
              backgroundColor: "rgba(251, 191, 36, 0.15)",
              color: "#fef3c7",
              fontWeight: 600,
              cursor: isSaving || isLoading ? "not-allowed" : "pointer",
            }}
          >
            {isSaving ? "Saving..." : "Save routing"}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
