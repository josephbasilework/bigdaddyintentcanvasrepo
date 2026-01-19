"""Reminder API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.repositories.hook_repo import AsyncHookRepository
from app.repositories.session_repo import AsyncSessionRepository
from app.schemas.reminder import ReminderCreateRequest, ReminderResponse
from app.services.hooks import (
    HOOK_TYPE_SCHEDULE,
    SCHEDULE_TYPE_DATE,
    ensure_next_run_at,
)

router = APIRouter()


def get_current_user() -> str:
    """Get current user from authentication (MVP default)."""
    return "default_user"


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _coerce_int(value: int | str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


@router.post(
    "/api/reminders",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reminder(
    payload: ReminderCreateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> ReminderResponse:
    """Create a time-based reminder notification."""
    scheduled_for = _normalize_datetime(payload.remind_at)
    now = datetime.utcnow()
    if scheduled_for <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="remindAt must be in the future",
        )

    session_repo = AsyncSessionRepository(db)
    session = (
        await session_repo.get_by_session_id(payload.session_id)
        if payload.session_id
        else None
    )
    resolved_user_id = session.user_id if session else user_id
    resolved_workspace_id = (
        session.workspace_id if session else payload.workspace_id
    )

    raw_node_id = payload.node_id
    node_id = _coerce_int(raw_node_id)
    action_metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    if raw_node_id is not None and node_id is None:
        action_metadata["nodeId"] = str(raw_node_id)
    if not action_metadata:
        action_metadata = None

    action = {
        "type": "notification",
        "title": payload.title,
        "message": payload.message,
        "level": payload.level or "info",
        "related_node_id": node_id,
        **({"metadata": action_metadata} if action_metadata else {}),
    }

    repo = AsyncHookRepository(db)
    hook = await repo.create_hook(
        name=f"Reminder: {payload.title}",
        description=payload.message,
        hook_type=HOOK_TYPE_SCHEDULE,
        event_type=None,
        schedule_type=SCHEDULE_TYPE_DATE,
        trigger={"run_at": scheduled_for.isoformat()},
        action=action,
        enabled=True,
        user_id=resolved_user_id,
        workspace_id=str(resolved_workspace_id) if resolved_workspace_id else None,
        session_id=payload.session_id,
    )
    hook = ensure_next_run_at(hook)
    hook = await repo.update_hook(hook)

    return ReminderResponse(
        hookId=hook.id,
        scheduledFor=scheduled_for.isoformat(),
        nextRunAt=hook.next_run_at.isoformat() if hook.next_run_at else None,
        title=payload.title,
        message=payload.message,
        level=payload.level or "info",
        nodeId=node_id,
        workspaceId=resolved_workspace_id,
        sessionId=payload.session_id,
        metadata=action_metadata,
    )
