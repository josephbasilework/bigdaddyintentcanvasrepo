"""Repository for hook operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.hook import Hook


def _apply_scope_filters(
    query,
    *,
    user_id: str | None,
    workspace_id: str | None,
    session_id: str | None,
    strict: bool = True,
):
    if user_id is not None:
        query = query.filter(or_(Hook.user_id.is_(None), Hook.user_id == user_id))
    elif strict:
        query = query.filter(Hook.user_id.is_(None))
    if workspace_id is not None:
        query = query.filter(
            or_(Hook.workspace_id.is_(None), Hook.workspace_id == workspace_id)
        )
    elif strict:
        query = query.filter(Hook.workspace_id.is_(None))
    if session_id is not None:
        query = query.filter(
            or_(Hook.session_id.is_(None), Hook.session_id == session_id)
        )
    elif strict:
        query = query.filter(Hook.session_id.is_(None))
    return query


class HookRepository:
    """Repository for Hook CRUD operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_hook(
        self,
        *,
        name: str,
        description: str | None,
        hook_type: str,
        event_type: str | None,
        schedule_type: str | None,
        trigger: dict[str, Any] | None,
        action: dict[str, Any] | None,
        enabled: bool,
        user_id: str | None,
        workspace_id: str | None,
        session_id: str | None,
        next_run_at: datetime | None = None,
    ) -> Hook:
        hook = Hook(
            name=name,
            description=description,
            hook_type=hook_type,
            event_type=event_type,
            schedule_type=schedule_type,
            trigger=trigger or None,
            action=action or None,
            enabled=enabled,
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            next_run_at=next_run_at,
        )
        self.db.add(hook)
        self.db.commit()
        self.db.refresh(hook)
        return hook

    def get_hook(self, hook_id: int) -> Hook | None:
        return self.db.query(Hook).filter(Hook.id == hook_id).first()

    def list_hooks(
        self,
        *,
        hook_type: str | None = None,
        event_type: str | None = None,
        schedule_type: str | None = None,
        enabled: bool | None = None,
        user_id: str | None = None,
        workspace_id: str | None = None,
        session_id: str | None = None,
    ) -> list[Hook]:
        query = self.db.query(Hook)
        if hook_type:
            query = query.filter(Hook.hook_type == hook_type)
        if event_type:
            query = query.filter(Hook.event_type == event_type)
        if schedule_type:
            query = query.filter(Hook.schedule_type == schedule_type)
        if enabled is not None:
            query = query.filter(Hook.enabled == enabled)
        if user_id is not None or workspace_id is not None or session_id is not None:
            query = _apply_scope_filters(
                query,
                user_id=user_id,
                workspace_id=workspace_id,
                session_id=session_id,
                strict=False,
            )
        return list(query.order_by(Hook.id.asc()).all())

    def list_event_hooks(
        self,
        *,
        event_type: str,
        user_id: str | None,
        workspace_id: str | None,
        session_id: str | None,
    ) -> list[Hook]:
        query = self.db.query(Hook).filter(
            Hook.enabled.is_(True),
            Hook.hook_type == "event",
            Hook.event_type == event_type,
        )
        query = _apply_scope_filters(
            query,
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            strict=True,
        )
        return list(query.order_by(Hook.id.asc()).all())

    def list_due_scheduled_hooks(self, now: datetime) -> list[Hook]:
        return list(
            self.db.query(Hook)
            .filter(
                Hook.enabled.is_(True),
                Hook.hook_type == "schedule",
                Hook.next_run_at.is_not(None),
                Hook.next_run_at <= now,
            )
            .order_by(Hook.next_run_at.asc(), Hook.id.asc())
            .all()
        )

    def update_hook(self, hook: Hook) -> Hook:
        self.db.add(hook)
        self.db.commit()
        self.db.refresh(hook)
        return hook

    def update_hook_fields(self, hook_id: int, **fields: Any) -> Hook | None:
        hook = self.get_hook(hook_id)
        if hook is None:
            return None
        for key, value in fields.items():
            if hasattr(hook, key):
                setattr(hook, key, value)
        self.db.add(hook)
        self.db.commit()
        self.db.refresh(hook)
        return hook

    def delete_hook(self, hook_id: int) -> bool:
        hook = self.get_hook(hook_id)
        if hook is None:
            return False
        self.db.delete(hook)
        self.db.commit()
        return True


class AsyncHookRepository:
    """Async repository for Hook CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_hook(
        self,
        *,
        name: str,
        description: str | None,
        hook_type: str,
        event_type: str | None,
        schedule_type: str | None,
        trigger: dict[str, Any] | None,
        action: dict[str, Any] | None,
        enabled: bool,
        user_id: str | None,
        workspace_id: str | None,
        session_id: str | None,
        next_run_at: datetime | None = None,
    ) -> Hook:
        hook = Hook(
            name=name,
            description=description,
            hook_type=hook_type,
            event_type=event_type,
            schedule_type=schedule_type,
            trigger=trigger or None,
            action=action or None,
            enabled=enabled,
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            next_run_at=next_run_at,
        )
        self.db.add(hook)
        await self.db.commit()
        await self.db.refresh(hook)
        return hook

    async def get_hook(self, hook_id: int) -> Hook | None:
        result = await self.db.execute(select(Hook).filter(Hook.id == hook_id))
        return result.scalar_one_or_none()

    async def list_hooks(
        self,
        *,
        hook_type: str | None = None,
        event_type: str | None = None,
        schedule_type: str | None = None,
        enabled: bool | None = None,
        user_id: str | None = None,
        workspace_id: str | None = None,
        session_id: str | None = None,
    ) -> list[Hook]:
        stmt = select(Hook)
        conditions = []
        if hook_type:
            conditions.append(Hook.hook_type == hook_type)
        if event_type:
            conditions.append(Hook.event_type == event_type)
        if schedule_type:
            conditions.append(Hook.schedule_type == schedule_type)
        if enabled is not None:
            conditions.append(Hook.enabled == enabled)
        if conditions:
            stmt = stmt.filter(and_(*conditions))
        if user_id is not None or workspace_id is not None or session_id is not None:
            stmt = _apply_scope_filters(
                stmt,
                user_id=user_id,
                workspace_id=workspace_id,
                session_id=session_id,
                strict=False,
            )
        stmt = stmt.order_by(Hook.id.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_event_hooks(
        self,
        *,
        event_type: str,
        user_id: str | None,
        workspace_id: str | None,
        session_id: str | None,
    ) -> list[Hook]:
        stmt = select(Hook).filter(
            Hook.enabled.is_(True),
            Hook.hook_type == "event",
            Hook.event_type == event_type,
        )
        stmt = _apply_scope_filters(
            stmt,
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            strict=True,
        )
        stmt = stmt.order_by(Hook.id.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_due_scheduled_hooks(self, now: datetime) -> list[Hook]:
        stmt = (
            select(Hook)
            .filter(
                Hook.enabled.is_(True),
                Hook.hook_type == "schedule",
                Hook.next_run_at.is_not(None),
                Hook.next_run_at <= now,
            )
            .order_by(Hook.next_run_at.asc(), Hook.id.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_hook(self, hook: Hook) -> Hook:
        self.db.add(hook)
        await self.db.commit()
        await self.db.refresh(hook)
        return hook

    async def update_hook_fields(self, hook_id: int, **fields: Any) -> Hook | None:
        hook = await self.get_hook(hook_id)
        if hook is None:
            return None
        for key, value in fields.items():
            if hasattr(hook, key):
                setattr(hook, key, value)
        self.db.add(hook)
        await self.db.commit()
        await self.db.refresh(hook)
        return hook

    async def delete_hook(self, hook_id: int) -> bool:
        hook = await self.get_hook(hook_id)
        if hook is None:
            return False
        await self.db.delete(hook)
        await self.db.commit()
        return True
