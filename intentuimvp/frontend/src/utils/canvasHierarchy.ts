import type { CanvasNodeType } from "../nodeTypes/types";
import { getNodeDimensions, type NodeDimensions } from "./nodeDimensions";

type CanvasNodeLike = {
  id: string;
  type: string;
  x: number;
  y: number;
  metadata?: Record<string, unknown>;
};

export type ContainerOffset = {
  x: number;
  y: number;
};

export type ContainerSize = {
  width: number;
  height: number;
};

export type ContainerMetadata = {
  parentId?: string;
  offset?: ContainerOffset;
  collapsed?: boolean;
  padding?: number;
  size?: ContainerSize;
};

export type ContainerMetadataUpdates = {
  parentId?: string | null;
  offset?: ContainerOffset | null;
  collapsed?: boolean | null;
  padding?: number | null;
  size?: ContainerSize | null;
};

export type HierarchyIndex = {
  childrenById: Map<string, string[]>;
  parentById: Map<string, string>;
  collapsedById: Set<string>;
};

export type NodeBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export const DEFAULT_CONTAINER_PADDING = 24;
export const DEFAULT_CONTAINER_HEADER_HEIGHT = 36;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const normalizeNumber = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const normalizeOffset = (value: unknown): ContainerOffset | undefined => {
  if (!isRecord(value)) return undefined;
  const x = normalizeNumber(value.x);
  const y = normalizeNumber(value.y);
  if (x === null || y === null) return undefined;
  return { x, y };
};

const normalizeSize = (value: unknown): ContainerSize | undefined => {
  if (!isRecord(value)) return undefined;
  const width = normalizeNumber(value.width);
  const height = normalizeNumber(value.height);
  if (width === null || height === null) return undefined;
  return { width, height };
};

export const getContainerMetadata = (
  metadata?: Record<string, unknown>
): ContainerMetadata => {
  if (!isRecord(metadata)) return {};
  const containerValue = metadata.container;
  if (!isRecord(containerValue)) return {};

  const parentIdValue = containerValue.parentId ?? containerValue.parent_id;
  const parentId = typeof parentIdValue === "string" && parentIdValue.trim().length > 0
    ? parentIdValue
    : undefined;

  const offset = normalizeOffset(containerValue.offset ?? containerValue.position);
  const size = normalizeSize(containerValue.size);
  const padding = normalizeNumber(containerValue.padding);
  const collapsed =
    typeof containerValue.collapsed === "boolean" ? containerValue.collapsed : undefined;

  return {
    ...(parentId ? { parentId } : {}),
    ...(offset ? { offset } : {}),
    ...(size ? { size } : {}),
    ...(padding !== null ? { padding } : {}),
    ...(collapsed !== undefined ? { collapsed } : {}),
  };
};

export const updateContainerMetadata = (
  metadata: Record<string, unknown> | undefined,
  updates: ContainerMetadataUpdates
): Record<string, unknown> => {
  const current = getContainerMetadata(metadata);
  const next: ContainerMetadata = { ...current };

  if ("parentId" in updates) {
    if (updates.parentId) {
      next.parentId = updates.parentId;
    } else {
      delete next.parentId;
    }
  }
  if ("offset" in updates) {
    if (updates.offset) {
      next.offset = updates.offset;
    } else {
      delete next.offset;
    }
  }
  if ("collapsed" in updates) {
    if (updates.collapsed === null) {
      delete next.collapsed;
    } else {
      next.collapsed = updates.collapsed ?? false;
    }
  }
  if ("padding" in updates) {
    if (updates.padding === null) {
      delete next.padding;
    } else if (updates.padding !== undefined) {
      next.padding = updates.padding;
    }
  }
  if ("size" in updates) {
    if (updates.size === null) {
      delete next.size;
    } else if (updates.size !== undefined) {
      next.size = updates.size;
    }
  }

  const nextMetadata = { ...(metadata ?? {}) } as Record<string, unknown>;
  if (Object.keys(next).length > 0) {
    nextMetadata.container = next;
  } else {
    delete nextMetadata.container;
  }
  return nextMetadata;
};

export const isContainerNode = (node: Pick<CanvasNodeLike, "type">): boolean =>
  node.type === "container";

export const getNodeParentId = (node: CanvasNodeLike): string | null =>
  getContainerMetadata(node.metadata).parentId ?? null;

export const getNodeOffset = (node: CanvasNodeLike): ContainerOffset | null =>
  getContainerMetadata(node.metadata).offset ?? null;

export const getContainerPadding = (node: CanvasNodeLike): number =>
  getContainerMetadata(node.metadata).padding ?? DEFAULT_CONTAINER_PADDING;

export const getContainerSize = (node: CanvasNodeLike): ContainerSize | null =>
  getContainerMetadata(node.metadata).size ?? null;

export const isContainerCollapsed = (node: CanvasNodeLike): boolean =>
  getContainerMetadata(node.metadata).collapsed ?? false;

