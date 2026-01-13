"""Helpers for validating dependency graphs."""

from collections import defaultdict, deque
from collections.abc import Iterable


class DependencyCycleError(ValueError):
    """Raised when dependency edges introduce a cycle.

    Domain Invariant: TI-001 - TaskDAG must be acyclic (topological sort validation).
    See: PRD §14 Domain Invariants & Business Rules
    """

    def __init__(self, message: str = "Dependency cycle detected") -> None:
        super().__init__(
            f"[TI-001] {message}. See PRD §14: Domain Invariants & Business Rules"
        )


def dependency_edges_have_cycle(edges: Iterable[tuple[int, int]]) -> bool:
    """Return True if the directed edge list contains a cycle."""
    adjacency: dict[int, set[int]] = defaultdict(set)
    in_degree: dict[int, int] = {}

    for source, target in edges:
        in_degree.setdefault(source, 0)
        in_degree.setdefault(target, 0)
        if target not in adjacency[source]:
            adjacency[source].add(target)
            in_degree[target] += 1

    if not in_degree:
        return False

    queue = deque(node for node, degree in in_degree.items() if degree == 0)
    visited = 0

    while queue:
        node = queue.popleft()
        visited += 1
        for neighbor in adjacency.get(node, ()):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return visited != len(in_degree)


def ensure_dependency_edges_acyclic(edges: Iterable[tuple[int, int]]) -> None:
    """Raise DependencyCycleError if dependency edges contain a cycle."""
    if dependency_edges_have_cycle(edges):
        raise DependencyCycleError("Dependency cycle detected")
