"""Notification API endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.repositories.notification_repo import AsyncNotificationRepository
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    NotificationUpdateRequest,
)

router = APIRouter()


def get_current_user() -> str:
    """Get current user from authentication (MVP default)."""
    return "default_user"


@router.get("/api/notifications", response_model=NotificationListResponse)
async def list_notifications(
    session_id: str | None = Query(default=None, alias="sessionId"),
    workspace_id: int | None = Query(default=None, alias="workspaceId"),
    unread_only: bool = Query(default=False, alias="unreadOnly"),
    include_dismissed: bool = Query(default=False, alias="includeDismissed"),
    after_id: int | None = Query(default=None, ge=0, alias="afterId"),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> NotificationListResponse:
    """List notifications for the current user."""
    repo = AsyncNotificationRepository(db)
    notifications = await repo.list_notifications(
        user_id=user_id,
        workspace_id=workspace_id,
        session_id=session_id,
        include_dismissed=include_dismissed,
        unread_only=unread_only,
        after_id=after_id,
        limit=limit,
    )
    return NotificationListResponse(
        notifications=[NotificationResponse(**item.to_dict()) for item in notifications],
        count=len(notifications),
    )


@router.put(
    "/api/notifications/{notification_id}",
    response_model=NotificationResponse,
)
async def update_notification(
    notification_id: int,
    payload: NotificationUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> NotificationResponse:
    """Update notification read/dismissed status."""
    if payload.read is None and payload.dismissed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="read or dismissed must be provided",
        )
    repo = AsyncNotificationRepository(db)
    notification = await repo.get_notification(notification_id, user_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    now = datetime.utcnow()
    if payload.read is not None:
        notification.read_at = now if payload.read else None
    if payload.dismissed is not None:
        notification.dismissed_at = now if payload.dismissed else None

    notification = await repo.update_notification(notification)
    return NotificationResponse(**notification.to_dict())
