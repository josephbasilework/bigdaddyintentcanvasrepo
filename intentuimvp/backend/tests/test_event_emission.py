"""Tests for unified event emission."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.canvas import Canvas
from app.models.event import Event
from app.models.node import Node, NodeType
from app.models.turn import TurnActor, TurnType
from app.services.events import resolve_event_type
from app.services.turns import log_turn_with_session_id_sync


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
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


@pytest.fixture
def test_canvas(db_session: Session) -> Canvas:
    """Create a test canvas."""
    canvas = Canvas(user_id="test-user", name="Test Canvas")
    db_session.add(canvas)
    db_session.commit()
    db_session.refresh(canvas)
    return canvas


@pytest.fixture
def test_node(db_session: Session, test_canvas: Canvas) -> Node:
    """Create a test node."""
    node = Node(
        canvas_id=test_canvas.id,
        type=NodeType.TEXT,
        label="Test Node",
        position='{"x": 0, "y": 0, "z": 0}',
    )
    db_session.add(node)
    db_session.commit()
    db_session.refresh(node)
    return node


class _DummyStore:
    def persist_turn(self, **_: object) -> None:
        return None


def test_log_turn_emits_event(
    db_session: Session, test_node: Node, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Logging a turn should emit a corresponding event."""
    monkeypatch.setattr(
        "app.services.turns.get_user_data_store", lambda: _DummyStore()
    )

    turn = log_turn_with_session_id_sync(
        db_session,
        session_id="session-1",
        actor=TurnActor.USER,
        turn_type=TurnType.NODE_CREATED,
        summary="Node created",
        payload={"nodeId": test_node.id},
        related_node_id=test_node.id,
    )

    assert turn is not None

    event = (
        db_session.query(Event)
        .filter(Event.related_turn_id == turn.id)
        .one()
    )
    assert event.event_type == "node.created"
    assert event.actor == "user"
    assert event.related_node_id == test_node.id
    assert event.get_payload()["nodeId"] == test_node.id


def test_resolve_event_type_uses_response_type() -> None:
    """Agent responses should map to response.* event types."""
    event_type = resolve_event_type(
        TurnType.AGENT_RESPONSE,
        TurnActor.AGENT,
        {"response_type": "clarification"},
    )
    assert event_type == "response.clarification"


def test_resolve_event_type_prefers_explicit_mapping() -> None:
    """Explicit mapping should override response-derived types."""
    event_type = resolve_event_type(
        TurnType.EXTERNAL_STATE_CHANGE,
        TurnActor.SYSTEM,
        {"response_type": "acknowledgment"},
    )
    assert event_type == "external.updated"
