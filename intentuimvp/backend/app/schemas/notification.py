"""Pydantic schemas for notification API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    """Response model for a notification."""

    id: int
    userId: str  # noqa: N815 - camelCase for API compatibility
    workspaceId: int | None = None  # noqa: N815 - camelCase for API compatibility
    sessionId: str | None = None  # noqa: N815 - camelCase for API compatibility
    source: str | None = None
    level: str
    title: str
    message: str
    createdAt: str  # noqa: N815 - camelCase for API compatibility
    readAt: str | None = None  # noqa: N815 - camelCase for API compatibility
    dismissedAt: str | None = None  # noqa: N815 - camelCase for API compatibility
    relatedNodeId: int | None = None  # noqa: N815 - camelCase for API compatibility
    relatedEdgeId: int | None = None  # noqa: N815 - camelCase for API compatibility
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
