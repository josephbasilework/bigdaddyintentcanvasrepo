"""SQLAlchemy model for workspace_session table.

A WorkspaceSession represents a persistent session identity that spans across
WebSocket reconnections. Sessions are workspace-scoped and tie together:
- WebSocket connections
- Turn timelines (via session_id foreign key in Turn)
- Context routing decisions

Sessions are created when a workspace is opened and can be resumed on reconnect.
The session_id serves as the global identifier referenced by Turns and other
session-scoped entities.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.canvas import Canvas


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())


class WorkspaceSession(Base):
    """WorkspaceSession model representing a persistent session identity.

    Sessions persist across WebSocket reconnections and provide the identity
    link between turns, context routing, and real-time updates.

    Attributes:
        id: Auto-increment primary key for internal references
        session_id: Unique session identifier (UUID) used externally
        workspace_id: Foreign key to the canvas/workspace this session belongs to
        user_id: The user who owns this session (matches canvas.user_id)
        created_at: When this session was first created
        last_active_at: When this session was last active (updated on reconnect)
        resumed_count: Number of times this session has been resumed
    """

    __tablename__ = "workspace_session"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Session identity
    session_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
        index=True,
        default=generate_session_id,
        comment="Unique session identifier (UUID)",
    )

    # Workspace relationship
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("canvas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to canvas/workspace",
    )

    # User ownership (denormalized for efficient queries)
    user_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
        comment="User who owns this session",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="When this session was created",
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
        comment="When this session was last active",
    )

    # Session metrics
    resumed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times session has been resumed",
    )

    # Relationships
    workspace: Mapped[Canvas] = relationship("Canvas", foreign_keys=[workspace_id])

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "workspaceId": self.workspace_id,
            "userId": self.user_id,
            "createdAt": self.created_at.isoformat(),
            "lastActiveAt": self.last_active_at.isoformat(),
            "resumedCount": self.resumed_count,
        }

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<WorkspaceSession(id={self.id}, session_id={self.session_id}, "
            f"workspace_id={self.workspace_id}, user_id={self.user_id})>"
        )
