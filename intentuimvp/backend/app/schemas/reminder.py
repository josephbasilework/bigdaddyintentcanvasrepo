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

    hookId: int
    scheduledFor: str
    nextRunAt: str | None = None
    title: str
    message: str
    level: str
    nodeId: int | None = None
    workspaceId: int | None = None
    sessionId: str | None = None
    metadata: dict[str, Any] | None = None
