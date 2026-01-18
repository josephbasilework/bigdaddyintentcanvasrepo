"""Tests for incremental/diff-based canvas persistence.

Tests the diff computation and incremental save functionality
that minimizes database operations by only applying changes.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.canvas import Canvas
from app.models.edge import Edge, RelationType
from app.models.node import Node, NodeType
from app.repositories.canvas import CanvasRepository
from app.repositories.diff import compute_edge_diff, compute_node_diff


@pytest.fixture
def in_memory_db() -> Generator:
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(in_memory_db) -> Generator[Session, None, None]:
    """Create a database session for testing."""
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=in_memory_db)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


class TestNodeDiffComputation:
    """Tests for node diff computation."""

    def test_no_changes_when_identical(self, db_session: Session) -> None:
        """Test that no changes are detected when data is identical."""
        # Create existing nodes
        canvas = Canvas(user_id="test_user", name="Test")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 1",
            position='{"x": 100, "y": 200, "z": 0}',
        )
        node2 = Node(
            canvas_id=canvas.id,
            type=NodeType.DOCUMENT,
            label="Node 2",
            position='{"x": 300, "y": 400, "z": 0}',
        )
        db_session.add_all([node1, node2])
        db_session.commit()

        # Incoming data identical to existing
        incoming_nodes = [
            {"id": node1.id, "label": "Node 1", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
            {"id": node2.id, "label": "Node 2", "type": NodeType.DOCUMENT, "x": 300, "y": 400, "z": 0},
        ]

        existing_nodes = db_session.query(Node).filter_by(canvas_id=canvas.id).all()
        changes = compute_node_diff(existing_nodes, incoming_nodes)

        # Should have no create, update, or delete operations
        assert sum(1 for c in changes if c.action == "create") == 0
        assert sum(1 for c in changes if c.action == "update") == 0
        assert sum(1 for c in changes if c.action == "delete") == 0

    def test_detects_node_position_change(self, db_session: Session) -> None:
        """Test that position changes are detected."""
        canvas = Canvas(user_id="test_user", name="Test")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 1",
            position='{"x": 100, "y": 200, "z": 0}',
        )
        db_session.add(node)
        db_session.commit()

        # Position changed
        incoming_nodes = [
            {"id": node.id, "label": "Node 1", "type": NodeType.TEXT, "x": 500, "y": 600, "z": 0},
        ]

        existing_nodes = [node]
        changes = compute_node_diff(existing_nodes, incoming_nodes)

        updates = [c for c in changes if c.action == "update"]
        assert len(updates) == 1
        assert updates[0].db_id == node.id

    def test_detects_node_label_change(self, db_session: Session) -> None:
        """Test that label changes are detected."""
        canvas = Canvas(user_id="test_user", name="Test")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Old Label",
            position='{"x": 100, "y": 200, "z": 0}',
        )
        db_session.add(node)
        db_session.commit()

        # Label changed
        incoming_nodes = [
            {"id": node.id, "label": "New Label", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
        ]

        existing_nodes = [node]
        changes = compute_node_diff(existing_nodes, incoming_nodes)

        updates = [c for c in changes if c.action == "update"]
        assert len(updates) == 1

    def test_detects_node_content_change(self, db_session: Session) -> None:
        """Test that content changes are detected."""
        canvas = Canvas(user_id="test_user", name="Test")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 1",
            content="Old content",
            position='{"x": 100, "y": 200, "z": 0}',
        )
        db_session.add(node)
        db_session.commit()

        incoming_nodes = [
            {
                "id": node.id,
                "label": "Node 1",
                "type": NodeType.TEXT,
                "content": "New content",
                "x": 100,
                "y": 200,
                "z": 0,
            },
        ]

        existing_nodes = [node]
        changes = compute_node_diff(existing_nodes, incoming_nodes)

        updates = [c for c in changes if c.action == "update"]
        assert len(updates) == 1

    def test_detects_new_nodes(self, db_session: Session) -> None:
        """Test that new nodes are detected."""
        canvas = Canvas(user_id="test_user", name="Test")
        db_session.add(canvas)
        db_session.commit()

        # Existing node
        node1 = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 1",
            position='{"x": 100, "y": 200, "z": 0}',
        )
        db_session.add(node1)
        db_session.commit()

        # Incoming data has existing node plus a new one
        incoming_nodes = [
            {"id": node1.id, "label": "Node 1", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
            {"id": "new-node-123", "label": "New Node", "type": NodeType.DOCUMENT, "x": 300, "y": 400, "z": 0},
        ]

        existing_nodes = [node1]
        changes = compute_node_diff(existing_nodes, incoming_nodes)

        creates = [c for c in changes if c.action == "create"]
        assert len(creates) == 1
        assert creates[0].client_id == "new-node-123"

    def test_detects_deleted_nodes(self, db_session: Session) -> None:
        """Test that deleted nodes are detected."""
        canvas = Canvas(user_id="test_user", name="Test")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 1",
            position='{"x": 100, "y": 200, "z": 0}',
        )
        node2 = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 2",
            position='{"x": 300, "y": 400, "z": 0}',
        )
        db_session.add_all([node1, node2])
        db_session.commit()

        # Only node1 in incoming, node2 should be deleted
        incoming_nodes = [
            {"id": node1.id, "label": "Node 1", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
        ]

        existing_nodes = [node1, node2]
        changes = compute_node_diff(existing_nodes, incoming_nodes)

        deletes = [c for c in changes if c.action == "delete"]
        assert len(deletes) == 1
        assert deletes[0].db_id == node2.id


class TestEdgeDiffComputation:
    """Tests for edge diff computation."""

    def test_no_changes_when_identical(self, db_session: Session) -> None:
        """Test that no changes are detected when edges are identical."""
        canvas = Canvas(user_id="test_user", name="Test")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 1",
            position='{"x": 0, "y": 0, "z": 0}',
        )
        node2 = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 2",
            position='{"x": 100, "y": 0, "z": 0}',
        )
        db_session.add_all([node1, node2])
        db_session.commit()

        edge = Edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.DEPENDS_ON,
            label="Depends",
        )
        db_session.add(edge)
        db_session.commit()

        # Same edge in incoming
        incoming_edges = [
            {
                "fromNodeId": node1.id,
                "toNodeId": node2.id,
                "relationType": "depends_on",
                "label": "Depends",
            },
        ]

        node_id_map = {str(node1.id): node1.id, str(node2.id): node2.id}
        existing_edges = [edge]
        changes = compute_edge_diff(existing_edges, incoming_edges, node_id_map)

        assert sum(1 for c in changes if c.action == "create") == 0
        assert sum(1 for c in changes if c.action == "delete") == 0

    def test_detects_new_edges(self, db_session: Session) -> None:
        """Test that new edges are detected."""
        canvas = Canvas(user_id="test_user", name="Test")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 1",
            position='{"x": 0, "y": 0, "z": 0}',
        )
        node2 = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 2",
            position='{"x": 100, "y": 0, "z": 0}',
        )
        db_session.add_all([node1, node2])
        db_session.commit()

        # No existing edges
        incoming_edges = [
            {
                "fromNodeId": node1.id,
                "toNodeId": node2.id,
                "relationType": "depends_on",
                "label": "Depends",
            },
        ]

        node_id_map = {str(node1.id): node1.id, str(node2.id): node2.id}
        changes = compute_edge_diff([], incoming_edges, node_id_map)

        creates = [c for c in changes if c.action == "create"]
        assert len(creates) == 1
        assert creates[0].resolved_from_id == node1.id
        assert creates[0].resolved_to_id == node2.id

    def test_detects_deleted_edges(self, db_session: Session) -> None:
        """Test that deleted edges are detected."""
        canvas = Canvas(user_id="test_user", name="Test")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 1",
            position='{"x": 0, "y": 0, "z": 0}',
        )
        node2 = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Node 2",
            position='{"x": 100, "y": 0, "z": 0}',
        )
        db_session.add_all([node1, node2])
        db_session.commit()

        edge = Edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.DEPENDS_ON,
        )
        db_session.add(edge)
        db_session.commit()

        # No incoming edges - edge should be deleted
        node_id_map = {str(node1.id): node1.id, str(node2.id): node2.id}
        changes = compute_edge_diff([edge], [], node_id_map)

        deletes = [c for c in changes if c.action == "delete"]
        assert len(deletes) == 1
        assert deletes[0].db_edge is not None
        assert deletes[0].db_edge.id == edge.id


class TestIncrementalSave:
    """Integration tests for incremental save functionality."""

    def test_incremental_save_creates_new_canvas(self, db_session: Session) -> None:
        """Test that incremental save creates a new canvas if none exists."""
        repo = CanvasRepository(db_session)

        canvas_data = {
            "nodes": [
                {"id": "node-1", "label": "Node 1", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
            ],
            "edges": [],
        }

        canvas = repo.save_canvas_incremental("test_user", canvas_data, "Test Canvas")

        assert canvas is not None
        assert canvas.user_id == "test_user"
        assert canvas.name == "Test Canvas"
        assert len(canvas.nodes) == 1
        assert canvas.nodes[0].label == "Node 1"

    def test_incremental_save_adds_nodes(self, db_session: Session) -> None:
        """Test that incremental save adds new nodes to existing canvas."""
        repo = CanvasRepository(db_session)

        # Create initial canvas with one node
        initial_data = {
            "nodes": [
                {"id": "node-1", "label": "Node 1", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
            ],
            "edges": [],
        }
        canvas = repo.save_canvas_incremental("test_user", initial_data, "Test Canvas")
        initial_node_count = len(canvas.nodes)

        # Add another node
        updated_data = {
            "nodes": [
                {"id": canvas.nodes[0].id, "label": "Node 1", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
                {"id": "node-2", "label": "Node 2", "type": NodeType.DOCUMENT, "x": 300, "y": 400, "z": 0},
            ],
            "edges": [],
        }
        canvas = repo.save_canvas_incremental("test_user", updated_data, "Test Canvas")

        assert len(canvas.nodes) == initial_node_count + 1
        node_labels = {n.label for n in canvas.nodes}
        assert node_labels == {"Node 1", "Node 2"}

    def test_incremental_save_updates_existing_nodes(self, db_session: Session) -> None:
        """Test that incremental save updates existing nodes."""
        repo = CanvasRepository(db_session)

        # Create initial canvas
        initial_data = {
            "nodes": [
                {"id": "node-1", "label": "Original Label", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
            ],
            "edges": [],
        }
        canvas = repo.save_canvas_incremental("test_user", initial_data, "Test Canvas")
        node_id = canvas.nodes[0].id

        # Update the node
        updated_data = {
            "nodes": [
                {"id": node_id, "label": "Updated Label", "type": NodeType.TEXT, "x": 500, "y": 600, "z": 0},
            ],
            "edges": [],
        }
        canvas = repo.save_canvas_incremental("test_user", updated_data, "Test Canvas")

        assert len(canvas.nodes) == 1
        assert canvas.nodes[0].id == node_id  # Same node
        assert canvas.nodes[0].label == "Updated Label"
        assert canvas.nodes[0].get_position() == {"x": 500, "y": 600, "z": 0}

    def test_incremental_save_deletes_removed_nodes(self, db_session: Session) -> None:
        """Test that incremental save deletes nodes not in incoming data."""
        repo = CanvasRepository(db_session)

        # Create canvas with two nodes
        initial_data = {
            "nodes": [
                {"id": "node-1", "label": "Node 1", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
                {"id": "node-2", "label": "Node 2", "type": NodeType.TEXT, "x": 300, "y": 400, "z": 0},
            ],
            "edges": [],
        }
        canvas = repo.save_canvas_incremental("test_user", initial_data, "Test Canvas")
        node1_id = canvas.nodes[0].id

        # Save with only node1 (node2 should be deleted)
        updated_data = {
            "nodes": [
                {"id": node1_id, "label": "Node 1", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
            ],
            "edges": [],
        }
        canvas = repo.save_canvas_incremental("test_user", updated_data, "Test Canvas")

        assert len(canvas.nodes) == 1
        assert canvas.nodes[0].label == "Node 1"

    def test_incremental_save_adds_and_removes_edges(self, db_session: Session) -> None:
        """Test that incremental save handles edge creation and deletion."""
        repo = CanvasRepository(db_session)

        # Create canvas with nodes and one edge
        initial_data = {
            "nodes": [
                {"id": "node-1", "label": "Node 1", "type": NodeType.TEXT, "x": 0, "y": 0, "z": 0},
                {"id": "node-2", "label": "Node 2", "type": NodeType.TEXT, "x": 100, "y": 0, "z": 0},
                {"id": "node-3", "label": "Node 3", "type": NodeType.TEXT, "x": 200, "y": 0, "z": 0},
            ],
            "edges": [
                {"fromNodeId": "node-1", "toNodeId": "node-2", "relationType": "depends_on", "label": "Depends"},
            ],
        }
        canvas = repo.save_canvas_incremental("test_user", initial_data, "Test Canvas")
        node1_id = canvas.nodes[0].id
        node2_id = canvas.nodes[1].id
        node3_id = canvas.nodes[2].id
        initial_edge_count = len(canvas.edges)

        # Remove old edge, add new edge from node2 to node3
        updated_data = {
            "nodes": [
                {"id": node1_id, "label": "Node 1", "type": NodeType.TEXT, "x": 0, "y": 0, "z": 0},
                {"id": node2_id, "label": "Node 2", "type": NodeType.TEXT, "x": 100, "y": 0, "z": 0},
                {"id": node3_id, "label": "Node 3", "type": NodeType.TEXT, "x": 200, "y": 0, "z": 0},
            ],
            "edges": [
                {"fromNodeId": node2_id, "toNodeId": node3_id, "relationType": "supports", "label": "Supports"},
            ],
        }
        canvas = repo.save_canvas_incremental("test_user", updated_data, "Test Canvas")

        assert len(canvas.edges) == initial_edge_count  # Still 1 edge, but different
        assert canvas.edges[0].from_node_id == node2_id
        assert canvas.edges[0].to_node_id == node3_id
        assert canvas.edges[0].relation_type == RelationType.SUPPORTS

    def test_incremental_save_preserves_unchanged_data(self, db_session: Session) -> None:
        """Test that unchanged nodes are not modified."""
        repo = CanvasRepository(db_session)

        # Create initial canvas
        initial_data = {
            "nodes": [
                {"id": "node-1", "label": "Node 1", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
                {"id": "node-2", "label": "Node 2", "type": NodeType.DOCUMENT, "x": 300, "y": 400, "z": 0},
            ],
            "edges": [],
        }
        canvas = repo.save_canvas_incremental("test_user", initial_data, "Test Canvas")
        node1_id = canvas.nodes[0].id
        original_created_at = canvas.nodes[0].created_at

        # Save with only node2 changed, node1 unchanged
        updated_data = {
            "nodes": [
                {"id": node1_id, "label": "Node 1", "type": NodeType.TEXT, "x": 100, "y": 200, "z": 0},
                {"id": canvas.nodes[1].id, "label": "Node 2 Updated", "type": NodeType.DOCUMENT, "x": 300, "y": 400, "z": 0},
            ],
            "edges": [],
        }
        canvas = repo.save_canvas_incremental("test_user", updated_data, "Test Canvas")

        # Find node1 in the refreshed canvas
        node1 = next((n for n in canvas.nodes if n.id == node1_id), None)
        assert node1 is not None
        assert node1.label == "Node 1"
        assert node1.created_at == original_created_at  # Unchanged node keeps created_at
        assert canvas.nodes[1].label == "Node 2 Updated"
