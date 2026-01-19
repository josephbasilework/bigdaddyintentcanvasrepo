"""SQLAlchemy model for user notifications."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.edge import Edge
    from app.models.node import Node


class Notification(Base):
    """Notification model representing user-facing alerts."""

    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True, comment="User receiving the notification"
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("canvas.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Workspace scope for the notification",
    )
    session_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
        comment="Session scope for the notification",
    )
    source: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
        comment="Origin of the notification (reminder/system/etc.)",
    )
    level: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="info",
        comment="Notification severity (info, success, warning)",
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    related_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("node.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional reference to related node",
    )
    related_edge_id: Mapped[int | None] = mapped_column(
        ForeignKey("edge.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional reference to related edge",
    )
    notification_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="Optional metadata for the notification",
    )

    related_node: Mapped[Node | None] = relationship("Node", foreign_keys=[related_node_id])
    related_edge: Mapped[Edge | None] = relationship("Edge", foreign_keys=[related_edge_id])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "userId": self.user_id,
            "workspaceId": self.workspace_id,
            "sessionId": self.session_id,
            "source": self.source,
            "level": self.level,
            "title": self.title,
            "message": self.message,
            "createdAt": self.created_at.isoformat(),
            "readAt": self.read_at.isoformat() if self.read_at else None,
            "dismissedAt": self.dismissed_at.isoformat() if self.dismissed_at else None,
            "relatedNodeId": self.related_node_id,
            "relatedEdgeId": self.related_edge_id,
            "metadata": self.notification_metadata or {},
        }
