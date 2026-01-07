"""Integration tests for workspace API endpoints."""

import tempfile

import pytest
from fastapi import testclient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models to register them with Base
import app.models.canvas  # noqa: F401 - Side-effect import to register models
from app.api.workspace import router as workspace_router
from app.database import Base, get_db


@pytest.fixture
def test_db_file():
    """Create temporary file for test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name


@pytest.fixture
def test_engine(test_db_file):
    """Create test database engine."""
    test_database_url = f"sqlite:///{test_db_file}"
    engine = create_engine(
        test_database_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine


@pytest.fixture
def workspace_app(test_engine):
    """Create a test FastAPI app with workspace router."""
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(workspace_router)
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(workspace_app) -> testclient.TestClient:
    """Create test client for workspace endpoints."""
    return testclient.TestClient(workspace_app)


class TestWorkspaceEndpoint:
    """Test suite for workspace API endpoints."""

    def test_get_workspace_empty(self, client: testclient.TestClient) -> None:
        """Test GET /api/workspace returns empty state when no canvas exists."""
        response = client.get("/api/workspace")
        assert response.status_code == 200
        data = response.json()
        assert data["nodes"] == []
        assert data["name"] == "default"

    def test_save_workspace_new(self, client: testclient.TestClient) -> None:
        """Test PUT /api/workspace creates new canvas."""
        payload = {
            "nodes": [
                {"label": "Node 1", "x": 100, "y": 200, "z": 0},
                {"label": "Node 2", "x": 300, "y": 400, "z": 0},
            ],
            "name": "test_workspace",
        }
        response = client.put("/api/workspace", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_workspace"
        assert data["user_id"] == "default_user"
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["label"] == "Node 1"
        assert data["nodes"][0]["x"] == 100
        assert data["nodes"][0]["y"] == 200
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_save_workspace_update(self, client: testclient.TestClient) -> None:
        """Test PUT /api/workspace updates existing canvas."""
        # Create initial canvas
        payload1 = {
            "nodes": [{"label": "Original Node", "x": 50, "y": 50, "z": 0}],
            "name": "update_test",
        }
        response1 = client.put("/api/workspace", json=payload1)
        assert response1.status_code == 200
        canvas_id = response1.json()["id"]

        # Update canvas with different nodes
        payload2 = {
            "nodes": [
                {"label": "Updated Node 1", "x": 100, "y": 100, "z": 0},
                {"label": "Updated Node 2", "x": 200, "y": 200, "z": 0},
            ],
            "name": "update_test",
        }
        response2 = client.put("/api/workspace", json=payload2)
        assert response2.status_code == 200
        data = response2.json()
        # Canvas ID should remain the same
        assert data["id"] == canvas_id
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["label"] == "Updated Node 1"

    def test_round_trip_save_load(self, client: testclient.TestClient) -> None:
        """Test round-trip: save then load returns same data."""
        # Save workspace
        save_payload = {
            "nodes": [
                {"label": "Alpha", "x": 10, "y": 20, "z": 5},
                {"label": "Beta", "x": 30, "y": 40, "z": 10},
                {"label": "Gamma", "x": 50, "y": 60, "z": 15},
            ],
            "name": "round_trip_test",
        }
        save_response = client.put("/api/workspace", json=save_payload)
        assert save_response.status_code == 200
        saved_data = save_response.json()

        # Load workspace
        load_response = client.get("/api/workspace")
        assert load_response.status_code == 200
        loaded_data = load_response.json()

        # Verify round-trip integrity
        assert loaded_data["id"] == saved_data["id"]
        assert loaded_data["name"] == saved_data["name"]
        assert len(loaded_data["nodes"]) == len(saved_data["nodes"])

        # Check each node
        for saved_node, loaded_node in zip(saved_data["nodes"], loaded_data["nodes"]):
            assert loaded_node["label"] == saved_node["label"]
            assert loaded_node["x"] == saved_node["x"]
            assert loaded_node["y"] == saved_node["y"]
            assert loaded_node["z"] == saved_node["z"]

    def test_save_workspace_empty_nodes(self, client: testclient.TestClient) -> None:
        """Test PUT /api/workspace with empty node list."""
        payload = {"nodes": [], "name": "empty_test"}
        response = client.put("/api/workspace", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["nodes"] == []

    def test_save_workspace_default_name(self, client: testclient.TestClient) -> None:
        """Test PUT /api/workspace with default name."""
        payload = {"nodes": [{"label": "Test", "x": 0, "y": 0, "z": 0}]}
        response = client.put("/api/workspace", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "default"

    def test_save_workspace_with_negative_coordinates(self, client: testclient.TestClient) -> None:
        """Test PUT /api/workspace with negative coordinates."""
        payload = {
            "nodes": [{"label": "Negative", "x": -100, "y": -200, "z": -50}],
            "name": "negative_test",
        }
        response = client.put("/api/workspace", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["nodes"][0]["x"] == -100
        assert data["nodes"][0]["y"] == -200
        assert data["nodes"][0]["z"] == -50

    def test_save_workspace_replaces_existing_nodes(self, client: testclient.TestClient) -> None:
        """Test that save replaces all existing nodes."""
        # Save with 3 nodes
        payload1 = {
            "nodes": [
                {"label": "A", "x": 0, "y": 0, "z": 0},
                {"label": "B", "x": 1, "y": 1, "z": 0},
                {"label": "C", "x": 2, "y": 2, "z": 0},
            ],
            "name": "replace_test",
        }
        response1 = client.put("/api/workspace", json=payload1)
        assert response1.status_code == 200
        assert len(response1.json()["nodes"]) == 3

        # Save with only 1 node - should replace previous nodes
        payload2 = {
            "nodes": [{"label": "Only Node", "x": 100, "y": 100, "z": 0}],
            "name": "replace_test",
        }
        response2 = client.put("/api/workspace", json=payload2)
        assert response2.status_code == 200
        data = response2.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["label"] == "Only Node"
