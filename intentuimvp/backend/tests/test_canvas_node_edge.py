"""Unit tests for Canvas, Node, and Edge models."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.canvas import Canvas
from app.models.edge import Edge, RelationType
from app.models.node import Node, NodeType
from app.schemas.node import (
    BiasAnalysisSchema,
    CriticNodeMetadata,
    PerspectiveSchema,
    SynthesisNodeMetadata,
)


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
            content=None,
            position='{"x": 100, "y": 200, "z": 0}',
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        assert node.id is not None
        assert node.canvas_id == canvas.id
        assert node.type == NodeType.TEXT
        assert node.label == "Test Node"
        assert node.content is None
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
            content="Graph details",
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
        assert result["content"] == "Graph details"
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
            label="Depends on",
        )
        db_session.add(edge)
        db_session.commit()
        db_session.refresh(edge)

        assert edge.id is not None
        assert edge.canvas_id == canvas.id
        assert edge.from_node_id == node1.id
        assert edge.to_node_id == node2.id
        assert edge.relation_type == RelationType.DEPENDS_ON
        assert edge.label == "Depends on"
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
            label="Supports",
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
        assert result["label"] == "Supports"
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


class TestPlanAndDagNodeTypes:
    """Tests for Plan and DAG node types."""

    def test_create_plan_node(self, db_session: Session):
        """Test creating a plan node."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.PLAN,
            label="Project Plan",
            position='{"x": 100, "y": 200, "z": 0}',
            node_metadata='{"plan_id": "plan-001", "status": "draft"}',
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        assert node.id is not None
        assert node.canvas_id == canvas.id
        assert node.type == NodeType.PLAN
        assert node.label == "Project Plan"
        assert node.get_metadata() == {"plan_id": "plan-001", "status": "draft"}
        assert node.created_at is not None

    def test_create_dag_node(self, db_session: Session):
        """Test creating a DAG node."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.DAG,
            label="Task DAG",
            position='{"x": 300, "y": 400, "z": 0}',
            node_metadata='{"dag_id": "dag-001", "task_count": 5}',
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        assert node.id is not None
        assert node.canvas_id == canvas.id
        assert node.type == NodeType.DAG
        assert node.label == "Task DAG"
        assert node.get_metadata() == {"dag_id": "dag-001", "task_count": 5}
        assert node.created_at is not None

    def test_plan_node_to_dict(self, db_session: Session):
        """Test plan node serialization to dictionary."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.PLAN,
            label="Sprint Plan",
            position='{"x": 50, "y": 100, "z": 0}',
            node_metadata='{"sprint": 1, "goals": ["feature-a", "feature-b"]}',
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        result = node.to_dict()
        assert result["id"] == node.id
        assert result["canvasId"] == canvas.id
        assert result["type"] == NodeType.PLAN
        assert result["label"] == "Sprint Plan"
        assert result["position"] == {"x": 50, "y": 100, "z": 0}
        assert result["metadata"] == {"sprint": 1, "goals": ["feature-a", "feature-b"]}

    def test_dag_node_to_dict(self, db_session: Session):
        """Test DAG node serialization to dictionary."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.DAG,
            label="Workflow DAG",
            position='{"x": 150, "y": 250, "z": 0}',
            node_metadata='{"workflow_id": "wf-001", "nodes": 10, "edges": 15}',
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        result = node.to_dict()
        assert result["id"] == node.id
        assert result["canvasId"] == canvas.id
        assert result["type"] == NodeType.DAG
        assert result["label"] == "Workflow DAG"
        assert result["position"] == {"x": 150, "y": 250, "z": 0}
        assert result["metadata"] == {"workflow_id": "wf-001", "nodes": 10, "edges": 15}

    def test_plan_and_dag_nodes_with_edges(self, db_session: Session):
        """Test creating edges between plan and DAG nodes."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        plan_node = Node(
            canvas_id=canvas.id,
            type=NodeType.PLAN,
            label="Master Plan",
            position='{"x": 0, "y": 0, "z": 0}',
        )
        dag_node = Node(
            canvas_id=canvas.id,
            type=NodeType.DAG,
            label="Execution DAG",
            position='{"x": 200, "y": 0, "z": 0}',
        )
        db_session.add_all([plan_node, dag_node])
        db_session.commit()

        edge = Edge(
            canvas_id=canvas.id,
            from_node_id=plan_node.id,
            to_node_id=dag_node.id,
            relation_type=RelationType.DERIVED_FROM,
            label="Generates",
        )
        db_session.add(edge)
        db_session.commit()
        db_session.refresh(plan_node)
        db_session.refresh(dag_node)

        assert len(plan_node.outgoing_edges) == 1
        assert len(dag_node.incoming_edges) == 1
        assert plan_node.outgoing_edges[0].to_node_id == dag_node.id
        assert dag_node.incoming_edges[0].from_node_id == plan_node.id


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


