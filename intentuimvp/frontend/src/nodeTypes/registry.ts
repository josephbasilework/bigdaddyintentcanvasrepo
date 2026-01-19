import type { ComponentType, ReactNode } from "react";
import type { NodeContext } from "../types/contextPreview";
import type { DAGTask } from "../state/canvasStore";
import { DEFAULT_NODE_TYPE, type CanvasNodeType } from "./types";

export type NodeTypeSchemaFieldType = "string" | "number" | "boolean" | "object" | "array";

export type NodeTypeSchemaField = {
  key: string;
  type: NodeTypeSchemaFieldType;
  required?: boolean;
  description?: string;
};

export type NodeTypeSchema = {
  fields: NodeTypeSchemaField[];
};

export type NodeTypeStyle = {
  backgroundColor: string;
  borderColor: string;
  selectedBorderColor: string;
  shadowColor: string;
  selectedShadowColor: string;
};

export type NodeLike = {
  id: string;
  type: CanvasNodeType;
  title: string;
  content?: string;
  metadata?: Record<string, unknown>;
  x?: number;
  y?: number;
  z?: number;
  createdByTurnId?: number | null;
};

export type NodeSerializePayload = Record<string, unknown>;

export type NodeTypeCreationProps<TNode extends NodeLike = NodeLike> = {
  onCreate: (node: Partial<TNode>) => void;
  onCancel: () => void;
};

export type NodeTypeCreationSpec<TNode extends NodeLike = NodeLike> = {
  label: string;
  description?: string;
  buildDefaults?: (input?: Record<string, unknown>) => Partial<TNode>;
  component?: (props: NodeTypeCreationProps<TNode>) => ReactNode;
};

export type NodeRendererProps = {
  node: NodeLike;
  isSelected?: boolean;
  documentPreview?: string;
  onSelect?: () => void;
  onRouteResults?: () => void;
  onRerunWithMoreCompute?: () => void;
  onDagTaskStatusChange?: (taskId: string, nextStatus: DAGTask["status"]) => void;
};

export type NodeEditorProps<TNode extends NodeLike = NodeLike> = {
  node: TNode;
  onSave: (updates: Partial<TNode>) => void;
  onCancel: () => void;
};

export type NodeTypeDefinition<TNode extends NodeLike = NodeLike> = {
  type: CanvasNodeType;
  label: string;
  description?: string;
  icon: string;
  schema: NodeTypeSchema;
  style?: NodeTypeStyle;
  creation?: NodeTypeCreationSpec<TNode>;
  render?: ComponentType<NodeRendererProps>;
  editor?: (props: NodeEditorProps<TNode>) => ReactNode;
  buildContext?: (node: TNode) => NodeContext;
  serialize?: (node: TNode, base: NodeSerializePayload) => NodeSerializePayload;
};

export type NodeTypeExtension<TNode extends NodeLike = NodeLike> = {
  id: string;
  definitions: NodeTypeDefinition<TNode>[] | NodeTypeDefinition<TNode>;
};

const NODE_TYPE_REGISTRY = new Map<CanvasNodeType, NodeTypeDefinition>();
const NODE_TYPE_EXTENSIONS = new Map<
  string,
  { extension: NodeTypeExtension; types: CanvasNodeType[] }
>();

const DEFAULT_STYLE: NodeTypeStyle = {
  backgroundColor: "#151515",
  borderColor: "#2f2f2f",
  selectedBorderColor: "#6b7280",
  shadowColor: "rgba(0, 0, 0, 0.3)",
  selectedShadowColor: "rgba(107, 114, 128, 0.35)",
};

const buildFallbackDefinition = (type: CanvasNodeType): NodeTypeDefinition => ({
  type,
  label: `Unknown (${String(type)})`,
  description: "Unregistered node type.",
  icon: "📦",
  schema: { fields: [] },
  style: DEFAULT_STYLE,
});

const stripUndefined = (payload: NodeSerializePayload): NodeSerializePayload =>
  Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined));

