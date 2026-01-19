export type BuiltInEdgeRelationType =
  | "dependency"
  | "relates_to"
  | "parent_child";

export type LegacyEdgeRelationType =
  | "depends_on"
  | "references"
  | "supports"
  | "conflicts"
  | "derived_from"
  | "critiques";

export type CanvasEdgeRelationType =
  | BuiltInEdgeRelationType
  | LegacyEdgeRelationType
  | (string & {});
