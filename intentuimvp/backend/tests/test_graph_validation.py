"""Unit tests for graph_validation module (cycle detection)."""

import pytest

from app.graph_validation import (
    DependencyCycleError,
    dependency_edges_have_cycle,
    ensure_dependency_edges_acyclic,
)


class TestDependencyEdgesHaveCycle:
    """Tests for dependency_edges_have_cycle function."""

    def test_empty_edges_no_cycle(self):
        """Empty edge list has no cycle."""
        assert dependency_edges_have_cycle([]) is False

    def test_single_edge_no_cycle(self):
        """A single edge cannot form a cycle."""
        assert dependency_edges_have_cycle([(1, 2)]) is False

    def test_linear_chain_no_cycle(self):
        """Linear chain 1 -> 2 -> 3 -> 4 has no cycle."""
        edges = [(1, 2), (2, 3), (3, 4)]
        assert dependency_edges_have_cycle(edges) is False

    def test_tree_structure_no_cycle(self):
        """Tree structure (one root, multiple children) has no cycle."""
        edges = [(1, 2), (1, 3), (2, 4), (2, 5), (3, 6)]
        assert dependency_edges_have_cycle(edges) is False

    def test_dag_with_convergence_no_cycle(self):
        """DAG with convergence (diamond shape) has no cycle."""
        edges = [(1, 2), (1, 3), (2, 4), (3, 4)]
        assert dependency_edges_have_cycle(edges) is False

    def test_simple_cycle_detected(self):
        """Simple cycle 1 -> 2 -> 1 is detected."""
        edges = [(1, 2), (2, 1)]
        assert dependency_edges_have_cycle(edges) is True

    def test_self_loop_detected(self):
        """Self-loop 1 -> 1 is detected as a cycle."""
        edges = [(1, 1)]
        assert dependency_edges_have_cycle(edges) is True

    def test_triangle_cycle_detected(self):
        """Triangle cycle 1 -> 2 -> 3 -> 1 is detected."""
        edges = [(1, 2), (2, 3), (3, 1)]
        assert dependency_edges_have_cycle(edges) is True

    def test_cycle_in_larger_graph(self):
        """Cycle embedded in larger graph is detected."""
        edges = [
            (1, 2),
            (2, 3),
            (3, 4),
            (4, 2),  # This creates cycle: 2 -> 3 -> 4 -> 2
            (4, 5),
        ]
        assert dependency_edges_have_cycle(edges) is True

    def test_disconnected_components_no_cycle(self):
        """Multiple disconnected acyclic components have no cycle."""
        edges = [(1, 2), (3, 4), (5, 6)]
        assert dependency_edges_have_cycle(edges) is False

    def test_disconnected_components_with_cycle(self):
        """Cycle in one of multiple disconnected components is detected."""
        edges = [(1, 2), (3, 4), (4, 3)]  # Cycle in second component
        assert dependency_edges_have_cycle(edges) is True

    def test_complex_dag_no_cycle(self):
        """Complex DAG with multiple paths has no cycle."""
        edges = [
            (1, 2),
            (1, 3),
            (2, 4),
            (2, 5),
            (3, 5),
            (3, 6),
            (4, 7),
            (5, 7),
            (6, 7),
        ]
        assert dependency_edges_have_cycle(edges) is False

    def test_duplicate_edges_handled(self):
        """Duplicate edges don't cause issues."""
        edges = [(1, 2), (1, 2), (2, 3)]
        assert dependency_edges_have_cycle(edges) is False

    def test_duplicate_edges_with_cycle(self):
        """Cycle with duplicate edges is detected."""
        edges = [(1, 2), (2, 3), (3, 1), (1, 2)]
        assert dependency_edges_have_cycle(edges) is True

    def test_long_chain_no_cycle(self):
        """Long linear chain has no cycle."""
        edges = [(i, i + 1) for i in range(100)]
        assert dependency_edges_have_cycle(edges) is False

    def test_long_chain_with_back_edge(self):
        """Long chain with back edge to start creates a cycle."""
        edges = [(i, i + 1) for i in range(100)] + [(99, 0)]
        assert dependency_edges_have_cycle(edges) is True


class TestEnsureDependencyEdgesAcyclic:
    """Tests for ensure_dependency_edges_acyclic function."""

    def test_acyclic_graph_no_exception(self):
        """Acyclic graph does not raise exception."""
        edges = [(1, 2), (2, 3), (3, 4)]
        ensure_dependency_edges_acyclic(edges)  # Should not raise

    def test_empty_edges_no_exception(self):
        """Empty edges do not raise exception."""
        ensure_dependency_edges_acyclic([])  # Should not raise

    def test_cyclic_graph_raises_error(self):
        """Cyclic graph raises DependencyCycleError."""
        edges = [(1, 2), (2, 3), (3, 1)]
        with pytest.raises(DependencyCycleError) as exc_info:
            ensure_dependency_edges_acyclic(edges)
        assert "Dependency cycle detected" in str(exc_info.value)

    def test_self_loop_raises_error(self):
        """Self-loop raises DependencyCycleError."""
        edges = [(1, 1)]
        with pytest.raises(DependencyCycleError):
            ensure_dependency_edges_acyclic(edges)


class TestDependencyCycleError:
    """Tests for DependencyCycleError exception."""

    def test_is_value_error(self):
        """DependencyCycleError is a subclass of ValueError."""
        assert issubclass(DependencyCycleError, ValueError)

    def test_can_be_raised_with_message(self):
        """Can raise DependencyCycleError with custom message."""
        with pytest.raises(DependencyCycleError) as exc_info:
            raise DependencyCycleError("Custom cycle message")
        assert "Custom cycle message" in str(exc_info.value)
