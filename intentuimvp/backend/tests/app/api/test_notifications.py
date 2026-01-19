"""Tests for notification API endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import testclient

from app.models.notification import Notification


def _create_notification(
    *,
    title: str,
    message: str,
    dismissed: bool = False,
) -> Notification:
    notification = Notification(
        user_id="default_user",
        workspace_id=None,
        session_id="session-1",
        source="system",
        level="info",
        title=title,
        message=message,
    )
    if dismissed:
        notification.dismissed_at = datetime.utcnow()
    return notification


def test_list_notifications_filters_dismissed(
    app_client: testclient.TestClient,
    db_session,
) -> None:
    notification = _create_notification(title="Hello", message="World")
    dismissed = _create_notification(title="Dismissed", message="Hidden", dismissed=True)
    db_session.add_all([notification, dismissed])
    db_session.commit()

    response = app_client.get("/api/notifications")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["notifications"][0]["title"] == "Hello"

    response = app_client.get("/api/notifications?includeDismissed=true")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2


def test_update_notification_read_and_dismiss(
    app_client: testclient.TestClient,
    db_session,
) -> None:
    notification = _create_notification(title="Needs read", message="Ping")
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)

    response = app_client.put(
        f"/api/notifications/{notification.id}",
        json={"read": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["readAt"] is not None

    response = app_client.put(
        f"/api/notifications/{notification.id}",
        json={"dismissed": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dismissedAt"] is not None
