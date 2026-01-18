"""Integration tests for dashboard subscription endpoints."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI, testclient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models to register them with Base
import app.models.canvas  # noqa: F401
import app.models.dashboard_subscription  # noqa: F401
import app.models.node  # noqa: F401
from app.api.dashboard_subscriptions import router as dashboard_subscriptions_router
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
    """Create async engine for dashboard subscription tests."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_file}")
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def sync_session_local(sync_engine):
    """Create sync session factory for test setup."""
    return sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


@pytest.fixture
def async_session_maker(async_engine):
    """Create async session factory for dashboard subscription endpoints."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
def subscriptions_app(async_session_maker) -> FastAPI:
    """Create a test FastAPI app with dashboard subscription router."""
    app = FastAPI()
    app.include_router(dashboard_subscriptions_router)

    async def override_get_async_db():
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_async_db] = override_get_async_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(subscriptions_app: FastAPI) -> testclient.TestClient:
    """Create test client for subscription endpoints."""
    return testclient.TestClient(subscriptions_app)


def create_canvas(sync_session_local) -> int:
    """Create a canvas and return its ID."""
    with sync_session_local() as session:
        canvas = Canvas(user_id="default_user", name="Test Canvas")
        session.add(canvas)
        session.commit()
        session.refresh(canvas)
        return canvas.id


def create_dashboard_node(sync_session_local, canvas_id: int) -> int:
    """Create a dashboard node and return its ID."""
    with sync_session_local() as session:
        node = Node(
            canvas_id=canvas_id,
            type=NodeType.DASHBOARD,
            label="Dashboard",
            position='{"x": 0, "y": 0, "z": 0}',
        )
        session.add(node)
        session.commit()
        session.refresh(node)
        return node.id


def test_create_external_subscription(
    client: testclient.TestClient,
    sync_session_local,
) -> None:
    """Creating an external subscription computes source_id and stores config."""
    canvas_id = create_canvas(sync_session_local)
    node_id = create_dashboard_node(sync_session_local, canvas_id)

    payload = {
        "canvas_id": canvas_id,
        "dashboard_node_id": node_id,
        "subscription_target": "external_state",
        "config": {
            "type": "api",
            "endpoint": "https://example.com/metrics?token=secret",
            "pollIntervalMs": 5000,
            "allowWrite": True,
        },
    }

    response = client.post("/api/dashboard/subscriptions", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["canvasId"] == canvas_id
    assert data["dashboardNodeId"] == node_id
    assert data["subscriptionTarget"] == "external_state"
    assert data["config"]["type"] == "api"
    assert data["sourceId"].startswith("https://example.com/metrics")


def test_update_external_subscription(
    client: testclient.TestClient,
    sync_session_local,
) -> None:
    """Updating a subscription stores new config and allows deactivation."""
    canvas_id = create_canvas(sync_session_local)
    node_id = create_dashboard_node(sync_session_local, canvas_id)

    create_payload = {
        "canvas_id": canvas_id,
        "dashboard_node_id": node_id,
        "subscription_target": "external_state",
        "config": {"type": "api", "endpoint": "https://example.com/metrics"},
    }
    create_response = client.post("/api/dashboard/subscriptions", json=create_payload)
    subscription_id = create_response.json()["id"]

    update_payload = {
        "config": {
            "type": "api",
            "endpoint": "https://example.com/metrics",
            "pollIntervalMs": 30000,
        },
        "is_active": False,
    }
    update_response = client.put(
        f"/api/dashboard/subscriptions/{subscription_id}", json=update_payload
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["isActive"] is False
    assert data["config"]["pollIntervalMs"] == 30000


def test_create_subscription_canvas_mismatch(
    client: testclient.TestClient,
    sync_session_local,
) -> None:
    """Creating subscription fails if node is on different canvas."""
    canvas_id = create_canvas(sync_session_local)
    node_id = create_dashboard_node(sync_session_local, canvas_id)
    other_canvas_id = create_canvas(sync_session_local)

    payload = {
        "canvas_id": other_canvas_id,
        "dashboard_node_id": node_id,
        "subscription_target": "external_state",
        "config": {"type": "api", "endpoint": "https://example.com"},
    }
    response = client.post("/api/dashboard/subscriptions", json=payload)
    assert response.status_code == 400
