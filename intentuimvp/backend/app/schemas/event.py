"""Pydantic schemas for event API responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventResponse(BaseModel):
    """Response model for a single event."""

    id: int
    eventType: str  # noqa: N815 - camelCase for API compatibility
    actor: str
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)
    relatedTurnId: int | None = None  # noqa: N815 - camelCase for API compatibility
    relatedNodeId: int | None = None  # noqa: N815 - camelCase for API compatibility
    relatedEdgeId: int | None = None  # noqa: N815 - camelCase for API compatibility


class EventListResponse(BaseModel):
    """Response model for a list of events."""

    events: list[EventResponse]
    count: int
