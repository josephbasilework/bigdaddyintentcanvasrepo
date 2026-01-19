"""Repository for notification operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.notification import Notification


def _apply_notification_filters(
    query,
    *,
    user_id: str,
    workspace_id: int | None,
    session_id: str | None,
    include_dismissed: bool,
    unread_only: bool,
    after_id: int | None,
):
    query = query.filter(Notification.user_id == user_id)
    if workspace_id is not None:
        query = query.filter(Notification.workspace_id == workspace_id)
    if session_id is not None:
        query = query.filter(Notification.session_id == session_id)
    if not include_dismissed:
        query = query.filter(Notification.dismissed_at.is_(None))
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    if after_id is not None:
        query = query.filter(Notification.id > after_id)
    return query


class NotificationRepository:
    """Repository for notification CRUD operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_notification(
        self,
        *,
        user_id: str,
        workspace_id: int | None,
        session_id: str | None,
        source: str | None,
        level: str,
        title: str,
        message: str,
        related_node_id: int | None = None,
        related_edge_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            source=source,
            level=level,
            title=title,
            message=message,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
            notification_metadata=metadata or None,
        )
        if created_at is not None:
            notification.created_at = created_at
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_notification(self, notification_id: int, user_id: str) -> Notification | None:
        return (
            self.db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )

    def list_notifications(
        self,
        *,
        user_id: str,
        workspace_id: int | None,
        session_id: str | None,
        include_dismissed: bool,
        unread_only: bool,
        after_id: int | None,
        limit: int | None,
    ) -> list[Notification]:
        query = self.db.query(Notification)
        query = _apply_notification_filters(
            query,
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            include_dismissed=include_dismissed,
            unread_only=unread_only,
            after_id=after_id,
        )
        query = query.order_by(Notification.created_at.desc(), Notification.id.desc())
        if limit:
            query = query.limit(limit)
        return list(query.all())

    def update_notification(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification


class AsyncNotificationRepository:
    """Async repository for notification CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_notification(
        self,
        *,
        user_id: str,
        workspace_id: int | None,
        session_id: str | None,
        source: str | None,
        level: str,
        title: str,
        message: str,
        related_node_id: int | None = None,
        related_edge_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            source=source,
            level=level,
            title=title,
            message=message,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
            notification_metadata=metadata or None,
        )
        if created_at is not None:
            notification.created_at = created_at
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def get_notification(self, notification_id: int, user_id: str) -> Notification | None:
        result = await self.db.execute(
            select(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_notifications(
        self,
        *,
        user_id: str,
        workspace_id: int | None,
        session_id: str | None,
        include_dismissed: bool,
        unread_only: bool,
        after_id: int | None,
        limit: int | None,
    ) -> list[Notification]:
        stmt = select(Notification)
        stmt = _apply_notification_filters(
            stmt,
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            include_dismissed=include_dismissed,
            unread_only=unread_only,
            after_id=after_id,
        )
        stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
        if limit:
            stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_notification(self, notification: Notification) -> Notification:
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification
