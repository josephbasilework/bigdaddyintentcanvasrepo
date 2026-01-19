import type { CanvasEdgeRelationType } from "../../state/canvasStore";

export const CUSTOM_EDGE_RELATION_VALUE = "__custom__";

const EDGE_RELATION_LABELS: Record<string, string> = {
  dependency: "Dependency",
  relates_to: "Relates to",
  parent_child: "Parent/child",
  depends_on: "Depends on",
  references: "References",
  supports: "Supports",
  conflicts: "Conflicts",
  derived_from: "Derived from",
  critiques: "Critiques",
};

export const EDGE_RELATION_OPTIONS: Array<{ value: CanvasEdgeRelationType; label: string }> = [
  { value: "dependency", label: EDGE_RELATION_LABELS.dependency },
  { value: "relates_to", label: EDGE_RELATION_LABELS.relates_to },
  { value: "parent_child", label: EDGE_RELATION_LABELS.parent_child },
  { value: "depends_on", label: EDGE_RELATION_LABELS.depends_on },
  { value: "references", label: EDGE_RELATION_LABELS.references },
  { value: "supports", label: EDGE_RELATION_LABELS.supports },
  { value: "conflicts", label: EDGE_RELATION_LABELS.conflicts },
  { value: "derived_from", label: EDGE_RELATION_LABELS.derived_from },
  { value: "critiques", label: EDGE_RELATION_LABELS.critiques },
];

const TITLECASE_EXCLUSIONS = new Set(["and", "or", "the", "to", "of", "in", "on"]);

const humanizeRelationType = (value: string): string => {
  const words = value
    .replace(/[_-]+/g, " ")
    .split(" ")
    .map((word) => word.trim())
    .filter(Boolean);

  if (words.length === 0) return value;

  return words
    .map((word, index) => {
      if (index > 0 && TITLECASE_EXCLUSIONS.has(word)) {
        return word;
      }
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
};

export const normalizeEdgeRelationType = (
  value: CanvasEdgeRelationType | string | null | undefined
): CanvasEdgeRelationType | null => {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed === CUSTOM_EDGE_RELATION_VALUE) return null;

  const normalized = trimmed
    .toLowerCase()
    .replace(/[\s-]+/g, "_")
    .replace(/[^a-z0-9_]/g, "")
    .replace(/^_+|_+$/g, "");

  return normalized.length > 0 ? (normalized as CanvasEdgeRelationType) : null;
};

export const getEdgeRelationLabel = (
  relationType?: CanvasEdgeRelationType | null
): string | null => {
  const normalized = normalizeEdgeRelationType(relationType ?? null);
  if (!normalized) return null;
  return EDGE_RELATION_LABELS[normalized] ?? humanizeRelationType(normalized);
};

export const buildEdgeRelationOptions = (
  relationTypes: Array<CanvasEdgeRelationType | string | null | undefined>
): Array<{ value: CanvasEdgeRelationType; label: string }> => {
  const options = new Map<string, string>();
  EDGE_RELATION_OPTIONS.forEach((option) => {
    options.set(option.value, option.label);
  });

  const customValues = relationTypes
    .map((relationType) => normalizeEdgeRelationType(relationType ?? null))
    .filter((relationType): relationType is CanvasEdgeRelationType => Boolean(relationType))
    .filter((relationType) => !options.has(relationType));

  customValues
    .sort((a, b) => {
      const labelA = getEdgeRelationLabel(a) ?? a;
      const labelB = getEdgeRelationLabel(b) ?? b;
      return labelA.localeCompare(labelB);
    })
    .forEach((relationType) => {
      options.set(relationType, getEdgeRelationLabel(relationType) ?? relationType);
    });

  return Array.from(options.entries()).map(([value, label]) => ({
    value: value as CanvasEdgeRelationType,
    label,
  }));
};
