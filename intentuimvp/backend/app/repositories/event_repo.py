"""Repository for unified event operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.turn import Turn


class EventRepository:
    """Repository for Event CRUD operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_event(
        self,
        *,
        event_type: str,
        actor: str,
        related_turn_id: int,
        payload: dict[str, Any] | None = None,
        related_node_id: int | None = None,
        related_edge_id: int | None = None,
        timestamp: datetime | None = None,
    ) -> Event:
        event = Event(
            event_type=event_type,
            actor=actor,
            related_turn_id=related_turn_id,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
        )
        if timestamp is not None:
            event.timestamp = timestamp
        if payload:
            event.set_payload(payload)

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_events_for_session(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        after_id: int | None = None,
        actor: str | None = None,
        event_type: str | None = None,
        related_node_id: int | None = None,
        related_edge_id: int | None = None,
    ) -> list[Event]:
        query = (
            self.db.query(Event)
            .join(Turn, Event.related_turn_id == Turn.id)
            .filter(Turn.session_id == session_id)
        )

        if after_id is not None:
            query = query.filter(Event.id > after_id)
        if actor is not None:
            query = query.filter(Event.actor == actor)
        if event_type is not None:
            query = query.filter(Event.event_type == event_type)
        if related_node_id is not None:
            query = query.filter(Event.related_node_id == related_node_id)
        if related_edge_id is not None:
            query = query.filter(Event.related_edge_id == related_edge_id)

        query = query.order_by(Event.timestamp.asc(), Event.id.asc())
        if limit:
            query = query.limit(limit)

        return list(query.all())


class AsyncEventRepository:
    """Async repository for Event CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_event(
        self,
        *,
        event_type: str,
        actor: str,
        related_turn_id: int,
        payload: dict[str, Any] | None = None,
        related_node_id: int | None = None,
        related_edge_id: int | None = None,
        timestamp: datetime | None = None,
    ) -> Event:
        event = Event(
            event_type=event_type,
            actor=actor,
            related_turn_id=related_turn_id,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
        )
        if timestamp is not None:
            event.timestamp = timestamp
        if payload:
            event.set_payload(payload)

        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_events_for_session(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        after_id: int | None = None,
        actor: str | None = None,
        event_type: str | None = None,
        related_node_id: int | None = None,
        related_edge_id: int | None = None,
    ) -> list[Event]:
        stmt = (
            select(Event)
            .join(Turn, Event.related_turn_id == Turn.id)
            .filter(Turn.session_id == session_id)
        )

        if after_id is not None:
            stmt = stmt.filter(Event.id > after_id)
        if actor is not None:
            stmt = stmt.filter(Event.actor == actor)
        if event_type is not None:
            stmt = stmt.filter(Event.event_type == event_type)
        if related_node_id is not None:
            stmt = stmt.filter(Event.related_node_id == related_node_id)
        if related_edge_id is not None:
            stmt = stmt.filter(Event.related_edge_id == related_edge_id)

        stmt = stmt.order_by(Event.timestamp.asc(), Event.id.asc())
        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

