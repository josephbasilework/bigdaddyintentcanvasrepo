export type LayoutType = "tree" | "hierarchy" | "force" | "grid";
export type LayoutDirection = "down" | "right";

export type LayoutNode = {
  id: string;
};

export type LayoutEdge = {
  source: string;
  target: string;
};

export type LayoutPoint = {
  x: number;
  y: number;
};

export type LayoutSpacing = {
  x: number;
  y: number;
};

export type LayoutOrigin = LayoutPoint;

export type LayoutOptions = {
  layout: LayoutType;
  direction?: LayoutDirection;
  spacing?: Partial<LayoutSpacing>;
  origin?: LayoutOrigin;
};

const DEFAULT_SPACING: LayoutSpacing = { x: 280, y: 200 };
const MAX_FORCE_NODES = 200;

const uniqueSortedIds = (nodes: LayoutNode[]): string[] => {
  const ids = nodes.map((node) => node.id).filter(Boolean);
  return Array.from(new Set(ids)).sort();
};

const normalizeSpacing = (spacing?: Partial<LayoutSpacing>): LayoutSpacing => ({
  x: spacing?.x ?? DEFAULT_SPACING.x,
  y: spacing?.y ?? DEFAULT_SPACING.y,
});

const buildEdgePairs = (edges: LayoutEdge[], validIds: Set<string>): Array<[string, string]> =>
  edges
    .map((edge) => [edge.source, edge.target] as [string, string])
    .filter(([source, target]) => validIds.has(source) && validIds.has(target));

const positionsByDepth = (
  depth: Record<string, number>,
  spacing: LayoutSpacing
): Record<string, LayoutPoint> => {
  const levels: Record<number, string[]> = {};
  Object.entries(depth).forEach(([nodeId, level]) => {
    const bucket = levels[level] ?? [];
    bucket.push(nodeId);
    levels[level] = bucket;
  });

  const positions: Record<string, LayoutPoint> = {};
  Object.keys(levels)
    .map((level) => Number(level))
    .sort((a, b) => a - b)
    .forEach((level) => {
      const nodesAtLevel = levels[level].slice().sort();
      nodesAtLevel.forEach((nodeId, index) => {
        positions[nodeId] = {
          x: index * spacing.x,
          y: level * spacing.y,
        };
      });
    });
  return positions;
};

const layoutGrid = (nodeIds: string[], spacing: LayoutSpacing): Record<string, LayoutPoint> => {
  const count = nodeIds.length;
  let cols = Math.max(1, Math.floor(Math.sqrt(count)));
  if (cols * cols < count) {
    cols += 1;
  }

  const positions: Record<string, LayoutPoint> = {};
  nodeIds.forEach((nodeId, index) => {
    const row = Math.floor(index / cols);
    const col = index % cols;
    positions[nodeId] = {
      x: col * spacing.x,
      y: row * spacing.y,
    };
  });
  return positions;
};

const layoutTree = (
  nodeIds: string[],
  edges: LayoutEdge[],
  spacing: LayoutSpacing
): Record<string, LayoutPoint> => {
  if (edges.length === 0) {
    return layoutGrid(nodeIds, spacing);
  }

  const adjacency: Record<string, string[]> = {};
  const indegree: Record<string, number> = {};
  nodeIds.forEach((nodeId) => {
    adjacency[nodeId] = [];
    indegree[nodeId] = 0;
  });

  edges.forEach((edge) => {
    if (!(edge.source in adjacency) || !(edge.target in adjacency)) {
      return;
    }
    adjacency[edge.source].push(edge.target);
    indegree[edge.target] += 1;
  });

  const roots = nodeIds.filter((nodeId) => indegree[nodeId] === 0);
  if (roots.length === 0) {
    return layoutGrid(nodeIds, spacing);
  }

  const depth: Record<string, number> = {};
  roots.forEach((nodeId) => {
    depth[nodeId] = 0;
  });

  const queue = [...roots];
  for (let i = 0; i < queue.length; i += 1) {
    const nodeId = queue[i];
    adjacency[nodeId].forEach((child) => {
      const nextDepth = (depth[nodeId] ?? 0) + 1;
      if (depth[child] === undefined || nextDepth < depth[child]) {
        depth[child] = nextDepth;
      }
      queue.push(child);
    });
  }

  nodeIds.forEach((nodeId) => {
    if (depth[nodeId] === undefined) {
      depth[nodeId] = 0;
    }
  });

  return positionsByDepth(depth, spacing);
};

