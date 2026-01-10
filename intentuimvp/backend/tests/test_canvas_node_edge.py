"""Unit tests for Canvas, Node, and Edge models."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.canvas import Canvas
from app.models.edge import Edge, RelationType
from app.models.node import Node, NodeType


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(in_memory_db):
    """Create a database session for testing."""
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=in_memory_db)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


class TestCanvasModel:
    """Tests for Canvas model."""

    def test_create_canvas(self, db_session: Session):
        """Test creating a canvas."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()
        db_session.refresh(canvas)

        assert canvas.id is not None
        assert canvas.user_id == "user-123"
        assert canvas.name == "Test Canvas"
        assert canvas.created_at is not None
        assert canvas.updated_at is not None

    def test_canvas_to_dict(self, db_session: Session):
        """Test canvas serialization to dictionary."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()
        db_session.refresh(canvas)

        result = canvas.to_dict()
        assert result["id"] == canvas.id
        assert result["userId"] == "user-123"
        assert result["name"] == "Test Canvas"
        assert "created_at" in result
        assert "updated_at" in result


class TestNodeModel:
    """Tests for Node model."""

    def test_create_node(self, db_session: Session):
        """Test creating a node."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Test Node",
            position='{"x": 100, "y": 200, "z": 0}',
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        assert node.id is not None
        assert node.canvas_id == canvas.id
        assert node.type == NodeType.TEXT
        assert node.label == "Test Node"
        assert node.created_at is not None

    def test_node_position_methods(self, db_session: Session):
        """Test node position getter/setter."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Test Node",
            position='{"x": 100, "y": 200, "z": 0}',
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        # Test get_position
        position = node.get_position()
        assert position == {"x": 100, "y": 200, "z": 0}

        # Test set_position
        new_position = {"x": 50, "y": 75, "z": 5}
        node.set_position(new_position)
        db_session.commit()
        db_session.refresh(node)
        assert node.get_position() == new_position

    def test_node_metadata_methods(self, db_session: Session):
        """Test node metadata getter/setter."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.DOCUMENT,
            label="Doc Node",
            position='{"x": 0, "y": 0, "z": 0}',
            node_metadata='{"color": "blue", "size": "large"}',
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        # Test get_metadata
        metadata = node.get_metadata()
        assert metadata == {"color": "blue", "size": "large"}

        # Test set_metadata
        new_metadata = {"color": "red", "tags": ["important"]}
        node.set_metadata(new_metadata)
        db_session.commit()
        db_session.refresh(node)
        assert node.get_metadata() == new_metadata

    def test_node_to_dict(self, db_session: Session):
        """Test node serialization to dictionary."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.GRAPH,
            label="Graph Node",
            position='{"x": 10, "y": 20, "z": 0}',
            node_metadata='{"data": "test"}',
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        result = node.to_dict()
        assert result["id"] == node.id
        assert result["canvasId"] == canvas.id
        assert result["type"] == NodeType.GRAPH
        assert result["label"] == "Graph Node"
        assert result["position"] == {"x": 10, "y": 20, "z": 0}
        assert result["metadata"] == {"data": "test"}
        assert "created_at" in result


class TestEdgeModel:
    """Tests for Edge model."""

    def test_create_edge(self, db_session: Session):
        """Test creating an edge."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 1", position='{"x": 0, "y": 0, "z": 0}'
        )
        node2 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 2", position='{"x": 100, "y": 0, "z": 0}'
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
        db_session.refresh(edge)

        assert edge.id is not None
        assert edge.canvas_id == canvas.id
        assert edge.from_node_id == node1.id
        assert edge.to_node_id == node2.id
        assert edge.relation_type == RelationType.DEPENDS_ON
        assert edge.created_at is not None

    def test_edge_to_dict(self, db_session: Session):
        """Test edge serialization to dictionary."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 1", position='{"x": 0, "y": 0, "z": 0}'
        )
        node2 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 2", position='{"x": 100, "y": 0, "z": 0}'
        )
        db_session.add_all([node1, node2])
        db_session.commit()

        edge = Edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.SUPPORTS,
        )
        db_session.add(edge)
        db_session.commit()
        db_session.refresh(edge)

        result = edge.to_dict()
        assert result["id"] == edge.id
        assert result["canvasId"] == canvas.id
        assert result["fromNodeId"] == node1.id
        assert result["toNodeId"] == node2.id
        assert result["relationType"] == RelationType.SUPPORTS
        assert "created_at" in result


class TestModelRelationships:
    """Tests for relationships between Canvas, Node, and Edge models."""

    def test_canvas_nodes_relationship(self, db_session: Session):
        """Test Canvas -> Nodes relationship."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 1", position='{"x": 0, "y": 0, "z": 0}'
        )
        node2 = Node(
            canvas_id=canvas.id, type=NodeType.DOCUMENT, label="Node 2", position='{"x": 100, "y": 0, "z": 0}'
        )
        db_session.add_all([node1, node2])
        db_session.commit()
        db_session.refresh(canvas)

        assert len(canvas.nodes) == 2
        assert canvas.nodes[0].label in ["Node 1", "Node 2"]
        assert canvas.nodes[1].label in ["Node 1", "Node 2"]

    def test_canvas_edges_relationship(self, db_session: Session):
        """Test Canvas -> Edges relationship."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 1", position='{"x": 0, "y": 0, "z": 0}'
        )
        node2 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 2", position='{"x": 100, "y": 0, "z": 0}'
        )
        db_session.add_all([node1, node2])
        db_session.commit()

        edge = Edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.REFERENCES,
        )
        db_session.add(edge)
        db_session.commit()
        db_session.refresh(canvas)

        assert len(canvas.edges) == 1
        assert canvas.edges[0].relation_type == RelationType.REFERENCES

    def test_node_canvas_relationship(self, db_session: Session):
        """Test Node -> Canvas relationship."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Test Node", position='{"x": 0, "y": 0, "z": 0}'
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        assert node.canvas.id == canvas.id
        assert node.canvas.name == "Test Canvas"

    def test_node_outgoing_edges(self, db_session: Session):
        """Test Node -> Outgoing Edges relationship."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 1", position='{"x": 0, "y": 0, "z": 0}'
        )
        node2 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 2", position='{"x": 100, "y": 0, "z": 0}'
        )
        node3 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 3", position='{"x": 200, "y": 0, "z": 0}'
        )
        db_session.add_all([node1, node2, node3])
        db_session.commit()

        edge1 = Edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.DEPENDS_ON,
        )
        edge2 = Edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node3.id,
            relation_type=RelationType.SUPPORTS,
        )
        db_session.add_all([edge1, edge2])
        db_session.commit()
        db_session.refresh(node1)

        assert len(node1.outgoing_edges) == 2
        assert set(e.relation_type for e in node1.outgoing_edges) == {
            RelationType.DEPENDS_ON,
            RelationType.SUPPORTS,
        }

    def test_node_incoming_edges(self, db_session: Session):
        """Test Node -> Incoming Edges relationship."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 1", position='{"x": 0, "y": 0, "z": 0}'
        )
        node2 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 2", position='{"x": 100, "y": 0, "z": 0}'
        )
        node3 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 3", position='{"x": 200, "y": 0, "z": 0}'
        )
        db_session.add_all([node1, node2, node3])
        db_session.commit()

        edge1 = Edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node3.id,
            relation_type=RelationType.DEPENDS_ON,
        )
        edge2 = Edge(
            canvas_id=canvas.id,
            from_node_id=node2.id,
            to_node_id=node3.id,
            relation_type=RelationType.SUPPORTS,
        )
        db_session.add_all([edge1, edge2])
        db_session.commit()
        db_session.refresh(node3)

        assert len(node3.incoming_edges) == 2
        assert set(e.relation_type for e in node3.incoming_edges) == {
            RelationType.DEPENDS_ON,
            RelationType.SUPPORTS,
        }

    def test_edge_from_node_relationship(self, db_session: Session):
        """Test Edge -> From Node relationship."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 1", position='{"x": 0, "y": 0, "z": 0}'
        )
        node2 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 2", position='{"x": 100, "y": 0, "z": 0}'
        )
        db_session.add_all([node1, node2])
        db_session.commit()

        edge = Edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.CONFLICTS,
        )
        db_session.add(edge)
        db_session.commit()
        db_session.refresh(edge)

        assert edge.from_node.id == node1.id
        assert edge.from_node.label == "Node 1"

    def test_edge_to_node_relationship(self, db_session: Session):
        """Test Edge -> To Node relationship."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 1", position='{"x": 0, "y": 0, "z": 0}'
        )
        node2 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 2", position='{"x": 100, "y": 0, "z": 0}'
        )
        db_session.add_all([node1, node2])
        db_session.commit()

        edge = Edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.CRITIQUES,
        )
        db_session.add(edge)
        db_session.commit()
        db_session.refresh(edge)

        assert edge.to_node.id == node2.id
        assert edge.to_node.label == "Node 2"


class TestCascadeDelete:
    """Tests for cascade delete behavior."""

    def test_delete_canvas_deletes_nodes(self, db_session: Session):
        """Test deleting a canvas deletes its nodes."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Test Node", position='{"x": 0, "y": 0, "z": 0}'
        )
        db_session.add(node)
        db_session.commit()

        node_id = node.id
        db_session.delete(canvas)
        db_session.commit()

        deleted_node = db_session.query(Node).filter_by(id=node_id).first()
        assert deleted_node is None

    def test_delete_canvas_deletes_edges(self, db_session: Session):
        """Test deleting a canvas deletes its edges."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node1 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 1", position='{"x": 0, "y": 0, "z": 0}'
        )
        node2 = Node(
            canvas_id=canvas.id, type=NodeType.TEXT, label="Node 2", position='{"x": 100, "y": 0, "z": 0}'
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

        edge_id = edge.id
        db_session.delete(canvas)
        db_session.commit()

        deleted_edge = db_session.query(Edge).filter_by(id=edge_id).first()
        assert deleted_edge is None
