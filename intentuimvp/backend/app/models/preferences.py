"""SQLAlchemy model for user preferences."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Preferences(Base):
    """User preferences model for theme, zoom, and panel layouts.

    Stores user-specific preferences that persist across sessions.
    Each user has one preferences record that is upserted on save.
    """

    __tablename__ = "preferences"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    preferences: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with user_id, preferences, and updated_at
        """
        return {
            "user_id": self.user_id,
            "preferences": self.preferences,
            "updated_at": self.updated_at.isoformat(),
        }
