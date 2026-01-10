"""SQLAlchemy model for canvas table."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Canvas(Base):
    """Canvas model representing a user's workspace."""

    __tablename__ = "canvas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    nodes: Mapped[list["Node"]] = relationship(  # noqa: F821
        "Node", back_populates="canvas", cascade="all, delete-orphan"
    )
    edges: Mapped[list["Edge"]] = relationship(  # noqa: F821
        "Edge", back_populates="canvas", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
