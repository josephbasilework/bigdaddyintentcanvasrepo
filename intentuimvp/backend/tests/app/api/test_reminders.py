"""Tests for reminder API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import testclient

from app.models.hook import Hook


def test_create_reminder_creates_schedule_hook(
    app_client: testclient.TestClient,
    db_session,
) -> None:
    remind_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
    payload = {
        "title": "Follow up",
        "message": "Check the task status",
        "remindAt": remind_at,
    }
    response = app_client.post("/api/reminders", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Follow up"
    assert datetime.fromisoformat(data["scheduledFor"]) == datetime.fromisoformat(remind_at)

    hook = db_session.query(Hook).filter(Hook.id == data["hookId"]).first()
    assert hook is not None
    assert hook.hook_type == "schedule"
    assert hook.schedule_type == "date"
    assert hook.trigger
    assert "run_at" in hook.trigger
