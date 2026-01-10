"""SQLAlchemy model for edge table."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RelationType(str, Enum):
    """Enumeration of edge relation types."""

    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    SUPPORTS = "supports"
    CONFLICTS = "conflicts"
    DERIVED_FROM = "derived_from"
    CRITIQUES = "critiques"


class Edge(Base):
    """Edge model representing a connection between two nodes."""

    __tablename__ = "edge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canvas_id: Mapped[int] = mapped_column(
        ForeignKey("canvas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_node_id: Mapped[int] = mapped_column(
        ForeignKey("node.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_node_id: Mapped[int] = mapped_column(
        ForeignKey("node.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[RelationType] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    canvas: Mapped["Canvas"] = relationship("Canvas", back_populates="edges")  # noqa: F821
    from_node: Mapped["Node"] = relationship(  # noqa: F821
        "Node", foreign_keys=[from_node_id], back_populates="outgoing_edges"
    )
    to_node: Mapped["Node"] = relationship(  # noqa: F821
        "Node", foreign_keys=[to_node_id], back_populates="incoming_edges"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "canvasId": self.canvas_id,
            "fromNodeId": self.from_node_id,
            "toNodeId": self.to_node_id,
            "relationType": self.relation_type,
            "created_at": self.created_at.isoformat(),
        }
