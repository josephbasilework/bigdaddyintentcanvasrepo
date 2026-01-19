"""Notification creation and dispatch helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.agui import AgentNotificationMessage, AgentNotificationPayload
from app.database import AsyncSessionLocal, SessionLocal
from app.models.turn import Turn, TurnType
from app.repositories.notification_repo import (
    AsyncNotificationRepository,
    NotificationRepository,
)
from app.repositories.session_repo import AsyncSessionRepository, SessionRepository

_ALLOWED_LEVELS = {"info", "success", "warning"}


@dataclass(frozen=True)
class NotificationSpec:
    level: str
    title: str
    message: str
    source: str | None = None
    related_node_id: int | None = None
    related_edge_id: int | None = None
    metadata: dict[str, Any] | None = None


def _normalize_level(value: str | None) -> str:
    if not value:
        return "info"
    normalized = value.strip().lower()
    return normalized if normalized in _ALLOWED_LEVELS else "info"


def _extract_duration(metadata: dict[str, Any] | None) -> int | None:
    if not metadata:
        return None
    for key in ("duration", "duration_ms", "durationMs"):
        value = metadata.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _extract_actions(metadata: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    if not metadata:
        return None
    actions = metadata.get("actions")
    if isinstance(actions, list) and actions:
        clean = [item for item in actions if isinstance(item, dict)]
        return clean or None
    return None


async def _dispatch_notification_async(
    *,
    notification: NotificationSpec,
    session_id: str | None,
    user_id: str | None,
) -> None:
    from app.ws.websocket import manager

    payload = AgentNotificationPayload(
        level=_normalize_level(notification.level),
        title=notification.title,
        message=notification.message,
        duration=_extract_duration(notification.metadata),
        actions=_extract_actions(notification.metadata),
    )
    message = AgentNotificationMessage(payload=payload)

    if session_id:
        for ws in manager.get_connections_by_session(session_id):
            await manager.send_agui_message(message, ws)
        return

    if user_id:
        for ws in manager.get_connections_by_user(user_id):
            await manager.send_agui_message(message, ws)
        return

    await manager.broadcast_agui(message)


def _dispatch_notification_sync(
    *,
    notification: NotificationSpec,
    session_id: str | None,
    user_id: str | None,
) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(
            _dispatch_notification_async(
                notification=notification,
                session_id=session_id,
                user_id=user_id,
            )
        )
        return

    loop.create_task(
        _dispatch_notification_async(
            notification=notification,
            session_id=session_id,
            user_id=user_id,
        )
    )


async def create_notification_async(
    *,
    user_id: str,
    workspace_id: int | None,
    session_id: str | None,
    level: str,
    title: str,
    message: str,
    source: str | None = None,
    related_node_id: int | None = None,
    related_edge_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Create and dispatch a notification using a new AsyncSessionLocal session."""
    spec = NotificationSpec(
        level=_normalize_level(level),
        title=title,
        message=message,
        source=source,
        related_node_id=related_node_id,
        related_edge_id=related_edge_id,
        metadata=metadata,
    )
    async with AsyncSessionLocal() as db:
        repo = AsyncNotificationRepository(db)
        await repo.create_notification(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            source=source,
            level=spec.level,
            title=spec.title,
            message=spec.message,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
            metadata=metadata,
        )

    await _dispatch_notification_async(
        notification=spec,
        session_id=session_id,
        user_id=user_id,
    )


