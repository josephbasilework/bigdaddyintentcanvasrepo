"""Event query API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.repositories.event_repo import AsyncEventRepository
from app.schemas.event import EventListResponse, EventResponse

router = APIRouter()


@router.get("/api/events", response_model=EventListResponse)
async def list_events(
    session_id: str = Query(..., description="Session ID to fetch events for"),
    event_type: str | None = Query(
        default=None,
        alias="type",
        description="Optional event type filter",
    ),
    actor: str | None = Query(default=None, description="Optional actor filter"),
    related_node_id: int | None = Query(
        default=None, description="Optional related node filter"
    ),
    related_edge_id: int | None = Query(
        default=None, description="Optional related edge filter"
    ),
    after_id: int | None = Query(
        default=None,
        ge=0,
        description="Optional event ID to start after (exclusive)",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Max events to return",
    ),
    db: AsyncSession = Depends(get_async_db),
) -> EventListResponse:
    """List events for a session with optional filters."""
    repo = AsyncEventRepository(db)
    events = await repo.get_events_for_session(
        session_id,
        limit=limit,
        after_id=after_id,
        actor=actor,
        event_type=event_type,
        related_node_id=related_node_id,
        related_edge_id=related_edge_id,
    )
    return EventListResponse(
        events=[EventResponse(**event.to_dict()) for event in events],
        count=len(events),
    )
