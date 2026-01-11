"""Integration tests for edge API endpoints."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI, testclient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models to register them with Base
import app.models.canvas  # noqa: F401 - Side-effect import to register models
import app.models.edge  # noqa: F401 - Side-effect import to register models
import app.models.node  # noqa: F401 - Side-effect import to register models
from app.api.edges import router as edges_router
from app.database import Base, get_async_db
from app.models.canvas import Canvas
from app.models.node import Node, NodeType


@pytest.fixture
def test_db_file():
    """Create temporary file for test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sync_engine(test_db_file: str):
    """Create sync engine for test database setup."""
    engine = create_engine(
        f"sqlite:///{test_db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def async_engine(test_db_file: str):
    """Create async engine for edge API tests."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_file}")
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def sync_session_local(sync_engine):
    """Create sync session factory for test setup."""
    return sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


@pytest.fixture
def async_session_maker(async_engine):
    """Create async session factory for edge endpoints."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
def edges_app(async_session_maker) -> FastAPI:
    """Create a test FastAPI app with edges router."""
    app = FastAPI()
    app.include_router(edges_router)

    async def override_get_async_db():
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_async_db] = override_get_async_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(edges_app: FastAPI) -> testclient.TestClient:
    """Create test client for edge endpoints."""
    return testclient.TestClient(edges_app)


def create_canvas(sync_session_local, name: str = "Test Canvas") -> int:
    """Create a canvas and return its ID."""
    with sync_session_local() as session:
        canvas = Canvas(user_id="default_user", name=name)
        session.add(canvas)
        session.commit()
        session.refresh(canvas)
        return canvas.id


def create_canvas_with_nodes(
    sync_session_local,
    name: str = "Test Canvas",
    node_count: int = 2,
) -> tuple[int, list[int]]:
    """Create a canvas with nodes and return IDs."""
    with sync_session_local() as session:
        canvas = Canvas(user_id="default_user", name=name)
        session.add(canvas)
        session.commit()
        session.refresh(canvas)

        nodes: list[Node] = []
        for index in range(node_count):
            node = Node(
                canvas_id=canvas.id,
                type=NodeType.TEXT,
                label=f"Node {index + 1}",
                position='{"x": 0, "y": 0, "z": 0}',
            )
            session.add(node)
            nodes.append(node)

        session.commit()
        for node in nodes:
            session.refresh(node)

        return canvas.id, [node.id for node in nodes]


class TestEdgeEndpoints:
    """Test suite for edge API endpoints."""

    def test_create_and_get_edge(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test creating an edge and retrieving it by ID."""
        canvas_id, node_ids = create_canvas_with_nodes(sync_session_local)
        payload = {
            "canvas_id": canvas_id,
            "from_node_id": node_ids[0],
            "to_node_id": node_ids[1],
            "relation_type": "depends_on",
        }
        response = client.post("/api/edges", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["canvas_id"] == canvas_id
        assert data["from_node_id"] == node_ids[0]
        assert data["to_node_id"] == node_ids[1]
        assert data["relation_type"] == "depends_on"
        assert "created_at" in data

        edge_id = data["id"]
        get_response = client.get(f"/api/edges/{edge_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["id"] == edge_id
        assert get_data["canvas_id"] == canvas_id

    def test_update_edge_relation_type(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test updating edge relation type."""
        canvas_id, node_ids = create_canvas_with_nodes(sync_session_local)
        create_response = client.post(
            "/api/edges",
            json={
                "canvas_id": canvas_id,
                "from_node_id": node_ids[0],
                "to_node_id": node_ids[1],
                "relation_type": "supports",
            },
        )
        assert create_response.status_code == 201
        edge_id = create_response.json()["id"]

        empty_update = client.put(f"/api/edges/{edge_id}", json={})
        assert empty_update.status_code == 400

        update_response = client.put(
            f"/api/edges/{edge_id}",
            json={"relation_type": "conflicts"},
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["relation_type"] == "conflicts"

    def test_list_and_delete_edges(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test listing edges with filters and deleting an edge."""
        canvas_id, node_ids = create_canvas_with_nodes(sync_session_local, node_count=3)
        other_canvas_id, other_node_ids = create_canvas_with_nodes(
            sync_session_local,
            name="Other Canvas",
        )

        edge_a = client.post(
            "/api/edges",
            json={
                "canvas_id": canvas_id,
                "from_node_id": node_ids[0],
                "to_node_id": node_ids[1],
                "relation_type": "depends_on",
            },
        )
        assert edge_a.status_code == 201

        edge_b = client.post(
            "/api/edges",
            json={
                "canvas_id": canvas_id,
                "from_node_id": node_ids[1],
                "to_node_id": node_ids[2],
                "relation_type": "references",
            },
        )
        assert edge_b.status_code == 201

        other_edge = client.post(
            "/api/edges",
            json={
                "canvas_id": other_canvas_id,
                "from_node_id": other_node_ids[0],
                "to_node_id": other_node_ids[1],
                "relation_type": "supports",
            },
        )
        assert other_edge.status_code == 201

        list_response = client.get(f"/api/edges?canvas_id={canvas_id}")
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data["count"] == 2
        assert all(edge["canvas_id"] == canvas_id for edge in list_data["edges"])

        outgoing = client.get(
            f"/api/edges?node_id={node_ids[1]}&as_source=true&as_target=false"
        )
        assert outgoing.status_code == 200
        outgoing_data = outgoing.json()
        assert outgoing_data["count"] == 1
        assert outgoing_data["edges"][0]["from_node_id"] == node_ids[1]

        incoming = client.get(
            f"/api/edges?node_id={node_ids[1]}&as_source=false&as_target=true"
        )
        assert incoming.status_code == 200
        incoming_data = incoming.json()
        assert incoming_data["count"] == 1
        assert incoming_data["edges"][0]["to_node_id"] == node_ids[1]

        edge_id = list_data["edges"][0]["id"]
        delete_response = client.delete(f"/api/edges/{edge_id}")
        assert delete_response.status_code == 204

        get_response = client.get(f"/api/edges/{edge_id}")
        assert get_response.status_code == 404

    def test_create_edge_canvas_mismatch(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test creating an edge with nodes outside the canvas fails."""
        canvas_id, node_ids = create_canvas_with_nodes(sync_session_local)
        other_canvas_id = create_canvas(sync_session_local, name="Other Canvas")

        response = client.post(
            "/api/edges",
            json={
                "canvas_id": other_canvas_id,
                "from_node_id": node_ids[0],
                "to_node_id": node_ids[1],
                "relation_type": "supports",
            },
        )
        assert response.status_code == 400
