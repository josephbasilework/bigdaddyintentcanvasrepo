import type { CanvasEdge, CanvasEdgeRelationType } from "../state/canvasStore";

export const DEFAULT_DEPENDENCY_RELATION: CanvasEdgeRelationType = "depends_on";
export const DEPENDENCY_CYCLE_MESSAGE =
  "Dependency cycle detected. Adjust dependencies to keep the DAG acyclic.";

const isDependencyEdge = (
  edge: CanvasEdge,
  defaultRelationType: CanvasEdgeRelationType = DEFAULT_DEPENDENCY_RELATION
): boolean => (edge.relationType ?? defaultRelationType) === "depends_on";

export const dependencyEdgesHaveCycle = (
  edges: CanvasEdge[],
  defaultRelationType: CanvasEdgeRelationType = DEFAULT_DEPENDENCY_RELATION
): boolean => {
  const adjacency = new Map<string, Set<string>>();
  const inDegree = new Map<string, number>();

  for (const edge of edges) {
    if (!isDependencyEdge(edge, defaultRelationType)) continue;

    const source = edge.sourceNodeId;
    const target = edge.targetNodeId;

    if (!adjacency.has(source)) {
      adjacency.set(source, new Set());
    }
    if (!inDegree.has(source)) {
      inDegree.set(source, 0);
    }
    if (!inDegree.has(target)) {
      inDegree.set(target, 0);
    }

    const neighbors = adjacency.get(source)!;
    if (!neighbors.has(target)) {
      neighbors.add(target);
      inDegree.set(target, (inDegree.get(target) ?? 0) + 1);
    }
  }

  if (inDegree.size === 0) {
    return false;
  }

  const queue: string[] = [];
  for (const [node, degree] of inDegree.entries()) {
    if (degree === 0) {
      queue.push(node);
    }
  }

  let visited = 0;
  while (queue.length > 0) {
    const node = queue.shift()!;
    visited += 1;
    const neighbors = adjacency.get(node);
    if (!neighbors) continue;
    for (const neighbor of neighbors) {
      const nextDegree = (inDegree.get(neighbor) ?? 0) - 1;
      inDegree.set(neighbor, nextDegree);
      if (nextDegree === 0) {
        queue.push(neighbor);
      }
    }
  }

  return visited !== inDegree.size;
};

export const wouldCreateDependencyCycle = (
  edges: CanvasEdge[],
  candidate: CanvasEdge,
  defaultRelationType: CanvasEdgeRelationType = DEFAULT_DEPENDENCY_RELATION
): boolean => {
  const nextEdges = edges.filter((edge) => edge.id !== candidate.id);
  nextEdges.push(candidate);
  return dependencyEdgesHaveCycle(nextEdges, defaultRelationType);
};
