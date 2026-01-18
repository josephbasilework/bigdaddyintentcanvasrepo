"""Integration tests for canvas action logging endpoint."""

import tempfile

import pytest
from fastapi import FastAPI, testclient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models.canvas  # noqa: F401 - register models
import app.models.event  # noqa: F401 - register models
import app.models.node  # noqa: F401 - register models
import app.models.session  # noqa: F401 - register models
import app.models.turn  # noqa: F401 - register models
from app.api.canvas_actions import router as canvas_actions_router
from app.database import Base, get_db
from app.models.canvas import Canvas
from app.models.event import Event
from app.models.node import Node, NodeType
from app.models.turn import Turn


@pytest.fixture
def test_db_file():
    """Create temporary file for test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name


@pytest.fixture
def test_engine(test_db_file):
    """Create test database engine."""
    engine = create_engine(
        f"sqlite:///{test_db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def canvas_actions_app(test_engine):
    """Create a test FastAPI app with canvas actions router."""
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(canvas_actions_router)
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(canvas_actions_app) -> testclient.TestClient:
    """Create test client for canvas action endpoints."""
    return testclient.TestClient(canvas_actions_app)


def _seed_canvas_with_node(test_engine) -> tuple[int, int]:
    session_local = sessionmaker(bind=test_engine)
    db = session_local()
    try:
        canvas = Canvas(user_id="default_user", name="Canvas")
        db.add(canvas)
        db.commit()
        db.refresh(canvas)

        node = Node(
            canvas_id=canvas.id,
            type=NodeType.TEXT,
            label="Seed Node",
            position='{"x": 0, "y": 0, "z": 0}',
        )
        db.add(node)
        db.commit()
        db.refresh(node)
        return canvas.id, node.id
    finally:
        db.close()


def test_canvas_action_creates_turns_and_events(
    client: testclient.TestClient,
    test_engine,
) -> None:
    """Canvas actions should log turns and events with origin references."""
    canvas_id, node_id = _seed_canvas_with_node(test_engine)
    session_id = "session-123"

    create_payload = {
        "action": "node_created",
        "workspace_id": canvas_id,
        "session_id": session_id,
        "payload": {"node": {"id": node_id, "title": "Seed Node", "x": 0, "y": 0}},
    }
    response = client.post("/api/canvas/actions", json=create_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "logged"
    assert data["sessionId"] == session_id
    assert isinstance(data.get("sequenceNumber"), int)
    created_turn_id = data["turnId"]

    update_payload = {
        "action": "node_updated",
        "workspace_id": canvas_id,
        "session_id": session_id,
        "payload": {
            "node": {"id": node_id, "title": "Seed Node", "x": 10, "y": 20},
            "updates": {"position": {"x": 10, "y": 20}},
        },
    }
    response = client.post("/api/canvas/actions", json=update_payload)
    assert response.status_code == 201
    updated_turn_id = response.json()["turnId"]

    session_local = sessionmaker(bind=test_engine)
    db = session_local()
    try:
        created_turn = db.query(Turn).filter(Turn.id == created_turn_id).one()
        updated_turn = db.query(Turn).filter(Turn.id == updated_turn_id).one()
        assert created_turn.type == "node_created"
        assert updated_turn.type == "node_updated"
        assert updated_turn.origin_sequence_number == created_turn.sequence_number
        assert updated_turn.related_node_id == node_id

        events = (
            db.query(Event)
            .filter(Event.related_turn_id.in_([created_turn_id, updated_turn_id]))
            .all()
        )
        event_types = {event.event_type for event in events}
        assert "node.created" in event_types
        assert "node.updated" in event_types
    finally:
        db.close()


def test_canvas_action_idempotent_client_request_id(
    client: testclient.TestClient,
    test_engine,
) -> None:
    """Canvas actions should de-dupe when client_request_id is reused."""
    canvas_id, node_id = _seed_canvas_with_node(test_engine)
    session_id = "session-xyz"

    payload = {
        "action": "node_created",
        "workspace_id": canvas_id,
        "session_id": session_id,
        "client_request_id": "req-123",
        "payload": {"node": {"id": node_id, "title": "Seed Node", "x": 0, "y": 0}},
    }

    response = client.post("/api/canvas/actions", json=payload)
    assert response.status_code == 201
    first_turn_id = response.json()["turnId"]

    response = client.post("/api/canvas/actions", json=payload)
    assert response.status_code == 201
    second_turn_id = response.json()["turnId"]

    assert first_turn_id == second_turn_id

    session_local = sessionmaker(bind=test_engine)
    db = session_local()
    try:
        turns = db.query(Turn).filter(Turn.session_id == session_id).all()
        assert len(turns) == 1
    finally:
        db.close()