class TestCriticAndSynthesisNodeTypes:
    """Tests for Critic and Synthesis node types (FR-012: Multi-Judge Compute)."""

    def test_critic_node_type_exists(self):
        """Test CRITIC node type is defined."""
        assert NodeType.CRITIC == "critic"

    def test_synthesis_node_type_exists(self):
        """Test SYNTHESIS node type is defined."""
        assert NodeType.SYNTHESIS == "synthesis"

    def test_create_critic_node(self, db_session: Session):
        """Test creating a critic node."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        perspective = PerspectiveSchema(
            id="persp-001",
            name="skeptic",
            description="Critical analysis of the topic",
            stance="con",
            arguments=["Weak evidence", "Unfounded assumptions"],
            evidence=["Source A lacks credibility"],
            confidence=0.7,
            strengths=["Rigorous scrutiny"],
            weaknesses=["May miss positive aspects"],
        )

        metadata = CriticNodeMetadata(
            topic="Should AI development continue unregulated?",
            perspective_type="skeptic",
            perspective=perspective,
            source_node_id=42,
        )

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.CRITIC,
            label="Skeptic Perspective",
            position='{"x": 100, "y": 200, "z": 0}',
            node_metadata=metadata.model_dump_json(),
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        assert node.id is not None
        assert node.canvas_id == canvas.id
        assert node.type == NodeType.CRITIC
        assert node.label == "Skeptic Perspective"
        retrieved_metadata = node.get_metadata()
        assert retrieved_metadata["topic"] == "Should AI development continue unregulated?"
        assert retrieved_metadata["perspective_type"] == "skeptic"
        assert retrieved_metadata["source_node_id"] == 42

    def test_create_synthesis_node(self, db_session: Session):
        """Test creating a synthesis node."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        perspectives = [
            PerspectiveSchema(
                id="persp-001",
                name="skeptic",
                description="Critical analysis",
                stance="con",
                arguments=["Argument 1"],
                confidence=0.7,
            ),
            PerspectiveSchema(
                id="persp-002",
                name="advocate",
                description="Supportive analysis",
                stance="pro",
                arguments=["Argument 2"],
                confidence=0.8,
            ),
        ]

        bias_analysis = BiasAnalysisSchema(
            detected_biases=["Framing bias"],
            bias_explanations=["Topic framed negatively"],
            mitigation_suggestions=["Include neutral framing"],
            overall_bias_rating="medium",
        )

        metadata = SynthesisNodeMetadata(
            topic="Should AI development continue unregulated?",
            perspectives=perspectives,
            consensus_points=["Both sides agree on need for transparency"],
            disagreement_points=["Disagree on regulatory scope"],
            bias_analysis=bias_analysis,
            recommendation="Implement moderate oversight",
            confidence=0.75,
            source_node_ids=[1, 2, 3],
        )

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.SYNTHESIS,
            label="Multi-Perspective Synthesis",
            position='{"x": 300, "y": 400, "z": 0}',
            node_metadata=metadata.model_dump_json(),
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        assert node.id is not None
        assert node.canvas_id == canvas.id
        assert node.type == NodeType.SYNTHESIS
        assert node.label == "Multi-Perspective Synthesis"
        retrieved_metadata = node.get_metadata()
        assert retrieved_metadata["topic"] == "Should AI development continue unregulated?"
        assert len(retrieved_metadata["perspectives"]) == 2
        assert retrieved_metadata["consensus_points"] == ["Both sides agree on need for transparency"]
        assert retrieved_metadata["bias_analysis"]["overall_bias_rating"] == "medium"
        assert retrieved_metadata["recommendation"] == "Implement moderate oversight"

    def test_critic_node_to_dict(self, db_session: Session):
        """Test critic node serialization to dictionary."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        perspective = PerspectiveSchema(
            id="persp-001",
            name="advocate",
            description="Supportive view",
            stance="pro",
            arguments=["Strong argument"],
            confidence=0.8,
        )

        metadata = CriticNodeMetadata(
            topic="Test topic",
            perspective_type="advocate",
            perspective=perspective,
        )

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.CRITIC,
            label="Advocate Perspective",
            position='{"x": 50, "y": 100, "z": 0}',
            node_metadata=metadata.model_dump_json(),
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        result = node.to_dict()
        assert result["id"] == node.id
        assert result["canvasId"] == canvas.id
        assert result["type"] == NodeType.CRITIC
        assert result["label"] == "Advocate Perspective"
        assert result["position"] == {"x": 50, "y": 100, "z": 0}
        assert result["metadata"]["perspective_type"] == "advocate"

    def test_synthesis_node_to_dict(self, db_session: Session):
        """Test synthesis node serialization to dictionary."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        metadata = SynthesisNodeMetadata(
            topic="Test topic",
            perspectives=[],
            consensus_points=["Common ground"],
            recommendation="Balanced approach",
            confidence=0.6,
        )

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.SYNTHESIS,
            label="Combined Analysis",
            position='{"x": 200, "y": 300, "z": 0}',
            node_metadata=metadata.model_dump_json(),
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        result = node.to_dict()
        assert result["id"] == node.id
        assert result["canvasId"] == canvas.id
        assert result["type"] == NodeType.SYNTHESIS
        assert result["label"] == "Combined Analysis"
        assert result["position"] == {"x": 200, "y": 300, "z": 0}
        assert result["metadata"]["confidence"] == 0.6

    def test_perspective_schema_validation(self):
        """Test PerspectiveSchema with all fields."""
        perspective = PerspectiveSchema(
            id="test-id",
            name="synthesizer",
            description="Bridge-building analysis",
            stance="neutral",
            arguments=["Finding common ground", "Identifying shared values"],
            evidence=["Source verification"],
            confidence=0.85,
            strengths=["Balanced view"],
            weaknesses=["May oversimplify"],
        )

        assert perspective.id == "test-id"
        assert perspective.name == "synthesizer"
        assert perspective.stance == "neutral"
        assert perspective.confidence == 0.85
        assert perspective.failed is False
        assert perspective.failure_reason is None

    def test_perspective_schema_with_failure(self):
        """Test PerspectiveSchema representing a failed perspective."""
        perspective = PerspectiveSchema(
            id="failed-persp",
            name="skeptic",
            description="Failed to generate",
            stance="neutral",
            arguments=[],
            confidence=0.0,
            failed=True,
            failure_reason="Timeout after 30s",
        )

        assert perspective.failed is True
        assert perspective.failure_reason == "Timeout after 30s"
        assert perspective.confidence == 0.0

    def test_bias_analysis_schema_defaults(self):
        """Test BiasAnalysisSchema default values."""
        bias = BiasAnalysisSchema()

        assert bias.detected_biases == []
        assert bias.bias_explanations == []
        assert bias.mitigation_suggestions == []
        assert bias.overall_bias_rating == "unknown"

    def test_critic_synthesis_with_failed_perspectives(self, db_session: Session):
        """Test synthesis node with failed perspectives included."""
        canvas = Canvas(user_id="user-123", name="Test Canvas")
        db_session.add(canvas)
        db_session.commit()

        successful_perspective = PerspectiveSchema(
            id="good-persp",
            name="advocate",
            description="Successful analysis",
            stance="pro",
            arguments=["Strong case"],
            confidence=0.8,
        )

        failed_perspective = PerspectiveSchema(
            id="bad-persp",
            name="skeptic",
            description="Failed to generate",
            stance="neutral",
            arguments=[],
            confidence=0.0,
            failed=True,
            failure_reason="Gateway timeout",
        )

        metadata = SynthesisNodeMetadata(
            topic="Mixed results topic",
            perspectives=[successful_perspective, failed_perspective],
            consensus_points=[],
            recommendation="Partial analysis available",
            confidence=0.4,
        )

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.SYNTHESIS,
            label="Partial Analysis",
            position='{"x": 0, "y": 0, "z": 0}',
            node_metadata=metadata.model_dump_json(),
        )
        db_session.add(node)
        db_session.commit()
        db_session.refresh(node)

        retrieved_metadata = node.get_metadata()
        perspectives = retrieved_metadata["perspectives"]
        assert len(perspectives) == 2
        # Check that failed perspective is included
        assert perspectives[1]["failed"] is True
        assert perspectives[1]["failure_reason"] == "Gateway timeout"
