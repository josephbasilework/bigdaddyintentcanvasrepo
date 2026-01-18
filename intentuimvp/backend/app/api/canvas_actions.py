"""Canvas action API endpoint for lightweight CRUD turn logging."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.turn import TurnActor, TurnType
from app.repositories.turn_repo import TurnRepository
from app.schemas.canvas_action import CanvasActionRequest, CanvasActionResponse, CanvasActionType
from app.services.events import resolve_event_type
from app.services.turns import log_turn_with_session_id_sync, resolve_session_id_sync

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user() -> str:
    """Get current user from authentication (MVP stub)."""
    return "default_user"


_NODE_ACTIONS = {
    CanvasActionType.NODE_CREATED,
    CanvasActionType.NODE_UPDATED,
    CanvasActionType.NODE_DELETED,
}
_EDGE_ACTIONS = {
    CanvasActionType.EDGE_CREATED,
    CanvasActionType.EDGE_UPDATED,
    CanvasActionType.EDGE_DELETED,
}


def _coerce_related_id(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _extract_related_id(payload: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        if key not in payload:
            continue
        candidate = _coerce_related_id(payload.get(key))
        if candidate is not None:
            return candidate
    return None


def _extract_node_id(payload: dict[str, Any]) -> int | None:
    nested = payload.get("node")
    if isinstance(nested, dict):
        found = _extract_related_id(nested, ["id", "node_id", "nodeId"])
        if found is not None:
            return found
    return _extract_related_id(payload, ["node_id", "nodeId", "id"])


def _extract_edge_id(payload: dict[str, Any]) -> int | None:
    nested = payload.get("edge")
    if isinstance(nested, dict):
        found = _extract_related_id(nested, ["id", "edge_id", "edgeId"])
        if found is not None:
            return found
    return _extract_related_id(payload, ["edge_id", "edgeId", "id"])


def _extract_label(payload: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                return trimmed
    return None


def _default_summary(action: CanvasActionType, payload: dict[str, Any]) -> str:
    label = None
    if action in _NODE_ACTIONS:
        nested = payload.get("node")
        if isinstance(nested, dict):
            label = _extract_label(nested, ["title", "label", "content"])
        if label is None:
            label = _extract_label(payload, ["title", "label", "content"])
    elif action in _EDGE_ACTIONS:
        nested = payload.get("edge")
        if isinstance(nested, dict):
            label = _extract_label(nested, ["label"])
        if label is None:
            label = _extract_label(payload, ["label"])

    if action == CanvasActionType.NODE_CREATED:
        base = "Node created"
    elif action == CanvasActionType.NODE_UPDATED:
        base = "Node updated"
    elif action == CanvasActionType.NODE_DELETED:
        base = "Node deleted"
    elif action == CanvasActionType.EDGE_CREATED:
        base = "Edge created"
    elif action == CanvasActionType.EDGE_UPDATED:
        base = "Edge updated"
    else:
        base = "Edge deleted"

    return f"{base}: {label}" if label else base


def _resolve_origin_sequence(
    db: Session,
    session_id: str,
    action: CanvasActionType,
    related_node_id: int | None,
    related_edge_id: int | None,
) -> int | None:
    repo = TurnRepository(db)
    if related_node_id is not None and action in {
        CanvasActionType.NODE_UPDATED,
        CanvasActionType.NODE_DELETED,
    }:
        origin = repo.get_latest_turn_for_node(
            session_id,
            related_node_id,
            turn_types=[TurnType.NODE_CREATED, TurnType.NODE_UPDATED],
        )
        return origin.sequence_number if origin else None
    if related_edge_id is not None and action in {
        CanvasActionType.EDGE_UPDATED,
        CanvasActionType.EDGE_DELETED,
    }:
        origin = repo.get_latest_turn_for_edge(
            session_id,
            related_edge_id,
            turn_types=[TurnType.EDGE_CREATED, TurnType.EDGE_UPDATED],
        )
        return origin.sequence_number if origin else None
    return None


@router.post(
    "/api/canvas/actions",
    response_model=CanvasActionResponse,
    status_code=status.HTTP_201_CREATED,
)
def log_canvas_action(
    payload: CanvasActionRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> CanvasActionResponse:
    """Log a lightweight canvas CRUD action as a turn/event."""
    resolved_session_id = resolve_session_id_sync(
        db,
        user_id=user_id,
        workspace_id=payload.workspace_id,
        session_id=payload.session_id,
    )
    if not resolved_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to resolve session for canvas action",
        )

    turn_type = TurnType(payload.action.value)
    related_node_id = (
        _extract_node_id(payload.payload)
        if payload.action in _NODE_ACTIONS
        else None
    )
    related_edge_id = (
        _extract_edge_id(payload.payload)
        if payload.action in _EDGE_ACTIONS
        else None
    )
    origin_sequence_number = _resolve_origin_sequence(
        db,
        resolved_session_id,
        payload.action,
        related_node_id,
        related_edge_id,
    )
    summary = payload.summary or _default_summary(payload.action, payload.payload)

    turn = log_turn_with_session_id_sync(
        db,
        session_id=resolved_session_id,
        actor=TurnActor.USER,
        turn_type=turn_type,
        summary=summary,
        payload=payload.payload,
        related_node_id=related_node_id,
        related_edge_id=related_edge_id,
        origin_sequence_number=origin_sequence_number,
        client_request_id=payload.client_request_id,
    )
    if not turn:
        logger.error(
            "Failed to persist canvas action turn for session %s", resolved_session_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log canvas action",
        )

    event_type = resolve_event_type(turn.type, turn.actor, turn.get_payload())
    return CanvasActionResponse(
        status="logged",
        turnId=turn.id,
        sessionId=turn.session_id,
        sequenceNumber=turn.sequence_number,
        eventType=event_type,
    )
