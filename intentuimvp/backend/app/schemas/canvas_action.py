"""Pydantic schemas for lightweight canvas CRUD action logging."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CanvasActionType(str, Enum):
    """Supported canvas CRUD actions."""

    NODE_CREATED = "node_created"
    NODE_UPDATED = "node_updated"
    NODE_DELETED = "node_deleted"
    EDGE_CREATED = "edge_created"
    EDGE_UPDATED = "edge_updated"
    EDGE_DELETED = "edge_deleted"


class CanvasActionRequest(BaseModel):
    """Request payload for logging a canvas CRUD action."""

    action: CanvasActionType = Field(..., description="Canvas CRUD action type")
    session_id: str | None = Field(
        default=None, description="Optional session ID for turn logging"
    )
    client_request_id: str | None = Field(
        default=None,
        description="Optional client request ID for idempotent replay",
    )
    workspace_id: int | None = Field(
        default=None, description="Optional canvas/workspace identifier"
    )
    summary: str | None = Field(
        default=None, description="Optional summary override for the turn"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Action payload for turn context"
    )


class CanvasActionResponse(BaseModel):
    """Response payload for a logged canvas CRUD action."""

    status: str = Field(default="logged", description="Status of the logging request")
    turnId: int = Field(  # noqa: N815 - camelCase for API compatibility
        ..., description="Persisted turn identifier"
    )
    sessionId: str = Field(  # noqa: N815 - camelCase for API compatibility
        ..., description="Session ID associated with the turn"
    )
    sequenceNumber: int | None = Field(  # noqa: N815 - camelCase for API compatibility
        default=None, description="Sequential turn number for the session"
    )
    eventType: str | None = Field(  # noqa: N815 - camelCase for API compatibility
        default=None, description="Resolved event type for the turn"
    )
