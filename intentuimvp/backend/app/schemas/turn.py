"""Pydantic schemas for turn API responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TurnResponse(BaseModel):
    """Response model for a single turn."""

    id: int
    sessionId: str  # noqa: N815 - camelCase for API compatibility
    sequenceNumber: int  # noqa: N815 - camelCase for API compatibility
    timestamp: str
    actor: str
    type: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    responseType: str | None = None  # noqa: N815 - camelCase for API compatibility
    eventType: str | None = None  # noqa: N815 - camelCase for API compatibility
    originSequenceNumber: int | None = None  # noqa: N815 - camelCase for API compatibility
    relatedNodeId: int | None = None  # noqa: N815 - camelCase for API compatibility
    relatedEdgeId: int | None = None  # noqa: N815 - camelCase for API compatibility


class TurnListResponse(BaseModel):
    """Response model for a list of turns."""

    turns: list[TurnResponse]
    count: int