def create_notification_sync(
    *,
    user_id: str,
    workspace_id: int | None,
    session_id: str | None,
    level: str,
    title: str,
    message: str,
    source: str | None = None,
    related_node_id: int | None = None,
    related_edge_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Create and dispatch a notification using a new SessionLocal session."""
    spec = NotificationSpec(
        level=_normalize_level(level),
        title=title,
        message=message,
        source=source,
        related_node_id=related_node_id,
        related_edge_id=related_edge_id,
        metadata=metadata,
    )
    db = SessionLocal()
    try:
        repo = NotificationRepository(db)
        repo.create_notification(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            source=source,
            level=spec.level,
            title=spec.title,
            message=spec.message,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
            metadata=metadata,
        )
    finally:
        db.close()

    _dispatch_notification_sync(
        notification=spec,
        session_id=session_id,
        user_id=user_id,
    )


def _spec_from_job_turn(turn: Turn) -> NotificationSpec | None:
    payload = turn.get_payload()
    job_id = payload.get("job_id") or payload.get("jobId")
    job_type = payload.get("job_type") or payload.get("jobType")
    label = job_id or job_type or "Job"
    if turn.type == TurnType.JOB_COMPLETED:
        level = "success"
        title = "Job complete"
        message = f"{label} completed."
        return NotificationSpec(
            level=level,
            title=title,
            message=message,
            source="job",
            related_node_id=turn.related_node_id,
            related_edge_id=turn.related_edge_id,
        )
    if turn.type == TurnType.JOB_FAILED:
        level = "warning"
        title = "Job failed"
        error_message = payload.get("error")
        message = (
            f"{label} failed: {error_message}" if isinstance(error_message, str) else f"{label} failed."
        )
        return NotificationSpec(
            level=level,
            title=title,
            message=message,
            source="job",
            related_node_id=turn.related_node_id,
            related_edge_id=turn.related_edge_id,
        )
    return None


def _spec_from_external_turn(turn: Turn) -> NotificationSpec | None:
    payload = turn.get_payload()
    detail = payload.get("summary") or payload.get("status")
    message = (
        f"External state updated: {detail}" if isinstance(detail, str) else "External state updated."
    )
    return NotificationSpec(
        level="info",
        title="External update",
        message=message,
        source="external",
        related_node_id=turn.related_node_id,
        related_edge_id=turn.related_edge_id,
    )


def _spec_from_hook_turn(turn: Turn) -> NotificationSpec | None:
    payload = turn.get_payload()
    hook_type = payload.get("hook_type") or payload.get("hookType")
    if hook_type != "schedule":
        return None
    action = payload.get("action")
    if isinstance(action, dict):
        action_type = action.get("type") or action.get("action_type") or action.get("actionType")
        if isinstance(action_type, str) and action_type.strip().lower() == "notification":
            return None
    hook_name = payload.get("hook_name") or payload.get("hookName") or "Scheduled hook"
    return NotificationSpec(
        level="info",
        title="Scheduled trigger fired",
        message=f"{hook_name} fired.",
        source="hook",
        related_node_id=turn.related_node_id,
        related_edge_id=turn.related_edge_id,
    )


def _notification_spec_for_turn(turn: Turn) -> NotificationSpec | None:
    if turn.type in {TurnType.JOB_COMPLETED, TurnType.JOB_FAILED}:
        return _spec_from_job_turn(turn)
    if turn.type == TurnType.EXTERNAL_STATE_CHANGE:
        return _spec_from_external_turn(turn)
    if turn.type == TurnType.HOOK_FIRED:
        return _spec_from_hook_turn(turn)
    return None


def maybe_create_notification_for_turn_sync(db: Session, turn: Turn) -> None:
    """Create notifications for turns that warrant user attention."""
    spec = _notification_spec_for_turn(turn)
    if spec is None:
        return
    session_repo = SessionRepository(db)
    session = session_repo.get_by_session_id(turn.session_id)
    if session is None:
        return
    repo = NotificationRepository(db)
    repo.create_notification(
        user_id=session.user_id,
        workspace_id=session.workspace_id,
        session_id=session.session_id,
        source=spec.source,
        level=spec.level,
        title=spec.title,
        message=spec.message,
        related_node_id=spec.related_node_id,
        related_edge_id=spec.related_edge_id,
        metadata=spec.metadata,
    )
    _dispatch_notification_sync(
        notification=spec,
        session_id=session.session_id,
        user_id=session.user_id,
    )


async def maybe_create_notification_for_turn_async(db: AsyncSession, turn: Turn) -> None:
    """Async notification creation for important turns."""
    spec = _notification_spec_for_turn(turn)
    if spec is None:
        return
    session_repo = AsyncSessionRepository(db)
    session = await session_repo.get_by_session_id(turn.session_id)
    if session is None:
        return
    repo = AsyncNotificationRepository(db)
    await repo.create_notification(
        user_id=session.user_id,
        workspace_id=session.workspace_id,
        session_id=session.session_id,
        source=spec.source,
        level=spec.level,
        title=spec.title,
        message=spec.message,
        related_node_id=spec.related_node_id,
        related_edge_id=spec.related_edge_id,
        metadata=spec.metadata,
    )
    await _dispatch_notification_async(
        notification=spec,
        session_id=session.session_id,
        user_id=session.user_id,
    )