const buildBasePayload = (node: NodeLike): NodeSerializePayload =>
  stripUndefined({
    id: node.id,
    type: node.type,
    title: node.title,
    label: node.title,
    content: node.content,
    x: node.x,
    y: node.y,
    z: node.z,
    position:
      node.x !== undefined || node.y !== undefined || node.z !== undefined
        ? {
            x: node.x ?? 0,
            y: node.y ?? 0,
            z: node.z ?? 0,
          }
        : undefined,
    metadata: node.metadata,
    createdByTurnId: node.createdByTurnId ?? undefined,
  });

const defaultContextBuilder = (node: NodeLike): NodeContext => ({
  id: node.id,
  title: node.title,
  node_type: String(node.type),
  ...(node.content ? { content: node.content } : {}),
  ...(node.metadata ? { metadata: node.metadata } : {}),
});

export const normalizeNodeTypeId = (value: unknown): CanvasNodeType | null => {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  return trimmed.toLowerCase() as CanvasNodeType;
};

export const registerNodeType = <TNode extends NodeLike>(
  definition: NodeTypeDefinition<TNode>
): void => {
  const key = normalizeNodeTypeId(String(definition.type)) ?? definition.type;
  NODE_TYPE_REGISTRY.set(key, { ...definition, type: key } as NodeTypeDefinition);
};

export const registerNodeTypes = <TNode extends NodeLike>(
  definitions: NodeTypeDefinition<TNode>[]
): void => {
  definitions.forEach((definition) => registerNodeType(definition));
};

const normalizeExtensionId = (value: unknown): string | null => {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  return trimmed.toLowerCase();
};

export const registerNodeTypeExtension = (extension: NodeTypeExtension): void => {
  const key = normalizeExtensionId(extension.id) ?? extension.id;
  const definitions = Array.isArray(extension.definitions)
    ? extension.definitions
    : [extension.definitions];
  if (definitions.length === 0) {
    return;
  }

  const existing = NODE_TYPE_EXTENSIONS.get(key);
  if (existing) {
    existing.types.forEach((type) => unregisterNodeType(type));
  }

  registerNodeTypes(definitions);
  const types = definitions.map(
    (definition) => normalizeNodeTypeId(String(definition.type)) ?? definition.type
  );
  NODE_TYPE_EXTENSIONS.set(key, { extension: { ...extension, definitions }, types });
};

export const unregisterNodeTypeExtension = (id: string): void => {
  const key = normalizeExtensionId(id) ?? id;
  const entry = NODE_TYPE_EXTENSIONS.get(key);
  if (!entry) return;
  entry.types.forEach((type) => unregisterNodeType(type));
  NODE_TYPE_EXTENSIONS.delete(key);
};

export const listNodeTypeExtensions = (): NodeTypeExtension[] =>
  Array.from(NODE_TYPE_EXTENSIONS.values()).map((entry) => entry.extension);

export const unregisterNodeType = (type: CanvasNodeType): void => {
  const key = normalizeNodeTypeId(String(type)) ?? type;
  NODE_TYPE_REGISTRY.delete(key);
};

export const hasNodeType = (type: CanvasNodeType): boolean => {
  const key = normalizeNodeTypeId(String(type)) ?? type;
  return NODE_TYPE_REGISTRY.has(key);
};

export const getNodeTypeDefinition = (type: CanvasNodeType): NodeTypeDefinition => {
  const key = normalizeNodeTypeId(String(type)) ?? type;
  return NODE_TYPE_REGISTRY.get(key) ?? buildFallbackDefinition(key);
};

export const listNodeTypes = (): NodeTypeDefinition[] =>
  Array.from(NODE_TYPE_REGISTRY.values());

export const resolveNodeTypeId = (
  value: unknown,
  fallback: CanvasNodeType = DEFAULT_NODE_TYPE
): CanvasNodeType => {
  const normalized = normalizeNodeTypeId(value);
  if (normalized && hasNodeType(normalized)) {
    return normalized;
  }
  return fallback;
};

export const buildNodeContextFromNode = (node: NodeLike): NodeContext => {
  const definition = getNodeTypeDefinition(node.type);
  const builder = definition.buildContext ?? defaultContextBuilder;
  return builder(node);
};

export const serializeCanvasNode = (node: NodeLike): NodeSerializePayload => {
  const definition = getNodeTypeDefinition(node.type);
  const basePayload = buildBasePayload(node);
  const serializer = definition.serialize ?? ((_, base) => base);
  return serializer(node, basePayload);
};
