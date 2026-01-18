"""Pydantic schemas for turn API responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TurnResponse(BaseModel):
    """Response model for a single turn."""

    id: int
    sessionId: str
    sequenceNumber: int
    timestamp: str
    actor: str
    type: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    responseType: str | None = None
    relatedNodeId: int | None = None
    relatedEdgeId: int | None = None


class TurnListResponse(BaseModel):
    """Response model for a list of turns."""

    turns: list[TurnResponse]
    count: int
