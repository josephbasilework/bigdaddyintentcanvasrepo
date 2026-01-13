"""Pydantic schemas for dashboard subscription API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.dashboard_subscription import DashboardSubscriptionTarget


def _sanitize_list(value: list[Any]) -> list[Any]:
    sanitized: list[Any] = []
    for item in value:
        if isinstance(item, str | int | float | bool | type(None)):
            sanitized.append(item)
        elif isinstance(item, dict):
            sanitized.append(_sanitize_config(item))
        elif isinstance(item, list):
            sanitized.append(_sanitize_list(item))
        else:
            sanitized.append(str(item))
    return sanitized


def _sanitize_config(value: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(item, str | int | float | bool | type(None)):
            sanitized[key] = item
        elif isinstance(item, dict):
            sanitized[key] = _sanitize_config(item)
        elif isinstance(item, list):
            sanitized[key] = _sanitize_list(item)
        else:
            sanitized[key] = str(item)
    return sanitized


class DashboardSubscriptionBase(BaseModel):
    """Base dashboard subscription payload."""

    subscription_target: DashboardSubscriptionTarget = Field(
        ..., description="Subscription target type"
    )
    source_id: str | None = Field(
        default=None, description="Optional source identifier for the subscription"
    )
    config: dict[str, Any] | None = Field(
        default=None, description="Subscription configuration payload"
    )
    is_active: bool = Field(default=True, description="Whether the subscription is active")

    @field_validator("config", mode="before")
    @classmethod
    def sanitize_config(cls, value: Any) -> dict[str, Any] | None:
        """Sanitize subscription config to JSON-safe primitives."""
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("config must be an object")
        return _sanitize_config(value)


class DashboardSubscriptionCreateRequest(DashboardSubscriptionBase):
    """Request body for creating a dashboard subscription."""

    canvas_id: int = Field(..., description="Canvas identifier")
    dashboard_node_id: int = Field(..., description="Dashboard node identifier")


class DashboardSubscriptionUpdateRequest(BaseModel):
    """Request body for updating a dashboard subscription."""

    subscription_target: DashboardSubscriptionTarget | None = Field(
        default=None, description="Updated subscription target"
    )
    source_id: str | None = Field(
        default=None, description="Updated source identifier"
    )
    config: dict[str, Any] | None = Field(
        default=None, description="Updated subscription configuration payload"
    )
    is_active: bool | None = Field(
        default=None, description="Whether the subscription is active"
    )

    @field_validator("config", mode="before")
    @classmethod
    def sanitize_config(cls, value: Any) -> dict[str, Any] | None:
        """Sanitize subscription config to JSON-safe primitives."""
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("config must be an object")
        return _sanitize_config(value)


class DashboardSubscriptionResponse(BaseModel):
    """Response model for dashboard subscription data."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    canvas_id: int = Field(alias="canvasId")
    dashboard_node_id: int = Field(alias="dashboardNodeId")
    subscription_target: DashboardSubscriptionTarget = Field(alias="subscriptionTarget")
    source_id: str | None = Field(default=None, alias="sourceId")
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(alias="isActive")
    created_at: str
    updated_at: str


class DashboardSubscriptionListResponse(BaseModel):
    """Response model for listing dashboard subscriptions."""

    subscriptions: list[DashboardSubscriptionResponse]
    count: int
