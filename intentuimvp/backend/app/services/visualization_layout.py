"""Layout helpers for agent-created visualizations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import cos, hypot, sin, sqrt, tau
from typing import Literal

LayoutType = Literal["tree", "hierarchy", "force", "grid"]
LayoutDirection = Literal["down", "right"]


@dataclass(frozen=True)
class LayoutEdge:
    """Edge reference for layout computation."""

    source: str
    target: str


def compute_layout_positions(
    node_ids: Sequence[str],
    edges: Sequence[LayoutEdge],
    *,
    layout: LayoutType,
    spacing_x: float,
    spacing_y: float,
    direction: LayoutDirection,
    origin_x: float,
    origin_y: float,
) -> dict[str, tuple[float, float]]:
    """Compute 2D layout positions for node IDs."""
    if not node_ids:
        return {}

    unique_ids = list(dict.fromkeys(node_ids))
    if layout == "grid":
        positions = _layout_grid(unique_ids, spacing_x, spacing_y)
    elif layout == "force":
        positions = _layout_force(unique_ids, edges, spacing_x, spacing_y)
    elif layout == "hierarchy":
        positions = _layout_hierarchy(unique_ids, edges, spacing_x, spacing_y)
    else:
        positions = _layout_tree(unique_ids, edges, spacing_x, spacing_y)

    if direction == "right":
        positions = {node_id: (y, x) for node_id, (x, y) in positions.items()}

    min_x = min(pos[0] for pos in positions.values())
    min_y = min(pos[1] for pos in positions.values())
    shift_x = origin_x - min_x
    shift_y = origin_y - min_y

    return {
        node_id: (x + shift_x, y + shift_y)
        for node_id, (x, y) in positions.items()
    }


def _layout_grid(
    node_ids: Sequence[str], spacing_x: float, spacing_y: float
) -> dict[str, tuple[float, float]]:
    count = len(node_ids)
    cols = max(1, int(sqrt(count)))
    if cols * cols < count:
        cols += 1

    positions: dict[str, tuple[float, float]] = {}
    for idx, node_id in enumerate(node_ids):
        row = idx // cols
        col = idx % cols
        positions[node_id] = (col * spacing_x, row * spacing_y)
    return positions


def _layout_tree(
    node_ids: Sequence[str],
    edges: Sequence[LayoutEdge],
    spacing_x: float,
    spacing_y: float,
) -> dict[str, tuple[float, float]]:
    if not edges:
        return _layout_grid(node_ids, spacing_x, spacing_y)

    adjacency = {node_id: [] for node_id in node_ids}
    indegree = {node_id: 0 for node_id in node_ids}

    for edge in edges:
        if edge.source not in adjacency or edge.target not in adjacency:
            continue
        adjacency[edge.source].append(edge.target)
        indegree[edge.target] += 1

    roots = [node_id for node_id, deg in indegree.items() if deg == 0]
    if not roots:
        return _layout_grid(node_ids, spacing_x, spacing_y)

    depth: dict[str, int] = {node_id: 0 for node_id in roots}
    queue = list(roots)
    for node_id in queue:
        for child in adjacency.get(node_id, []):
            next_depth = depth[node_id] + 1
            if child not in depth or next_depth < depth[child]:
                depth[child] = next_depth
            queue.append(child)

    for node_id in node_ids:
        depth.setdefault(node_id, 0)

    return _positions_by_depth(depth, spacing_x, spacing_y)


def _layout_hierarchy(
    node_ids: Sequence[str],
    edges: Sequence[LayoutEdge],
    spacing_x: float,
    spacing_y: float,
) -> dict[str, tuple[float, float]]:
    if not edges:
        return _layout_grid(node_ids, spacing_x, spacing_y)

    adjacency = {node_id: [] for node_id in node_ids}
    indegree = {node_id: 0 for node_id in node_ids}
    incoming: dict[str, list[str]] = {node_id: [] for node_id in node_ids}

    for edge in edges:
        if edge.source not in adjacency or edge.target not in adjacency:
            continue
        adjacency[edge.source].append(edge.target)
        indegree[edge.target] += 1
        incoming[edge.target].append(edge.source)

    queue = [node_id for node_id in node_ids if indegree[node_id] == 0]
    queue.sort()
    topo: list[str] = []

    while queue:
        node_id = queue.pop(0)
        topo.append(node_id)
        for child in adjacency[node_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
                queue.sort()

    if len(topo) != len(node_ids):
        return _layout_grid(node_ids, spacing_x, spacing_y)

    depth: dict[str, int] = {node_id: 0 for node_id in topo}
    for node_id in topo:
        if incoming[node_id]:
            depth[node_id] = max(depth[parent] + 1 for parent in incoming[node_id])

    return _positions_by_depth(depth, spacing_x, spacing_y)


def _positions_by_depth(
    depth: dict[str, int],
    spacing_x: float,
    spacing_y: float,
) -> dict[str, tuple[float, float]]:
    levels: dict[int, list[str]] = {}
    for node_id, level in depth.items():
        levels.setdefault(level, []).append(node_id)

    positions: dict[str, tuple[float, float]] = {}
    for level in sorted(levels):
        nodes_at_level = sorted(levels[level])
        for idx, node_id in enumerate(nodes_at_level):
            positions[node_id] = (idx * spacing_x, level * spacing_y)
    return positions


def _layout_force(
    node_ids: Sequence[str],
    edges: Sequence[LayoutEdge],
    spacing_x: float,
    spacing_y: float,
) -> dict[str, tuple[float, float]]:
    if len(node_ids) == 1:
        return {node_ids[0]: (0.0, 0.0)}

    max_nodes = 200
    if len(node_ids) > max_nodes:
        return _layout_grid(node_ids, spacing_x, spacing_y)

    ids = list(node_ids)
    count = len(ids)
    radius = max(spacing_x, spacing_y) * max(1.0, sqrt(count))
    positions: dict[str, list[float]] = {}
    for idx, node_id in enumerate(ids):
        angle = (tau * idx) / count
        positions[node_id] = [radius * cos(angle), radius * sin(angle)]

    edge_pairs = [
        (edge.source, edge.target)
        for edge in edges
        if edge.source in positions and edge.target in positions
    ]
    k = max(spacing_x, spacing_y)
    temperature = k * 0.5
    iterations = 60

    for _ in range(iterations):
        disp: dict[str, list[float]] = {node_id: [0.0, 0.0] for node_id in ids}

        for i in range(count):
            for j in range(i + 1, count):
                v = ids[i]
                u = ids[j]
                dx = positions[v][0] - positions[u][0]
                dy = positions[v][1] - positions[u][1]
                dist = hypot(dx, dy) + 0.01
                force = (k * k) / dist
                disp[v][0] += (dx / dist) * force
                disp[v][1] += (dy / dist) * force
                disp[u][0] -= (dx / dist) * force
                disp[u][1] -= (dy / dist) * force

        for source, target in edge_pairs:
            dx = positions[source][0] - positions[target][0]
            dy = positions[source][1] - positions[target][1]
            dist = hypot(dx, dy) + 0.01
            force = (dist * dist) / k
            disp[source][0] -= (dx / dist) * force
            disp[source][1] -= (dy / dist) * force
            disp[target][0] += (dx / dist) * force
            disp[target][1] += (dy / dist) * force

        for node_id in ids:
            dx, dy = disp[node_id]
            dist = hypot(dx, dy) or 1.0
            step = min(dist, temperature)
            positions[node_id][0] += (dx / dist) * step
            positions[node_id][1] += (dy / dist) * step

        temperature *= 0.9

    return {node_id: (pos[0], pos[1]) for node_id, pos in positions.items()}
