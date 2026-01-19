"""SQLAlchemy model for unified event logging."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.edge import Edge
    from app.models.node import Node
    from app.models.turn import Turn


class Event(Base):
    """Event model representing a structured system event."""

    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
        comment="Namespaced event type (e.g., node.created)",
    )
    actor: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
        comment="Actor responsible for the event",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Event timestamp",
    )
    event_payload: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON payload for the event"
    )

    related_turn_id: Mapped[int] = mapped_column(
        ForeignKey("turn.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related turn identifier",
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

    related_turn: Mapped[Turn] = relationship("Turn", foreign_keys=[related_turn_id])
    related_node: Mapped[Node | None] = relationship("Node", foreign_keys=[related_node_id])
    related_edge: Mapped[Edge | None] = relationship("Edge", foreign_keys=[related_edge_id])

    def get_payload(self) -> dict[str, Any]:
        """Get payload as dictionary."""
        return json.loads(self.event_payload) if self.event_payload else {}

    def set_payload(self, payload: dict[str, Any]) -> None:
        """Set payload from dictionary."""
        self.event_payload = json.dumps(payload)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "eventType": self.event_type,
            "actor": self.actor,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.get_payload(),
            "relatedTurnId": self.related_turn_id,
            "relatedNodeId": self.related_node_id,
            "relatedEdgeId": self.related_edge_id,
        }
