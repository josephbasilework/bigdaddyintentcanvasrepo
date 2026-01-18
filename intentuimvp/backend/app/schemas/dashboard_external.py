"""Schemas for dashboard external state interactions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DashboardExternalWriteRequest(BaseModel):
    """Request payload for external write-back actions."""

    canvas_id: int = Field(..., description="Canvas identifier")
    dashboard_node_id: int = Field(..., description="Dashboard node identifier")
    confirm: bool = Field(default=False, description="Whether user confirmed the write")
    payload_override: dict[str, Any] | None = Field(
        default=None, description="Optional payload override"
    )


class DashboardExternalWriteResponse(BaseModel):
    """Response payload for external write-back actions."""

    success: bool
    result: Any | None = None
    error: str | None = None
    requires_confirmation: bool = False
    preview: dict[str, Any] | None = None
    diff: dict[str, Any] | None = None