const layoutHierarchy = (
  nodeIds: string[],
  edges: LayoutEdge[],
  spacing: LayoutSpacing
): Record<string, LayoutPoint> => {
  if (edges.length === 0) {
    return layoutGrid(nodeIds, spacing);
  }

  const adjacency: Record<string, string[]> = {};
  const indegree: Record<string, number> = {};
  const incoming: Record<string, string[]> = {};
  nodeIds.forEach((nodeId) => {
    adjacency[nodeId] = [];
    indegree[nodeId] = 0;
    incoming[nodeId] = [];
  });

  edges.forEach((edge) => {
    if (!(edge.source in adjacency) || !(edge.target in adjacency)) {
      return;
    }
    adjacency[edge.source].push(edge.target);
    indegree[edge.target] += 1;
    incoming[edge.target].push(edge.source);
  });

  const queue = nodeIds.filter((nodeId) => indegree[nodeId] === 0).sort();
  const topo: string[] = [];

  while (queue.length > 0) {
    const nodeId = queue.shift();
    if (!nodeId) break;
    topo.push(nodeId);
    adjacency[nodeId].forEach((child) => {
      indegree[child] -= 1;
      if (indegree[child] === 0) {
        queue.push(child);
        queue.sort();
      }
    });
  }

  if (topo.length !== nodeIds.length) {
    return layoutGrid(nodeIds, spacing);
  }

  const depth: Record<string, number> = {};
  topo.forEach((nodeId) => {
    const parents = incoming[nodeId];
    if (parents.length === 0) {
      depth[nodeId] = 0;
      return;
    }
    depth[nodeId] = Math.max(...parents.map((parent) => (depth[parent] ?? 0) + 1));
  });

  return positionsByDepth(depth, spacing);
};

const layoutForce = (
  nodeIds: string[],
  edges: LayoutEdge[],
  spacing: LayoutSpacing
): Record<string, LayoutPoint> => {
  if (nodeIds.length === 1) {
    return { [nodeIds[0]]: { x: 0, y: 0 } };
  }
  if (nodeIds.length > MAX_FORCE_NODES) {
    return layoutGrid(nodeIds, spacing);
  }

  const count = nodeIds.length;
  const radius = Math.max(spacing.x, spacing.y) * Math.max(1, Math.sqrt(count));
  const positions: Record<string, LayoutPoint> = {};

  nodeIds.forEach((nodeId, index) => {
    const angle = (Math.PI * 2 * index) / count;
    positions[nodeId] = {
      x: radius * Math.cos(angle),
      y: radius * Math.sin(angle),
    };
  });

  const edgePairs = buildEdgePairs(edges, new Set(nodeIds));
  const k = Math.max(spacing.x, spacing.y);
  let temperature = k * 0.5;
  const iterations = 60;

  for (let step = 0; step < iterations; step += 1) {
    const disp: Record<string, LayoutPoint> = {};
    nodeIds.forEach((nodeId) => {
      disp[nodeId] = { x: 0, y: 0 };
    });

    for (let i = 0; i < count; i += 1) {
      for (let j = i + 1; j < count; j += 1) {
        const v = nodeIds[i];
        const u = nodeIds[j];
        const dx = positions[v].x - positions[u].x;
        const dy = positions[v].y - positions[u].y;
        const dist = Math.hypot(dx, dy) + 0.01;
        const force = (k * k) / dist;
        disp[v].x += (dx / dist) * force;
        disp[v].y += (dy / dist) * force;
        disp[u].x -= (dx / dist) * force;
        disp[u].y -= (dy / dist) * force;
      }
    }

    edgePairs.forEach(([source, target]) => {
      const dx = positions[source].x - positions[target].x;
      const dy = positions[source].y - positions[target].y;
      const dist = Math.hypot(dx, dy) + 0.01;
      const force = (dist * dist) / k;
      disp[source].x -= (dx / dist) * force;
      disp[source].y -= (dy / dist) * force;
      disp[target].x += (dx / dist) * force;
      disp[target].y += (dy / dist) * force;
    });

    nodeIds.forEach((nodeId) => {
      const dx = disp[nodeId].x;
      const dy = disp[nodeId].y;
      const dist = Math.hypot(dx, dy) || 1;
      const stepSize = Math.min(dist, temperature);
      positions[nodeId].x += (dx / dist) * stepSize;
      positions[nodeId].y += (dy / dist) * stepSize;
    });

    temperature *= 0.9;
  }

  return positions;
};

export const computeLayoutPositions = (
  nodes: LayoutNode[],
  edges: LayoutEdge[],
  options: LayoutOptions
): Record<string, LayoutPoint> => {
  const nodeIds = uniqueSortedIds(nodes);
  if (nodeIds.length === 0) return {};

  const spacing = normalizeSpacing(options.spacing);
  const layout = options.layout;
  let positions: Record<string, LayoutPoint>;

  switch (layout) {
    case "grid":
      positions = layoutGrid(nodeIds, spacing);
      break;
    case "force":
      positions = layoutForce(nodeIds, edges, spacing);
      break;
    case "hierarchy":
      positions = layoutHierarchy(nodeIds, edges, spacing);
      break;
    default:
      positions = layoutTree(nodeIds, edges, spacing);
      break;
  }

  if (options.direction === "right") {
    positions = Object.fromEntries(
      Object.entries(positions).map(([nodeId, pos]) => [nodeId, { x: pos.y, y: pos.x }])
    );
  }

  const origin = options.origin;
  if (origin) {
    const minX = Math.min(...Object.values(positions).map((pos) => pos.x));
    const minY = Math.min(...Object.values(positions).map((pos) => pos.y));
    const shiftX = origin.x - minX;
    const shiftY = origin.y - minY;
    positions = Object.fromEntries(
      Object.entries(positions).map(([nodeId, pos]) => [
        nodeId,
        { x: pos.x + shiftX, y: pos.y + shiftY },
      ])
    );
  }

  return positions;
};
