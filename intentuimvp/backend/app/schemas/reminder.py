"""Pydantic schemas for reminder API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReminderCreateRequest(BaseModel):
    """Request payload for creating a reminder."""

    model_config = ConfigDict(populate_by_name=True)

    title: str
    message: str
    remind_at: datetime = Field(alias="remindAt")
    level: str | None = None
    node_id: int | str | None = Field(default=None, alias="nodeId")
    workspace_id: int | None = Field(default=None, alias="workspaceId")
    session_id: str | None = Field(default=None, alias="sessionId")
    metadata: dict[str, Any] | None = None


class ReminderResponse(BaseModel):
    """Response payload for created reminder."""

    hookId: int  # noqa: N815 - camelCase for API compatibility
    scheduledFor: str  # noqa: N815 - camelCase for API compatibility
    nextRunAt: str | None = None  # noqa: N815 - camelCase for API compatibility
    title: str
    message: str
    level: str
    nodeId: int | None = None  # noqa: N815 - camelCase for API compatibility
    workspaceId: int | None = None  # noqa: N815 - camelCase for API compatibility
    sessionId: str | None = None  # noqa: N815 - camelCase for API compatibility
    metadata: dict[str, Any] | None = None
