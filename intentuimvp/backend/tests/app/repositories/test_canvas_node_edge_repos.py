"""Unit and integration tests for Canvas, Node, and Edge repositories."""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import models to register them with Base
import app.models.canvas  # noqa: F401 - Side-effect import to register models
from app.database import Base
from app.models.edge import RelationType
from app.models.node import NodeType
from app.repositories.canvas_repo import CanvasRepository
from app.repositories.edge_repo import EdgeRepository
from app.repositories.node_repo import NodeRepository

# In-memory async test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async test engine with in-memory database."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_db(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for tests."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.mark.asyncio
class TestCanvasRepository:
    """Unit tests for CanvasRepository CRUD operations."""

    async def test_create_canvas(self, async_db: AsyncSession) -> None:
        """Test creating a new canvas."""
        repo = CanvasRepository(async_db)
        canvas = await repo.create_canvas(
            user_id="test_user",
            name="Test Canvas",
        )

        assert canvas.id is not None
        assert canvas.user_id == "test_user"
        assert canvas.name == "Test Canvas"
        assert canvas.created_at is not None
        assert canvas.updated_at is not None

    async def test_get_by_id(self, async_db: AsyncSession) -> None:
        """Test getting canvas by ID."""
        repo = CanvasRepository(async_db)
        created = await repo.create_canvas(user_id="test_user", name="Test")

        retrieved = await repo.get_by_id(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Test"

    async def test_get_by_id_not_found(self, async_db: AsyncSession) -> None:
        """Test getting non-existent canvas returns None."""
        repo = CanvasRepository(async_db)
        result = await repo.get_by_id(99999)
        assert result is None

    async def test_list_canvases(self, async_db: AsyncSession) -> None:
        """Test listing canvases with pagination."""
        repo = CanvasRepository(async_db)

        # Create multiple canvases
        for i in range(5):
            await repo.create_canvas(user_id=f"user_{i}", name=f"Canvas {i}")

        # List with limit
        results = await repo.list(limit=3)
        assert len(results) == 3

        # List with offset
        results = await repo.list(offset=3, limit=10)
        assert len(results) == 2

    async def test_update_canvas_name(self, async_db: AsyncSession) -> None:
        """Test updating canvas name."""
        repo = CanvasRepository(async_db)
        canvas = await repo.create_canvas(user_id="test_user", name="Old Name")

        updated = await repo.update_name(canvas.id, "New Name")
        assert updated is not None
        assert updated.name == "New Name"
        assert updated.id == canvas.id

    async def test_delete_canvas(self, async_db: AsyncSession) -> None:
        """Test deleting a canvas."""
        repo = CanvasRepository(async_db)
        canvas = await repo.create_canvas(user_id="test_user", name="To Delete")

        # Verify exists
        assert await repo.get_by_id(canvas.id) is not None

        # Delete
        result = await repo.delete(canvas.id)
        assert result is True

        # Verify deleted
        assert await repo.get_by_id(canvas.id) is None

    async def test_delete_nonexistent_canvas(self, async_db: AsyncSession) -> None:
        """Test deleting non-existent canvas returns False."""
        repo = CanvasRepository(async_db)
        result = await repo.delete(99999)
        assert result is False

    async def test_get_with_nodes(self, async_db: AsyncSession) -> None:
        """Test getting canvas with nodes preloaded."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")

        # Add nodes
        await node_repo.create_node(
            canvas_id=canvas.id,
            label="Node 1",
            type=NodeType.TEXT,
        )
        await node_repo.create_node(
            canvas_id=canvas.id,
            label="Node 2",
            type=NodeType.DOCUMENT,
        )

        # Get canvas with nodes
        canvas_with_nodes = await canvas_repo.get_with_nodes(canvas.id)
        assert canvas_with_nodes is not None
        assert len(canvas_with_nodes.nodes) == 2
        assert canvas_with_nodes.nodes[0].label == "Node 1"

    async def test_get_by_user(self, async_db: AsyncSession) -> None:
        """Test getting canvases by user ID."""
        repo = CanvasRepository(async_db)

        # Create canvases for different users
        await repo.create_canvas(user_id="user1", name="Canvas 1")
        await repo.create_canvas(user_id="user1", name="Canvas 2")
        await repo.create_canvas(user_id="user2", name="Canvas 3")

        # Get canvases for user1
        user1_canvases = await repo.get_by_user("user1")
        assert len(user1_canvases) == 2

        # Get canvases for user2
        user2_canvases = await repo.get_by_user("user2")
        assert len(user2_canvases) == 1

    async def test_count(self, async_db: AsyncSession) -> None:
        """Test counting canvases."""
        repo = CanvasRepository(async_db)

        initial_count = await repo.count()
        assert initial_count == 0

        await repo.create_canvas(user_id="user1", name="Canvas 1")
        await repo.create_canvas(user_id="user2", name="Canvas 2")

        count = await repo.count()
        assert count == 2


@pytest.mark.asyncio
class TestNodeRepository:
    """Unit tests for NodeRepository CRUD operations."""

    async def test_create_node(self, async_db: AsyncSession) -> None:
        """Test creating a new node."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")

        node = await node_repo.create_node(
            canvas_id=canvas.id,
            label="Test Node",
            type=NodeType.TEXT,
            position={"x": 100, "y": 200, "z": 0},
            node_metadata={"color": "blue"},
        )

        assert node.id is not None
        assert node.canvas_id == canvas.id
        assert node.label == "Test Node"
        assert node.type == NodeType.TEXT
        assert node.get_position() == {"x": 100, "y": 200, "z": 0}
        assert node.get_metadata() == {"color": "blue"}

    async def test_get_by_id(self, async_db: AsyncSession) -> None:
        """Test getting node by ID."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")
        created = await node_repo.create_node(
            canvas_id=canvas.id,
            label="Test Node",
        )

        retrieved = await node_repo.get_by_id(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.label == "Test Node"

    async def test_get_by_canvas(self, async_db: AsyncSession) -> None:
        """Test getting nodes by canvas ID."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)

        canvas1 = await canvas_repo.create_canvas(user_id="user1", name="Canvas 1")
        canvas2 = await canvas_repo.create_canvas(user_id="user1", name="Canvas 2")

        # Add nodes to canvas1
        await node_repo.create_node(canvas_id=canvas1.id, label="Node 1")
        await node_repo.create_node(canvas_id=canvas1.id, label="Node 2")
        # Add node to canvas2
        await node_repo.create_node(canvas_id=canvas2.id, label="Node 3")

        # Get nodes for canvas1
        canvas1_nodes = await node_repo.get_by_canvas(canvas1.id)
        assert len(canvas1_nodes) == 2

        # Get nodes for canvas2
        canvas2_nodes = await node_repo.get_by_canvas(canvas2.id)
        assert len(canvas2_nodes) == 1

    async def test_update_position(self, async_db: AsyncSession) -> None:
        """Test updating node position."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")
        node = await node_repo.create_node(
            canvas_id=canvas.id,
            label="Test Node",
            position={"x": 0, "y": 0, "z": 0},
        )

        updated = await node_repo.update_position(node.id, {"x": 500, "y": 600, "z": 10})
        assert updated is not None
        assert updated.get_position() == {"x": 500, "y": 600, "z": 10}

    async def test_update_metadata(self, async_db: AsyncSession) -> None:
        """Test updating node metadata."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")
        node = await node_repo.create_node(
            canvas_id=canvas.id,
            label="Test Node",
            node_metadata={"color": "blue"},
        )

        updated = await node_repo.update_metadata(
            node.id,
            {"color": "red", "size": "large"},
        )
        assert updated is not None
        assert updated.get_metadata() == {"color": "red", "size": "large"}

    async def test_delete_node(self, async_db: AsyncSession) -> None:
        """Test deleting a node."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")
        node = await node_repo.create_node(
            canvas_id=canvas.id,
            label="To Delete",
        )

        # Delete
        result = await node_repo.delete(node.id)
        assert result is True

        # Verify deleted
        assert await node_repo.get_by_id(node.id) is None


@pytest.mark.asyncio
class TestEdgeRepository:
    """Unit tests for EdgeRepository CRUD operations."""

    async def test_create_edge(self, async_db: AsyncSession) -> None:
        """Test creating a new edge."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)
        edge_repo = EdgeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")
        node1 = await node_repo.create_node(canvas_id=canvas.id, label="Node 1")
        node2 = await node_repo.create_node(canvas_id=canvas.id, label="Node 2")

        edge = await edge_repo.create_edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.DEPENDS_ON,
        )

        assert edge.id is not None
        assert edge.canvas_id == canvas.id
        assert edge.from_node_id == node1.id
        assert edge.to_node_id == node2.id
        assert edge.relation_type == RelationType.DEPENDS_ON

    async def test_get_by_id(self, async_db: AsyncSession) -> None:
        """Test getting edge by ID."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)
        edge_repo = EdgeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")
        node1 = await node_repo.create_node(canvas_id=canvas.id, label="Node 1")
        node2 = await node_repo.create_node(canvas_id=canvas.id, label="Node 2")
        created = await edge_repo.create_edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.DEPENDS_ON,
        )

        retrieved = await edge_repo.get_by_id(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.relation_type == RelationType.DEPENDS_ON

    async def test_get_by_canvas(self, async_db: AsyncSession) -> None:
        """Test getting edges by canvas ID."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)
        edge_repo = EdgeRepository(async_db)

        canvas1 = await canvas_repo.create_canvas(user_id="user1", name="Canvas 1")
        canvas2 = await canvas_repo.create_canvas(user_id="user1", name="Canvas 2")

        # Create nodes and edges for canvas1
        n1 = await node_repo.create_node(canvas_id=canvas1.id, label="N1")
        n2 = await node_repo.create_node(canvas_id=canvas1.id, label="N2")
        await edge_repo.create_edge(
            canvas_id=canvas1.id,
            from_node_id=n1.id,
            to_node_id=n2.id,
            relation_type=RelationType.DEPENDS_ON,
        )

        # Create node and edge for canvas2
        n3 = await node_repo.create_node(canvas_id=canvas2.id, label="N3")
        n4 = await node_repo.create_node(canvas_id=canvas2.id, label="N4")
        await edge_repo.create_edge(
            canvas_id=canvas2.id,
            from_node_id=n3.id,
            to_node_id=n4.id,
            relation_type=RelationType.REFERENCES,
        )

        # Get edges for canvas1
        canvas1_edges = await edge_repo.get_by_canvas(canvas1.id)
        assert len(canvas1_edges) == 1
        assert canvas1_edges[0].relation_type == RelationType.DEPENDS_ON

        # Get edges for canvas2
        canvas2_edges = await edge_repo.get_by_canvas(canvas2.id)
        assert len(canvas2_edges) == 1
        assert canvas2_edges[0].relation_type == RelationType.REFERENCES

    async def test_get_by_node(self, async_db: AsyncSession) -> None:
        """Test getting edges connected to a node."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)
        edge_repo = EdgeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")
        node1 = await node_repo.create_node(canvas_id=canvas.id, label="Node 1")
        node2 = await node_repo.create_node(canvas_id=canvas.id, label="Node 2")
        node3 = await node_repo.create_node(canvas_id=canvas.id, label="Node 3")

        # Create edges: node1 -> node2, node1 -> node3, node2 -> node3
        await edge_repo.create_edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.DEPENDS_ON,
        )
        await edge_repo.create_edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node3.id,
            relation_type=RelationType.REFERENCES,
        )
        await edge_repo.create_edge(
            canvas_id=canvas.id,
            from_node_id=node2.id,
            to_node_id=node3.id,
            relation_type=RelationType.SUPPORTS,
        )

        # Get outgoing edges from node1
        outgoing = await edge_repo.get_by_node(node1.id, as_source=True, as_target=False)
        assert len(outgoing) == 2

        # Get incoming edges to node3
        incoming = await edge_repo.get_by_node(node3.id, as_source=False, as_target=True)
        assert len(incoming) == 2

        # Get all edges connected to node1
        all_edges = await edge_repo.get_by_node(node1.id, as_source=True, as_target=True)
        assert len(all_edges) == 2

    async def test_update_relation_type(self, async_db: AsyncSession) -> None:
        """Test updating edge relation type."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)
        edge_repo = EdgeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")
        node1 = await node_repo.create_node(canvas_id=canvas.id, label="Node 1")
        node2 = await node_repo.create_node(canvas_id=canvas.id, label="Node 2")
        edge = await edge_repo.create_edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.DEPENDS_ON,
        )

        updated = await edge_repo.update_relation_type(edge.id, RelationType.CONFLICTS)
        assert updated is not None
        assert updated.relation_type == RelationType.CONFLICTS

    async def test_delete_edge(self, async_db: AsyncSession) -> None:
        """Test deleting an edge."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)
        edge_repo = EdgeRepository(async_db)

        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test")
        node1 = await node_repo.create_node(canvas_id=canvas.id, label="Node 1")
        node2 = await node_repo.create_node(canvas_id=canvas.id, label="Node 2")
        edge = await edge_repo.create_edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.DEPENDS_ON,
        )

        # Delete
        result = await edge_repo.delete(edge.id)
        assert result is True

        # Verify deleted
        assert await edge_repo.get_by_id(edge.id) is None


@pytest.mark.asyncio
class TestIntegrationFullGraph:
    """Integration test: Create canvas -> add nodes -> link with edges -> retrieve full graph."""

    async def test_full_graph_retrieval(self, async_db: AsyncSession) -> None:
        """Integration test for full graph retrieval."""
        canvas_repo = CanvasRepository(async_db)
        node_repo = NodeRepository(async_db)
        edge_repo = EdgeRepository(async_db)

        # 1. Create canvas
        canvas = await canvas_repo.create_canvas(user_id="test_user", name="Test Canvas")
        assert canvas.id is not None

        # 2. Add nodes
        node1 = await node_repo.create_node(
            canvas_id=canvas.id,
            label="Task A",
            type=NodeType.TEXT,
            position={"x": 100, "y": 100, "z": 0},
        )
        node2 = await node_repo.create_node(
            canvas_id=canvas.id,
            label="Task B",
            type=NodeType.DOCUMENT,
            position={"x": 300, "y": 100, "z": 0},
        )
        node3 = await node_repo.create_node(
            canvas_id=canvas.id,
            label="Task C",
            type=NodeType.GRAPH,
            position={"x": 200, "y": 300, "z": 0},
        )

        # 3. Link with edges
        edge1 = await edge_repo.create_edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            relation_type=RelationType.DEPENDS_ON,
        )
        await edge_repo.create_edge(
            canvas_id=canvas.id,
            from_node_id=node2.id,
            to_node_id=node3.id,
            relation_type=RelationType.DEPENDS_ON,
        )
        await edge_repo.create_edge(
            canvas_id=canvas.id,
            from_node_id=node1.id,
            to_node_id=node3.id,
            relation_type=RelationType.REFERENCES,
        )

        # 4. Retrieve full graph
        full_canvas = await canvas_repo.get_with_graph(canvas.id)
        assert full_canvas is not None
        assert full_canvas.id == canvas.id
        assert len(full_canvas.nodes) == 3
        assert len(full_canvas.edges) == 3

        # Verify node labels
        node_labels = {n.label for n in full_canvas.nodes}
        assert node_labels == {"Task A", "Task B", "Task C"}

        # Verify edges
        edge_types = {e.relation_type for e in full_canvas.edges}
        assert edge_types == {RelationType.DEPENDS_ON, RelationType.REFERENCES}

        # 5. Get node with edges
        node_with_edges = await node_repo.get_with_edges(node2.id)
        assert node_with_edges is not None
        assert node_with_edges.label == "Task B"
        # node2 has one incoming (from node1) and one outgoing (to node3)
        assert len(node_with_edges.incoming_edges) == 1
        assert len(node_with_edges.outgoing_edges) == 1
        assert node_with_edges.incoming_edges[0].from_node_id == node1.id
        assert node_with_edges.outgoing_edges[0].to_node_id == node3.id

        # 6. Get edge with nodes
        edge_with_nodes = await edge_repo.get_with_nodes(edge1.id)
        assert edge_with_nodes is not None
        assert edge_with_nodes.relation_type == RelationType.DEPENDS_ON
        assert edge_with_nodes.from_node.label == "Task A"
        assert edge_with_nodes.to_node.label == "Task B"
