"""Helpers for turn filtering and categorization."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.turn import ResponseType, Turn, TurnType, resolve_response_type
from app.services.events import EVENT_TYPE_MAP, RESPONSE_EVENT_TYPE_MAP

INPUT_TURN_TYPES = {TurnType.USER_INPUT, TurnType.USER_CANVAS_ACTION}
CRUD_TURN_TYPES = {
    TurnType.NODE_CREATED,
    TurnType.NODE_UPDATED,
    TurnType.NODE_DELETED,
    TurnType.EDGE_CREATED,
    TurnType.EDGE_UPDATED,
    TurnType.EDGE_DELETED,
}
JOB_TURN_TYPES = {
    TurnType.JOB_STARTED,
    TurnType.JOB_PROGRESS,
    TurnType.JOB_COMPLETED,
    TurnType.JOB_FAILED,
}
RESPONSE_MESSAGE_TURN_TYPES = {TurnType.AGENT_RESPONSE, TurnType.SYSTEM_MESSAGE}
RESPONSE_TURN_TYPES = RESPONSE_MESSAGE_TURN_TYPES | {
    TurnType.ASSUMPTION_CONFIRMED,
    TurnType.ASSUMPTION_REJECTED,
    TurnType.ASSUMPTION_MODIFIED,
    TurnType.MCP_TOOL_INVOKED,
    TurnType.MCP_TOOL_RESULT,
    TurnType.EXTERNAL_STATE_CHANGE,
}
PROPOSAL_TURN_TYPES = {TurnType.ASSUMPTION_PRESENTED}

CATEGORY_TURN_TYPES = {
    "input": INPUT_TURN_TYPES,
    "crud": CRUD_TURN_TYPES,
    "proposal": PROPOSAL_TURN_TYPES | RESPONSE_MESSAGE_TURN_TYPES,
    "response": RESPONSE_TURN_TYPES,
}

EVENT_TYPE_TO_TURN_TYPES: dict[str, set[TurnType]] = {}
for turn_type, event_type in EVENT_TYPE_MAP.items():
    EVENT_TYPE_TO_TURN_TYPES.setdefault(event_type, set()).add(turn_type)

RESPONSE_EVENT_TYPE_TO_RESPONSE_TYPE = {
    event_type: response_type
    for response_type, event_type in RESPONSE_EVENT_TYPE_MAP.items()
}


def normalize_filter_values(values: Iterable[str] | None) -> list[str]:
    """Normalize query filter values to lowercase strings."""
    if not values:
        return []
    normalized: list[str] = []
    for value in values:
        if not value:
            continue
        cleaned = value.strip().lower()
        if cleaned:
            normalized.append(cleaned)
    return sorted(set(normalized))


def map_categories_to_turn_types(categories: list[str]) -> set[TurnType]:
    """Map category filters to possible turn types."""
    turn_types: set[TurnType] = set()
    for category in categories:
        mapped = CATEGORY_TURN_TYPES.get(category)
        if mapped:
            turn_types |= mapped
    return turn_types


def map_event_types_to_turn_types(event_types: list[str]) -> set[TurnType]:
    """Map event type filters to possible turn types."""
    turn_types: set[TurnType] = set()
    for event_type in event_types:
        mapped = EVENT_TYPE_TO_TURN_TYPES.get(event_type)
        if mapped:
            turn_types |= mapped
            continue
        if event_type in RESPONSE_EVENT_TYPE_TO_RESPONSE_TYPE:
            turn_types |= RESPONSE_MESSAGE_TURN_TYPES
            continue
        if event_type:
            candidate = event_type.replace(".", "_")
            try:
                turn_types.add(TurnType(candidate))
            except ValueError:
                continue
    return turn_types


def resolve_turn_category(turn: Turn) -> str:
    """Resolve the high-level category for a turn."""
    response_type = resolve_response_type(
        turn.type,
        turn.actor,
        turn.get_payload(),
    )
    resolved_type = _normalize_turn_type(turn.type)
    if response_type == ResponseType.PROPOSAL:
        return "proposal"
    if response_type:
        return "response"
    if resolved_type in CRUD_TURN_TYPES:
        return "crud"
    if resolved_type in INPUT_TURN_TYPES:
        return "input"
    if resolved_type in PROPOSAL_TURN_TYPES:
        return "proposal"
    if resolved_type in RESPONSE_TURN_TYPES:
        return "response"
    return "other"


def _normalize_turn_type(turn_type: TurnType | str) -> TurnType | None:
    if isinstance(turn_type, TurnType):
        return turn_type
    if isinstance(turn_type, str):
        try:
            return TurnType(turn_type)
        except ValueError:
            return None
    return None
