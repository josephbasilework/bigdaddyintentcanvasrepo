"""SQLAlchemy model for deterministic hooks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Hook(Base):
    """Hook definition for deterministic lifecycle and scheduled triggers."""

    __tablename__ = "hook"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    schedule_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    trigger: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    action: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "hookType": self.hook_type,
            "eventType": self.event_type,
            "scheduleType": self.schedule_type,
            "trigger": self.trigger or {},
            "action": self.action or {},
            "enabled": self.enabled,
            "userId": self.user_id,
            "workspaceId": self.workspace_id,
            "sessionId": self.session_id,
            "lastFiredAt": self.last_fired_at.isoformat() if self.last_fired_at else None,
            "nextRunAt": self.next_run_at.isoformat() if self.next_run_at else None,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }
