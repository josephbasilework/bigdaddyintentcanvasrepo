export const BUILTIN_NODE_TYPES = [
  "text",
  "document",
  "audio",
  "graph",
  "plan",
  "dag",
  "dashboard",
  "job",
  "container",
] as const;

export type BuiltinNodeType = (typeof BUILTIN_NODE_TYPES)[number];

export type CanvasNodeType = BuiltinNodeType | (string & {});

export const DEFAULT_NODE_TYPE: BuiltinNodeType = "text";
