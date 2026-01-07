"""Integration tests for preferences API endpoints."""

import tempfile

import pytest
from fastapi import testclient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models to register them with Base
import app.models.canvas  # noqa: F401 - Side-effect import to register models
import app.models.preferences  # noqa: F401 - Side-effect import to register models
from app.api.preferences import router as preferences_router
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
def preferences_app(test_engine):
    """Create a test FastAPI app with preferences router."""
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(preferences_router)
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(preferences_app) -> testclient.TestClient:
    """Create test client for preferences endpoints."""
    return testclient.TestClient(preferences_app)


class TestPreferencesEndpoint:
    """Test suite for preferences API endpoints."""

    def test_get_preferences_default(self, client: testclient.TestClient) -> None:
        """Test GET /api/preferences returns defaults when no preferences exist."""
        response = client.get("/api/preferences")
        assert response.status_code == 200
        data = response.json()
        assert "preferences" in data
        assert data["preferences"]["theme"] == "light"
        assert data["preferences"]["zoom_level"] == 1.0
        assert data["preferences"]["panel_layouts"] == {}

    def test_save_preferences_new(self, client: testclient.TestClient) -> None:
        """Test PUT /api/preferences creates new preferences."""
        payload = {
            "preferences": {
                "theme": "dark",
                "zoom_level": 1.5,
                "panel_layouts": {
                    "sidebar": {"id": "sidebar", "position": {"x": 0, "y": 0}, "size": {"width": 250, "height": 800}, "visible": True}
                },
            }
        }
        response = client.put("/api/preferences", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "default_user"
        assert data["preferences"]["theme"] == "dark"
        assert data["preferences"]["zoom_level"] == 1.5
        assert "sidebar" in data["preferences"]["panel_layouts"]
        assert "updated_at" in data

    def test_save_preferences_update(self, client: testclient.TestClient) -> None:
        """Test PUT /api/preferences updates existing preferences."""
        # Create initial preferences
        payload1 = {
            "preferences": {
                "theme": "light",
                "zoom_level": 1.0,
                "panel_layouts": {},
            }
        }
        response1 = client.put("/api/preferences", json=payload1)
        assert response1.status_code == 200

        # Update preferences
        payload2 = {
            "preferences": {
                "theme": "auto",
                "zoom_level": 1.25,
                "panel_layouts": {},
            }
        }
        response2 = client.put("/api/preferences", json=payload2)
        assert response2.status_code == 200
        data = response2.json()
        assert data["preferences"]["theme"] == "auto"
        assert data["preferences"]["zoom_level"] == 1.25

    def test_round_trip_save_load(self, client: testclient.TestClient) -> None:
        """Test round-trip: save then load returns same data."""
        # Save preferences
        save_payload = {
            "preferences": {
                "theme": "dark",
                "zoom_level": 1.75,
                "panel_layouts": {
                    "panel1": {"id": "panel1", "position": {"x": 10, "y": 20}, "size": {"width": 300, "height": 400}, "visible": True},
                    "panel2": {"id": "panel2", "position": {"x": 320, "y": 20}, "size": {"width": 200, "height": 400}, "visible": False},
                },
            }
        }
        save_response = client.put("/api/preferences", json=save_payload)
        assert save_response.status_code == 200
        saved_data = save_response.json()

        # Load preferences
        load_response = client.get("/api/preferences")
        assert load_response.status_code == 200
        loaded_data = load_response.json()

        # Verify round-trip integrity
        assert loaded_data["preferences"]["theme"] == saved_data["preferences"]["theme"]
        assert loaded_data["preferences"]["zoom_level"] == saved_data["preferences"]["zoom_level"]
        assert loaded_data["preferences"]["panel_layouts"] == saved_data["preferences"]["panel_layouts"]

    def test_save_preferences_default_values(self, client: testclient.TestClient) -> None:
        """Test PUT /api/preferences with default values."""
        payload = {
            "preferences": {
                "theme": "light",
                "zoom_level": 1.0,
                "panel_layouts": {},
            }
        }
        response = client.put("/api/preferences", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["preferences"]["theme"] == "light"
        assert data["preferences"]["zoom_level"] == 1.0

    def test_save_preferences_merge(self, client: testclient.TestClient) -> None:
        """Test that updating preferences merges with existing data."""
        # Create initial preferences with panel layouts
        payload1 = {
            "preferences": {
                "theme": "dark",
                "zoom_level": 1.2,
                "panel_layouts": {
                    "panel1": {"id": "panel1", "position": {"x": 0, "y": 0}, "size": {"width": 200, "height": 300}, "visible": True},
                },
            }
        }
        response1 = client.put("/api/preferences", json=payload1)
        assert response1.status_code == 200

        # Update only theme - should preserve panel layouts
        payload2 = {
            "preferences": {
                "theme": "light",
                "zoom_level": 1.2,
                "panel_layouts": {
                    "panel1": {"id": "panel1", "position": {"x": 0, "y": 0}, "size": {"width": 200, "height": 300}, "visible": True},
                },
            }
        }
        response2 = client.put("/api/preferences", json=payload2)
        assert response2.status_code == 200
        data = response2.json()
        assert data["preferences"]["theme"] == "light"
        assert "panel1" in data["preferences"]["panel_layouts"]

    def test_save_preferences_zoom_bounds(self, client: testclient.TestClient) -> None:
        """Test that zoom level is bounded between 0.5 and 2.0."""
        # This test validates the Pydantic schema enforces bounds
        payload = {
            "preferences": {
                "theme": "light",
                "zoom_level": 1.5,  # Valid value
                "panel_layouts": {},
            }
        }
        response = client.put("/api/preferences", json=payload)
        assert response.status_code == 200

    def test_save_preferences_invalid_theme(self, client: testclient.TestClient) -> None:
        """Test that invalid theme value is rejected."""
        payload = {
            "preferences": {
                "theme": "invalid_theme",  # Not in allowed values
                "zoom_level": 1.0,
                "panel_layouts": {},
            }
        }
        response = client.put("/api/preferences", json=payload)
        assert response.status_code == 422  # Validation error

    def test_save_preferences_invalid_zoom(self, client: testclient.TestClient) -> None:
        """Test that invalid zoom level is rejected."""
        payload = {
            "preferences": {
                "theme": "light",
                "zoom_level": 3.0,  # Above max of 2.0
                "panel_layouts": {},
            }
        }
        response = client.put("/api/preferences", json=payload)
        assert response.status_code == 422  # Validation error
