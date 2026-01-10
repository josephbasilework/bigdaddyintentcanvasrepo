"""SQLAlchemy model for node table."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.canvas import Canvas
    from app.models.edge import Edge


class NodeType(str, Enum):
    """Enumeration of node types."""

    TEXT = "text"
    DOCUMENT = "document"
    AUDIO = "audio"
    GRAPH = "graph"


class Node(Base):
    """Node model representing an element on a canvas."""

    __tablename__ = "node"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canvas_id: Mapped[int] = mapped_column(
        ForeignKey("canvas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NodeType] = mapped_column(String, nullable=False, default=NodeType.TEXT)
    label: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string: {"x": 0, "y": 0, "z": 0}
    node_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string for additional metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    canvas: Mapped[Canvas] = relationship("Canvas", back_populates="nodes")
    outgoing_edges: Mapped[list[Edge]] = relationship(
        "Edge", foreign_keys="Edge.from_node_id", back_populates="from_node"
    )
    incoming_edges: Mapped[list[Edge]] = relationship(
        "Edge", foreign_keys="Edge.to_node_id", back_populates="to_node"
    )

    def get_position(self) -> dict:
        """Get position as dictionary."""
        return json.loads(self.position) if self.position else {"x": 0, "y": 0, "z": 0}

    def set_position(self, position: dict) -> None:
        """Set position from dictionary."""
        self.position = json.dumps(position)

    def get_metadata(self) -> dict:
        """Get metadata as dictionary."""
        return json.loads(self.node_metadata) if self.node_metadata else {}

    def set_metadata(self, metadata: dict) -> None:
        """Set metadata from dictionary."""
        self.node_metadata = json.dumps(metadata)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "canvasId": self.canvas_id,
            "type": self.type,
            "label": self.label,
            "position": self.get_position(),
            "metadata": self.get_metadata(),
            "created_at": self.created_at.isoformat(),
        }
