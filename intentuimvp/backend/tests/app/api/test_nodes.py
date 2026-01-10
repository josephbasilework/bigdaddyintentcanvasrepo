"""Integration tests for node API endpoints."""

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
import app.models.node  # noqa: F401 - Side-effect import to register models
from app.api.nodes import router as nodes_router
from app.database import Base, get_async_db
from app.models.canvas import Canvas


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
    """Create async engine for node API tests."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_file}")
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def sync_session_local(sync_engine):
    """Create sync session factory for test setup."""
    return sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


@pytest.fixture
def async_session_maker(async_engine):
    """Create async session factory for node endpoints."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
def nodes_app(async_session_maker) -> FastAPI:
    """Create a test FastAPI app with nodes router."""
    app = FastAPI()
    app.include_router(nodes_router)

    async def override_get_async_db():
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_async_db] = override_get_async_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(nodes_app: FastAPI) -> testclient.TestClient:
    """Create test client for node endpoints."""
    return testclient.TestClient(nodes_app)


def create_canvas(sync_session_local, name: str = "Test Canvas") -> int:
    """Create a canvas and return its ID."""
    with sync_session_local() as session:
        canvas = Canvas(user_id="default_user", name=name)
        session.add(canvas)
        session.commit()
        session.refresh(canvas)
        return canvas.id


class TestNodeEndpoints:
    """Test suite for node API endpoints."""

    def test_create_and_get_node(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test creating a node and retrieving it by ID."""
        canvas_id = create_canvas(sync_session_local)
        payload = {
            "canvas_id": canvas_id,
            "label": "Test Node",
            "type": "text",
            "position": {"x": 10, "y": 20, "z": 1},
            "metadata": {"color": "blue"},
        }
        response = client.post("/api/nodes", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["canvas_id"] == canvas_id
        assert data["label"] == "Test Node"
        assert data["type"] == "text"
        assert data["position"] == {"x": 10, "y": 20, "z": 1}
        assert data["metadata"] == {"color": "blue"}
        assert "created_at" in data

        node_id = data["id"]
        get_response = client.get(f"/api/nodes/{node_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["id"] == node_id
        assert get_data["canvas_id"] == canvas_id

    def test_update_node_partial_position(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test updating node fields with partial position data."""
        canvas_id = create_canvas(sync_session_local)
        create_payload = {
            "canvas_id": canvas_id,
            "label": "Original",
            "type": "text",
            "position": {"x": 5, "y": 6, "z": 7},
        }
        create_response = client.post("/api/nodes", json=create_payload)
        assert create_response.status_code == 201
        node_id = create_response.json()["id"]

        update_payload = {
            "label": "Updated",
            "position": {"x": 99},
            "metadata": {"status": "active"},
        }
        update_response = client.put(f"/api/nodes/{node_id}", json=update_payload)
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["label"] == "Updated"
        assert updated["position"]["x"] == 99
        assert updated["position"]["y"] == 6
        assert updated["position"]["z"] == 7
        assert updated["metadata"] == {"status": "active"}

    def test_update_node_empty_payload(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test updating a node with no fields returns 400."""
        canvas_id = create_canvas(sync_session_local)
        response = client.post(
            "/api/nodes",
            json={"canvas_id": canvas_id, "label": "Node"},
        )
        node_id = response.json()["id"]

        update_response = client.put(f"/api/nodes/{node_id}", json={})
        assert update_response.status_code == 400

    def test_list_and_delete_nodes(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test listing nodes by canvas and deleting a node."""
        canvas_id = create_canvas(sync_session_local, name="Canvas A")
        other_canvas_id = create_canvas(sync_session_local, name="Canvas B")

        for label in ["Node A", "Node B"]:
            response = client.post(
                "/api/nodes",
                json={"canvas_id": canvas_id, "label": label},
            )
            assert response.status_code == 201

        response = client.post(
            "/api/nodes",
            json={"canvas_id": other_canvas_id, "label": "Other"},
        )
        assert response.status_code == 201

        list_response = client.get(f"/api/nodes?canvas_id={canvas_id}")
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data["count"] == 2
        assert all(node["canvas_id"] == canvas_id for node in list_data["nodes"])

        node_id = list_data["nodes"][0]["id"]
        delete_response = client.delete(f"/api/nodes/{node_id}")
        assert delete_response.status_code == 204

        get_response = client.get(f"/api/nodes/{node_id}")
        assert get_response.status_code == 404
