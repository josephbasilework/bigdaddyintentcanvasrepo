"""SQLAlchemy models for canvas and node tables."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
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

    # Relationship to nodes
    nodes: Mapped[list["Node"]] = relationship(
        "Node", back_populates="canvas", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "nodes": [node.to_dict() for node in self.nodes],
        }


class Node(Base):
    """Node model representing an element on a canvas."""

    __tablename__ = "node"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canvas_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("canvas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    y: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    z: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationship to canvas
    canvas: Mapped["Canvas"] = relationship("Canvas", back_populates="nodes")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "canvas_id": self.canvas_id,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "created_at": self.created_at.isoformat(),
        }
