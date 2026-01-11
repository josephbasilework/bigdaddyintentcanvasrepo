import type { CanvasEdgeRelationType } from "../../state/canvasStore";

export const EDGE_RELATION_OPTIONS: Array<{ value: CanvasEdgeRelationType; label: string }> = [
  { value: "depends_on", label: "Depends on" },
  { value: "references", label: "References" },
  { value: "supports", label: "Supports" },
  { value: "conflicts", label: "Conflicts" },
  { value: "derived_from", label: "Derived from" },
  { value: "critiques", label: "Critiques" },
];

export const EDGE_RELATION_LABELS: Record<CanvasEdgeRelationType, string> = {
  depends_on: "Depends on",
  references: "References",
  supports: "Supports",
  conflicts: "Conflicts",
  derived_from: "Derived from",
  critiques: "Critiques",
};

export const getEdgeRelationLabel = (
  relationType?: CanvasEdgeRelationType
): string | null => {
  if (!relationType) return null;
  return EDGE_RELATION_LABELS[relationType] ?? null;
};
