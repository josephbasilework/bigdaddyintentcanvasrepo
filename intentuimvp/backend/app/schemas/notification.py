"""Pydantic schemas for notification API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    """Response model for a notification."""

    id: int
    userId: str
    workspaceId: int | None = None
    sessionId: str | None = None
    source: str | None = None
    level: str
    title: str
    message: str
    createdAt: str
    readAt: str | None = None
    dismissedAt: str | None = None
    relatedNodeId: int | None = None
    relatedEdgeId: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationListResponse(BaseModel):
    """Response model for a list of notifications."""

    notifications: list[NotificationResponse]
    count: int


class NotificationUpdateRequest(BaseModel):
    """Request payload for updating notification status."""

    model_config = ConfigDict(populate_by_name=True)

    read: bool | None = None
    dismissed: bool | None = None