export const buildHierarchyIndex = (nodes: CanvasNodeLike[]): HierarchyIndex => {
  const childrenById = new Map<string, string[]>();
  const parentById = new Map<string, string>();
  const collapsedById = new Set<string>();

  nodes.forEach((node) => {
    if (isContainerNode(node) && isContainerCollapsed(node)) {
      collapsedById.add(node.id);
    }
    const parentId = getNodeParentId(node);
    if (!parentId) return;
    parentById.set(node.id, parentId);
    const list = childrenById.get(parentId);
    if (list) {
      list.push(node.id);
    } else {
      childrenById.set(parentId, [node.id]);
    }
  });

  return { childrenById, parentById, collapsedById };
};

export const getDescendantIds = (
  parentId: string,
  index: Pick<HierarchyIndex, "childrenById">
): string[] => {
  const results: string[] = [];
  const stack = [...(index.childrenById.get(parentId) ?? [])];
  const visited = new Set<string>();

  while (stack.length > 0) {
    const current = stack.pop();
    if (!current || visited.has(current)) continue;
    visited.add(current);
    results.push(current);
    const children = index.childrenById.get(current);
    if (children) {
      children.forEach((childId) => stack.push(childId));
    }
  }

  return results;
};

export const buildHiddenNodeSet = (
  nodes: CanvasNodeLike[],
  index: HierarchyIndex = buildHierarchyIndex(nodes)
): Set<string> => {
  const hidden = new Set<string>();
  const { parentById, collapsedById } = index;

  nodes.forEach((node) => {
    let current = parentById.get(node.id);
    while (current) {
      if (collapsedById.has(current)) {
        hidden.add(node.id);
        break;
      }
      current = parentById.get(current);
    }
  });

  return hidden;
};

export const getNodeDepth = (
  nodeId: string,
  parentById: Map<string, string>
): number => {
  let depth = 0;
  let current = parentById.get(nodeId);
  const seen = new Set<string>();
  while (current) {
    if (seen.has(current)) break;
    seen.add(current);
    depth += 1;
    current = parentById.get(current);
  }
  return depth;
};

export const resolveNodeSize = (node: CanvasNodeLike): NodeDimensions => {
  if (isContainerNode(node)) {
    const size = getContainerSize(node);
    if (size) {
      return size;
    }
  }
  return getNodeDimensions({ type: node.type as CanvasNodeType });
};

const resolveNodeBounds = (node: CanvasNodeLike): NodeBounds => {
  const size = resolveNodeSize(node);
  return { x: node.x, y: node.y, width: size.width, height: size.height };
};

const isPointInsideBounds = (
  point: { x: number; y: number },
  bounds: NodeBounds
): boolean =>
  point.x >= bounds.x &&
  point.x <= bounds.x + bounds.width &&
  point.y >= bounds.y &&
  point.y <= bounds.y + bounds.height;

export const findContainerParentId = (
  node: CanvasNodeLike,
  nodes: CanvasNodeLike[]
): string | null => {
  const hierarchyIndex = buildHierarchyIndex(nodes);
  const nodeBounds = resolveNodeBounds(node);
  const center = {
    x: nodeBounds.x + nodeBounds.width / 2,
    y: nodeBounds.y + nodeBounds.height / 2,
  };
  const excludedIds = isContainerNode(node)
    ? new Set(getDescendantIds(node.id, hierarchyIndex))
    : new Set<string>();

  let bestId: string | null = null;
  let bestDepth = 0;
  let bestArea = 0;

  nodes.forEach((candidate) => {
    if (!isContainerNode(candidate)) return;
    if (candidate.id === node.id) return;
    if (excludedIds.has(candidate.id)) return;
    const bounds = resolveNodeBounds(candidate);
    if (!isPointInsideBounds(center, bounds)) return;
    const depth = getNodeDepth(candidate.id, hierarchyIndex.parentById);
    const area = bounds.width * bounds.height;
    if (
      bestId === null ||
      depth > bestDepth ||
      (depth === bestDepth && area < bestArea)
    ) {
      bestId = candidate.id;
      bestDepth = depth;
      bestArea = area;
    }
  });

  return bestId;
};

export const computeNodesBounds = (nodes: CanvasNodeLike[]): NodeBounds | null => {
  if (nodes.length === 0) return null;
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  nodes.forEach((node) => {
    const size = resolveNodeSize(node);
    minX = Math.min(minX, node.x);
    minY = Math.min(minY, node.y);
    maxX = Math.max(maxX, node.x + size.width);
    maxY = Math.max(maxY, node.y + size.height);
  });

  return {
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY,
  };
};

export const buildContainerFrame = (
  bounds: NodeBounds,
  options?: { padding?: number; headerHeight?: number; minSize?: NodeDimensions }
): NodeBounds => {
  const padding = options?.padding ?? DEFAULT_CONTAINER_PADDING;
  const headerHeight = options?.headerHeight ?? DEFAULT_CONTAINER_HEADER_HEIGHT;
  const minSize = options?.minSize;

  const x = bounds.x - padding;
  const y = bounds.y - padding - headerHeight;
  const width = bounds.width + padding * 2;
  const height = bounds.height + padding * 2 + headerHeight;
  const adjustedWidth = minSize ? Math.max(width, minSize.width) : width;
  const adjustedHeight = minSize ? Math.max(height, minSize.height) : height;

  return { x, y, width: adjustedWidth, height: adjustedHeight };
};
