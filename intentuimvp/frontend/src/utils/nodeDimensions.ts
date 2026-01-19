import type { CanvasNodeType } from "../nodeTypes/types";

export type NodeDimensions = {
  width: number;
  height: number;
};

export const DEFAULT_NODE_DIMENSIONS: NodeDimensions = { width: 240, height: 140 };

export const NODE_DIMENSIONS_BY_TYPE: Record<string, NodeDimensions> = {
  text: { width: 240, height: 140 },
  document: { width: 260, height: 160 },
  audio: { width: 300, height: 180 },
  graph: { width: 280, height: 170 },
  plan: { width: 320, height: 200 },
  dag: { width: 360, height: 220 },
  dashboard: { width: 360, height: 220 },
  job: { width: 300, height: 180 },
  container: { width: 360, height: 240 },
};

export const getNodeDimensions = (node: { type: CanvasNodeType }): NodeDimensions =>
  NODE_DIMENSIONS_BY_TYPE[node.type] ?? DEFAULT_NODE_DIMENSIONS;
