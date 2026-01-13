"""SQLAlchemy model for dashboard subscription table."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.canvas import Canvas
    from app.models.node import Node


class DashboardSubscriptionTarget(str, Enum):
    """Enumeration of dashboard subscription targets."""

    WORKSPACE_STATE = "workspace_state"
    NODE = "node"
    EDGE = "edge"
    JOB = "job"
    ARTIFACT = "artifact"
    TOOL_OUTPUT = "tool_output"


class DashboardSubscription(Base):
    """Dashboard subscription model for live workspace views."""

    __tablename__ = "dashboard_subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canvas_id: Mapped[int] = mapped_column(
        ForeignKey("canvas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dashboard_node_id: Mapped[int] = mapped_column(
        ForeignKey("node.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_target: Mapped[DashboardSubscriptionTarget] = mapped_column(
        String, nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    subscription_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    canvas: Mapped[Canvas] = relationship("Canvas", back_populates="dashboard_subscriptions")
    dashboard_node: Mapped[Node] = relationship(
        "Node",
        back_populates="dashboard_subscriptions",
        foreign_keys=[dashboard_node_id],
    )

    @property
    def config(self) -> dict[str, Any]:
        """Expose parsed config for schema serialization."""
        return self.get_config()

    @config.setter
    def config(self, value: dict[str, Any] | None) -> None:
        """Set config from dictionary or clear when None."""
        if value is None:
            self.subscription_config = None
        else:
            self.set_config(value)

    def get_config(self) -> dict[str, Any]:
        """Get subscription config as dictionary."""
        return json.loads(self.subscription_config) if self.subscription_config else {}

    def set_config(self, config: dict[str, Any]) -> None:
        """Set subscription config from dictionary."""
        self.subscription_config = json.dumps(config)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "canvasId": self.canvas_id,
            "dashboardNodeId": self.dashboard_node_id,
            "subscriptionTarget": self.subscription_target,
            "sourceId": self.source_id,
            "config": self.get_config(),
            "isActive": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
