"""Unified event mapping and emission helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.turn import ResponseType, Turn, TurnActor, TurnType, resolve_response_type
from app.repositories.event_repo import AsyncEventRepository, EventRepository

EVENT_TYPE_MAP: dict[TurnType, str] = {
    TurnType.USER_INPUT: "intent.parsed",
    TurnType.USER_CANVAS_ACTION: "canvas.action",
    TurnType.NODE_CREATED: "node.created",
    TurnType.NODE_UPDATED: "node.updated",
    TurnType.NODE_DELETED: "node.deleted",
    TurnType.EDGE_CREATED: "edge.created",
    TurnType.EDGE_UPDATED: "edge.updated",
    TurnType.EDGE_DELETED: "edge.deleted",
    TurnType.JOB_STARTED: "job.started",
    TurnType.JOB_PROGRESS: "job.progress",
    TurnType.JOB_COMPLETED: "job.completed",
    TurnType.JOB_FAILED: "job.failed",
    TurnType.ASSUMPTION_PRESENTED: "assumption.presented",
    TurnType.ASSUMPTION_CONFIRMED: "assumption.confirmed",
    TurnType.ASSUMPTION_REJECTED: "assumption.rejected",
    TurnType.ASSUMPTION_MODIFIED: "assumption.modified",
    TurnType.MCP_TOOL_INVOKED: "tool.invoked",
    TurnType.MCP_TOOL_RESULT: "tool.result",
    TurnType.EXTERNAL_STATE_CHANGE: "external.updated",
    TurnType.HOOK_FIRED: "hook.fired",
    TurnType.HOOK_FAILED: "hook.failed",
}

RESPONSE_EVENT_TYPE_MAP: dict[ResponseType, str] = {
    ResponseType.CONVERSATIONAL: "response.conversational",
    ResponseType.PROPOSAL: "response.proposal",
    ResponseType.CLARIFICATION: "response.clarification",
    ResponseType.ACKNOWLEDGMENT: "response.acknowledgment",
    ResponseType.TOOL_INVOCATION: "response.tool_invocation",
}

RESPONSE_TURN_TYPES = {TurnType.AGENT_RESPONSE, TurnType.SYSTEM_MESSAGE}


def _normalize_turn_type(turn_type: TurnType | str) -> TurnType | None:
    if isinstance(turn_type, TurnType):
        return turn_type
    if isinstance(turn_type, str):
        try:
            return TurnType(turn_type)
        except ValueError:
            return None
    return None


def _normalize_actor(actor: TurnActor | str) -> str:
    return getattr(actor, "value", str(actor))


def resolve_event_type(
    turn_type: TurnType | str,
    actor: TurnActor | str,
    payload: dict[str, Any] | None,
) -> str:
    """Resolve the unified event type for a turn."""
    resolved_turn_type = _normalize_turn_type(turn_type)

    if resolved_turn_type in EVENT_TYPE_MAP:
        return EVENT_TYPE_MAP[resolved_turn_type]

    if resolved_turn_type in RESPONSE_TURN_TYPES:
        response_type = resolve_response_type(
            resolved_turn_type,
            actor,
            payload or {},
        )
        if response_type:
            return RESPONSE_EVENT_TYPE_MAP.get(
                response_type, f"response.{response_type.value}"
            )

    raw_type = (
        resolved_turn_type.value if resolved_turn_type is not None else str(turn_type)
    )
    return raw_type.replace("_", ".")


def create_event_from_turn_sync(
    db: Session,
    *,
    turn: Turn,
    payload: dict[str, Any] | None = None,
) -> Event:
    """Create an event record derived from a persisted turn."""
    event_payload = payload if payload is not None else turn.get_payload()
    event_type = resolve_event_type(turn.type, turn.actor, event_payload)
    repo = EventRepository(db)
    return repo.create_event(
        event_type=event_type,
        actor=_normalize_actor(turn.actor),
        related_turn_id=turn.id,
        payload=event_payload,
        related_node_id=turn.related_node_id,
        related_edge_id=turn.related_edge_id,
        timestamp=turn.timestamp,
    )


async def create_event_from_turn_async(
    db: AsyncSession,
    *,
    turn: Turn,
    payload: dict[str, Any] | None = None,
) -> Event:
    """Async event creation derived from a persisted turn."""
    event_payload = payload if payload is not None else turn.get_payload()
    event_type = resolve_event_type(turn.type, turn.actor, event_payload)
    repo = AsyncEventRepository(db)
    return await repo.create_event(
        event_type=event_type,
        actor=_normalize_actor(turn.actor),
        related_turn_id=turn.id,
        payload=event_payload,
        related_node_id=turn.related_node_id,
        related_edge_id=turn.related_edge_id,
        timestamp=turn.timestamp,
    )
