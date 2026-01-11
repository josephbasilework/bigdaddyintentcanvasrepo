"""Tests for command submission API endpoint."""

import uuid

import pytest
from fastapi import FastAPI, testclient

from app.api.commands import CommandSubmission, SelectionScope, _route_command_submission
from app.api.commands import router as commands_router
from app.context.models import ContextPayload, RoutingDecision


def test_submit_command_returns_correlation_id_and_enqueues_routing(monkeypatch) -> None:
    """Submitting a command returns a correlation ID and enqueues routing."""
    captured: dict[str, CommandSubmission] = {}

    def fake_enqueue(submission: CommandSubmission) -> None:
        captured["submission"] = submission

    monkeypatch.setattr("app.api.commands.enqueue_command", fake_enqueue)

    app = FastAPI()
    app.include_router(commands_router)
    client = testclient.TestClient(app)

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


def test_submit_command_missing_command_returns_400() -> None:
    """Submitting without a command returns a validation error."""
    app = FastAPI()
    app.include_router(commands_router)
    client = testclient.TestClient(app)

    response = client.post("/api/commands", json={"attachments": []})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_route_command_submission_passes_selection(monkeypatch) -> None:
    """Routing a command submission forwards selection scope into the payload."""
    captured: dict[str, ContextPayload] = {}

    class FakeRouter:
        async def route(self, payload: ContextPayload) -> RoutingDecision:
            captured["payload"] = payload
            return RoutingDecision(
                handler="help_handler",
                confidence=1.0,
                payload=payload,
                reason="ok",
            )

    monkeypatch.setattr("app.api.commands.get_context_router", lambda: FakeRouter())

    submission = CommandSubmission(
        correlation_id="test",
        command="/help",
        attachments=[],
        selection=SelectionScope(
            selected_nodes=["node-1"],
            selected_edges=["edge-1"],
        ),
    )

    await _route_command_submission(submission)

    payload = captured["payload"]
    assert payload.selection is not None
    assert payload.selection.selected_nodes == ["node-1"]
    assert payload.selection.selected_edges == ["edge-1"]
