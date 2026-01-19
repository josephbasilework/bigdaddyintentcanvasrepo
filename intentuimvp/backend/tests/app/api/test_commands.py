"""Tests for command submission API endpoint."""

import uuid

import pytest
from fastapi import FastAPI, testclient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.canvas  # noqa: F401
import app.models.session  # noqa: F401
import app.models.turn  # noqa: F401
from app.api.commands import CommandSubmission, SelectionScope, _route_command_submission
from app.api.commands import router as commands_router
from app.context.models import ContextPayload, RoutingDecision
from app.database import Base, get_db


@pytest.fixture
def commands_app() -> FastAPI:
    """Create a test FastAPI app with DB override."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(commands_router)
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(commands_app: FastAPI) -> testclient.TestClient:
    """Create a test client for the commands endpoint."""
    return testclient.TestClient(commands_app)


def test_submit_command_returns_correlation_id_and_enqueues_routing(
    monkeypatch,
    client: testclient.TestClient,
) -> None:
    """Submitting a command returns a correlation ID and enqueues routing."""
    captured: dict[str, CommandSubmission] = {}

    def fake_enqueue(submission: CommandSubmission) -> None:
        captured["submission"] = submission

    monkeypatch.setattr("app.api.commands.enqueue_command", fake_enqueue)

    payload = {
        "command": "/research AI trends",
        "attachments": ["file-1"],
        "selection": {
            "selected_nodes": ["node-1"],
            "selected_edges": ["edge-1"],
        },
    }
    response = client.post("/api/commands", json=payload)

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    uuid.UUID(data["correlation_id"])

    submission = captured["submission"]
    assert submission.command == payload["command"]
    assert submission.attachments == payload["attachments"]
    assert submission.selection is not None
    assert submission.selection == SelectionScope(
        selected_nodes=["node-1"],
        selected_edges=["edge-1"],
    )


def test_submit_command_skip_routing_logs_only(
    monkeypatch,
    client: testclient.TestClient,
) -> None:
    """Submitting with skip_routing logs a turn without enqueuing routing."""
    calls = {"count": 0}

    def fake_enqueue(submission: CommandSubmission) -> None:
        calls["count"] += 1

    monkeypatch.setattr("app.api.commands.enqueue_command", fake_enqueue)

    response = client.post(
        "/api/commands",
        json={"command": "show chat", "skip_routing": True, "command_key": "show_chat"},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "logged"
    assert calls["count"] == 0


def test_submit_command_missing_command_returns_400(
    client: testclient.TestClient,
) -> None:
    """Submitting without a command returns a validation error."""
    response = client.post("/api/commands", json={"attachments": []})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_route_command_submission_passes_selection(monkeypatch) -> None:
    """Routing a command submission forwards selection scope into the payload."""
    captured: dict[str, ContextPayload] = {}

    class FakeRouter:
        async def route(
            self,
            payload: ContextPayload,
            *,
            user_id: str | None = None,
            session_id: str | None = None,
        ) -> RoutingDecision:
            captured["payload"] = payload
            captured["session_id"] = session_id
            return RoutingDecision(
                handler="help_handler",
                confidence=1.0,
                payload=payload,
                reason="ok",
            )

    monkeypatch.setattr("app.api.commands.get_input_router", lambda: FakeRouter())

    submission = CommandSubmission(
        correlation_id="test",
        command="/help",
        attachments=[],
        selection=SelectionScope(
            selected_nodes=["node-1"],
            selected_edges=["edge-1"],
        ),
        session_id="session-123",
    )

    await _route_command_submission(submission)

    payload = captured["payload"]
    assert payload.selection is not None
    assert payload.selection.selected_nodes == ["node-1"]
    assert payload.selection.selected_edges == ["edge-1"]
    assert captured["session_id"] == "session-123"
