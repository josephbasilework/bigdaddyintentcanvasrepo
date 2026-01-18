"""Pydantic schemas for hook API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HookBase(BaseModel):
    """Base hook payload."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str | None = None
    hook_type: str = Field(alias="hookType")
    event_type: str | None = Field(default=None, alias="eventType")
    schedule_type: str | None = Field(default=None, alias="scheduleType")
    trigger: dict[str, Any] = Field(default_factory=dict)
    action: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    user_id: str | None = Field(default=None, alias="userId")
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    session_id: str | None = Field(default=None, alias="sessionId")


class HookCreateRequest(HookBase):
    """Request payload for creating a hook."""


class HookUpdateRequest(BaseModel):
    """Request payload for updating a hook."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    description: str | None = None
    hook_type: str | None = Field(default=None, alias="hookType")
    event_type: str | None = Field(default=None, alias="eventType")
    schedule_type: str | None = Field(default=None, alias="scheduleType")
    trigger: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    enabled: bool | None = None
    user_id: str | None = Field(default=None, alias="userId")
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    session_id: str | None = Field(default=None, alias="sessionId")


class HookResponse(BaseModel):
    """Response model for a hook."""

    id: int
    name: str
    description: str | None = None
    hookType: str
    eventType: str | None = None
    scheduleType: str | None = None
    trigger: dict[str, Any] = Field(default_factory=dict)
    action: dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    userId: str | None = None
    workspaceId: str | None = None
    sessionId: str | None = None
    lastFiredAt: str | None = None
    nextRunAt: str | None = None
    createdAt: str
    updatedAt: str


class HookListResponse(BaseModel):
    """Response model for a list of hooks."""

    hooks: list[HookResponse]
    count: int
