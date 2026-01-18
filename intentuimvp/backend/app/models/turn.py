"""SQLAlchemy model for turn table.

A Turn represents any state change in the system: user input, canvas CRUD operations,
job lifecycle events, system responses, and assumption reconciliation.

Turns are forward-only (append-only) and grow indefinitely - no branching or undo at DB level.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.edge import Edge
    from app.models.node import Node


class TurnActor(str, Enum):
    """Enumeration of actors that can create turns."""

    USER = "user"  # Human user input
    SYSTEM = "system"  # System-generated events (canvas CRUD, job lifecycle)
    AGENT = "agent"  # AI agent responses and actions
    MCP = "mcp"  # MCP tool invocations


class TurnType(str, Enum):
    """Enumeration of turn types representing different state changes."""

    # User interactions
    USER_INPUT = "user_input"  # User command/query input
    USER_CANVAS_ACTION = "user_canvas_action"  # User-initiated canvas modification

    # Canvas CRUD operations
    NODE_CREATED = "node_created"
    NODE_UPDATED = "node_updated"
    NODE_DELETED = "node_deleted"
    EDGE_CREATED = "edge_created"
    EDGE_UPDATED = "edge_updated"
    EDGE_DELETED = "edge_deleted"

    # Job lifecycle
    JOB_STARTED = "job_started"
    JOB_PROGRESS = "job_progress"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"

    # Agent/system responses
    AGENT_RESPONSE = "agent_response"
    SYSTEM_MESSAGE = "system_message"
    EXTERNAL_STATE_CHANGE = "external_state_change"

    # Assumption reconciliation (FR-003)
    ASSUMPTION_PRESENTED = "assumption_presented"
    ASSUMPTION_CONFIRMED = "assumption_confirmed"
    ASSUMPTION_REJECTED = "assumption_rejected"
    ASSUMPTION_MODIFIED = "assumption_modified"

    # MCP operations
    MCP_TOOL_INVOKED = "mcp_tool_invoked"
    MCP_TOOL_RESULT = "mcp_tool_result"


class ResponseType(str, Enum):
    """Enumeration of response types for system/agent responses."""

    CONVERSATIONAL = "conversational"
    PROPOSAL = "proposal"
    CLARIFICATION = "clarification"
    ACKNOWLEDGMENT = "acknowledgment"
    TOOL_INVOCATION = "tool_invocation"


_RESPONSE_TYPE_ALIASES = {
    "acknowledgement": ResponseType.ACKNOWLEDGMENT.value,
    "tool": ResponseType.TOOL_INVOCATION.value,
    "tool-invocation": ResponseType.TOOL_INVOCATION.value,
    "tool_invocation": ResponseType.TOOL_INVOCATION.value,
}


def _normalize_response_type(value: Any) -> ResponseType | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("-", "_")
    normalized = _RESPONSE_TYPE_ALIASES.get(normalized, normalized)
    try:
        return ResponseType(normalized)
    except ValueError:
        return None


def _response_type_from_payload(payload: dict[str, Any]) -> ResponseType | None:
    for key in ("response_type", "responseType"):
        if key not in payload:
            continue
        resolved = _normalize_response_type(payload.get(key))
        if resolved:
            return resolved
    return None


def _request_type_to_response_type(value: str) -> ResponseType | None:
    normalized = value.strip().lower()
    if normalized == "confirmation":
        return ResponseType.PROPOSAL
    if normalized in {"input", "choice", "file"}:
        return ResponseType.CLARIFICATION
    return None


def _has_non_empty_list(payload: dict[str, Any], keys: list[str]) -> bool:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def resolve_response_type(
    turn_type: TurnType,
    actor: TurnActor | str,
    payload: dict[str, Any],
) -> ResponseType | None:
    """Resolve response type from explicit payload or turn context."""
    explicit = _response_type_from_payload(payload)
    if explicit:
        return explicit

    nested = payload.get("result")
    if isinstance(nested, dict):
        nested_response = _response_type_from_payload(nested)
        if nested_response:
            return nested_response
        nested_request_type = nested.get("request_type") or nested.get("requestType")
        if isinstance(nested_request_type, str):
            request_response = _request_type_to_response_type(nested_request_type)
            if request_response:
                return request_response
        if _has_non_empty_list(nested, ["clarifying_questions", "clarifyingQuestions"]):
            return ResponseType.CLARIFICATION
        if _has_non_empty_list(nested, ["assumptions"]):
            return ResponseType.PROPOSAL

    request_type = payload.get("request_type") or payload.get("requestType")
    if isinstance(request_type, str):
        request_response = _request_type_to_response_type(request_type)
        if request_response:
            return request_response

    if _has_non_empty_list(payload, ["clarifying_questions", "clarifyingQuestions"]):
        return ResponseType.CLARIFICATION
    if _has_non_empty_list(payload, ["assumptions"]):
        return ResponseType.PROPOSAL

    if turn_type == TurnType.ASSUMPTION_PRESENTED:
        return ResponseType.PROPOSAL
    if turn_type in {TurnType.MCP_TOOL_INVOKED, TurnType.MCP_TOOL_RESULT}:
        return ResponseType.TOOL_INVOCATION
    if turn_type == TurnType.AGENT_RESPONSE:
        return ResponseType.CONVERSATIONAL
    if turn_type in {TurnType.SYSTEM_MESSAGE, TurnType.EXTERNAL_STATE_CHANGE}:
        return ResponseType.ACKNOWLEDGMENT

    return None


class Turn(Base):
    """Turn model representing a single state change event.

    Turns form an append-only log of all state changes in a session.
    They enable session replay, audit trails, and context reconstruction.

    Attributes:
        id: Unique identifier (auto-increment primary key)
        session_id: Identifier for the session/conversation this turn belongs to
        sequence_number: Monotonic sequence number within the session
        timestamp: When this turn occurred
        actor: Who/what created this turn (user, system, agent, mcp)
        type: Type of state change this turn represents
        summary: Human-readable summary of the turn
        payload: JSON object with turn-specific data
        related_node_id: Optional reference to a node involved in this turn
        related_edge_id: Optional reference to an edge involved in this turn
    """

    __tablename__ = "turn"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Session and sequencing
    session_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True, comment="Session/conversation identifier"
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Monotonic sequence number within session"
    )

    # Timing
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When this turn occurred",
    )

    # Turn classification
    actor: Mapped[TurnActor] = mapped_column(
        String,
        nullable=False,
        index=True,
        default=TurnActor.USER,
        comment="Who/what created this turn",
    )
    type: Mapped[TurnType] = mapped_column(
        String, nullable=False, index=True, comment="Type of state change"
    )

    # Content
    summary: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Human-readable summary of the turn"
    )
    turn_payload: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON object with turn-specific data"
    )

    # Related entities (optional foreign keys for canvas relationships)
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

    # Relationships
    related_node: Mapped[Node | None] = relationship("Node", foreign_keys=[related_node_id])
    related_edge: Mapped[Edge | None] = relationship("Edge", foreign_keys=[related_edge_id])

    # JSON payload helpers
    def get_payload(self) -> dict[str, Any]:
        """Get payload as dictionary."""
        return json.loads(self.turn_payload) if self.turn_payload else {}

    def set_payload(self, payload: dict[str, Any]) -> None:
        """Set payload from dictionary."""
        self.turn_payload = json.dumps(payload)

    def get_response_type(self) -> ResponseType | None:
        """Get response type for this turn if applicable."""
        return resolve_response_type(self.type, self.actor, self.get_payload())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        response_type = self.get_response_type()
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "sequenceNumber": self.sequence_number,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "type": self.type,
            "summary": self.summary,
            "payload": self.get_payload(),
            "responseType": response_type.value if response_type else None,
            "relatedNodeId": self.related_node_id,
            "relatedEdgeId": self.related_edge_id,
        }

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<Turn(id={self.id}, session={self.session_id}, "
            f"seq={self.sequence_number}, actor={self.actor}, type={self.type})>"
        )
