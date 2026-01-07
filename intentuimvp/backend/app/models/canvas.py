"""SQLAlchemy models for canvas and node tables."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Canvas(Base):
    """Canvas model representing a user's workspace."""

    __tablename__ = "canvas"
    __table_args__ = {"extend_existing": True}

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
    nodes: Mapped[list["Node"]] = relationship(
        "Node", back_populates="canvas", cascade="all, delete-orphan"
    )
    edges: Mapped[list["Edge"]] = relationship(
        "Edge", back_populates="canvas", cascade="all, delete-orphan"
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
            "edges": [edge.to_dict() for edge in self.edges],
        }


class Node(Base):
    """Node model representing an element on a canvas."""

    __tablename__ = "node"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # String ID for frontend compatibility (e.g., "node-1234567890-abc123")
    node_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    canvas_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("canvas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Node type: text, document, audio, graph
    type: Mapped[str] = mapped_column(String, nullable=False, default="text")
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Metadata stored as JSON string (renamed from 'metadata' to avoid SQLAlchemy reserved word)
    node_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
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
            "id": self.node_id,  # Use node_id for frontend
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "title": self.title,
            "label": self.title,  # Backwards compatibility - same as title
            "content": self.content,
            "metadata": self.node_metadata,  # Return as 'metadata' for frontend compatibility
        }


class Edge(Base):
    """Edge model representing a connection between two nodes."""

    __tablename__ = "edge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # String ID for frontend compatibility (e.g., "edge-1234567890-abc123")
    edge_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    canvas_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("canvas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_node_id: Mapped[str] = mapped_column(String, nullable=False)
    target_node_id: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False, default="solid")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationship to canvas
    canvas: Mapped["Canvas"] = relationship("Canvas", back_populates="edges")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.edge_id,
            "sourceNodeId": self.source_node_id,
            "targetNodeId": self.target_node_id,
            "label": self.label,
            "type": self.type,
        }
