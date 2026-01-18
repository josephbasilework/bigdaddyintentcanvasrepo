"""Turn logging helpers for session-scoped event persistence."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.database import AsyncSessionLocal
from app.models.event import Event
from app.models.session import WorkspaceSession
from app.models.turn import Turn, TurnActor, TurnType, resolve_response_type
from app.repositories.canvas import CanvasRepository as SyncCanvasRepository
from app.repositories.canvas_repo import CanvasRepository as AsyncCanvasRepository
from app.repositories.session_repo import AsyncSessionRepository, SessionRepository
from app.repositories.turn_repo import AsyncTurnRepository, TurnRepository
from app.schemas.event import EventResponse
from app.schemas.turn import TurnResponse
from app.services.events import (
    create_event_from_turn_async,
    create_event_from_turn_sync,
    resolve_event_type,
)
from app.services.user_data_store import get_user_data_store

logger = logging.getLogger(__name__)

DEFAULT_SESSION_LOOKBACK_HOURS = 24


def _coerce_workspace_id(workspace_id: int | str | None) -> int | None:
    if workspace_id is None:
        return None
    if isinstance(workspace_id, int):
        return workspace_id
    if isinstance(workspace_id, str) and workspace_id.isdigit():
        return int(workspace_id)
    return None


def resolve_session_id_sync(
    db: Session,
    *,
    user_id: str | None,
    workspace_id: int | str | None = None,
    session_id: str | None = None,
) -> str | None:
    """Resolve a session_id for logging, creating a session if needed."""
    if session_id:
        if user_id:
            session_repo = SessionRepository(db)
            session = session_repo.get_by_session_id(session_id)
            if session and session.user_id == user_id:
                session_repo.update_activity(session_id)
                return session_id
            resolved_workspace_id = _coerce_workspace_id(workspace_id)
            if session is None and resolved_workspace_id is not None:
                session = session_repo.create_session(
                    user_id=user_id,
                    workspace_id=resolved_workspace_id,
                    session_id=session_id,
                )
                return session.session_id
        return session_id

    if user_id is None:
        return None

    resolved_workspace_id = _coerce_workspace_id(workspace_id)
    session_repo = SessionRepository(db)
    if resolved_workspace_id is not None:
        session = session_repo.get_by_user_and_workspace(user_id, resolved_workspace_id)
        if session:
            session_repo.update_activity(session.session_id)
            return session.session_id
        session = session_repo.create_session(user_id=user_id, workspace_id=resolved_workspace_id)
        return session.session_id

    sessions = session_repo.get_active_sessions_for_user(
        user_id, max_age_hours=DEFAULT_SESSION_LOOKBACK_HOURS
    )
    if sessions:
        session_repo.update_activity(sessions[0].session_id)
        return sessions[0].session_id

    canvas_repo = SyncCanvasRepository(db)
    canvas = canvas_repo.get_by_user(user_id)
    if canvas:
        session = session_repo.create_session(user_id=user_id, workspace_id=canvas.id)
        return session.session_id

    return None


async def _get_latest_session_for_user(
    db: AsyncSession,
    user_id: str,
) -> WorkspaceSession | None:
    result = await db.execute(
        select(WorkspaceSession)
        .filter(WorkspaceSession.user_id == user_id)
        .order_by(WorkspaceSession.last_active_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def resolve_session_id_async(
    db: AsyncSession,
    *,
    user_id: str | None,
    workspace_id: int | str | None = None,
    session_id: str | None = None,
) -> str | None:
    """Resolve a session_id for logging, creating a session if needed."""
    if session_id:
        if user_id:
            session_repo = AsyncSessionRepository(db)
            session = await session_repo.get_by_session_id(session_id)
            if session and session.user_id == user_id:
                await session_repo.update_activity(session_id)
                return session_id
            resolved_workspace_id = _coerce_workspace_id(workspace_id)
            if session is None and resolved_workspace_id is not None:
                session = await session_repo.create_session(
                    user_id=user_id,
                    workspace_id=resolved_workspace_id,
                    session_id=session_id,
                )
                return session.session_id
        return session_id

    if user_id is None:
        return None

    resolved_workspace_id = _coerce_workspace_id(workspace_id)
    session_repo = AsyncSessionRepository(db)
    if resolved_workspace_id is not None:
        session = await session_repo.get_by_user_and_workspace(
            user_id, resolved_workspace_id
        )
        if session:
            await session_repo.update_activity(session.session_id)
            return session.session_id
        session = await session_repo.create_session(
            user_id=user_id, workspace_id=resolved_workspace_id
        )
        return session.session_id

    session = await _get_latest_session_for_user(db, user_id)
    if session:
        session.last_active_at = datetime.now(UTC)
        await db.commit()
        return session.session_id

    canvas_repo = AsyncCanvasRepository(db)
    canvases = await canvas_repo.get_by_user(user_id, limit=1)
    if canvases:
        session = await session_repo.create_session(
            user_id=user_id,
            workspace_id=canvases[0].id,
        )
        return session.session_id

    return None


def _normalize_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value)
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return None


def _extract_position(payload: dict[str, Any]) -> dict[str, Any] | None:
    position = payload.get("position")
    if isinstance(position, dict):
        return position
    return None


def _normalize_node_payload(
    payload: dict[str, Any],
    related_node_id: int | None,
) -> dict[str, Any] | None:
    candidate = payload
    nested = payload.get("node")
    if isinstance(nested, dict):
        candidate = nested

    node_id = (
        _normalize_id(candidate.get("id"))
        or _normalize_id(payload.get("node_id"))
        or _normalize_id(payload.get("nodeId"))
        or _normalize_id(related_node_id)
    )
    if node_id is None:
        return None

    position = _extract_position(candidate) or _extract_position(payload) or {}
    updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else {}

    x = candidate.get("x", position.get("x"))
    y = candidate.get("y", position.get("y"))
    z = candidate.get("z", position.get("z"))
    title = (
        candidate.get("title")
        or candidate.get("label")
        or updates.get("label")
        or updates.get("content")
    )
    content = candidate.get("content") or updates.get("content") or title
    metadata = candidate.get("metadata") or candidate.get("node_metadata")
    if metadata is None:
        metadata = candidate.get("nodeMetadata") or updates.get("metadata")

    return {
        "id": node_id,
        "type": candidate.get("type"),
        "title": title,
        "content": content,
        "x": x,
        "y": y,
        "z": z,
        "position": position or None,
        "metadata": metadata,
        "previous": payload.get("previous") or candidate.get("previous"),
        "updates": updates or None,
        "canvas_id": candidate.get("canvas_id") or candidate.get("canvasId"),
    }


def _normalize_edge_payload(
    payload: dict[str, Any],
    related_edge_id: int | None,
) -> dict[str, Any] | None:
    candidate = payload
    nested = payload.get("edge")
    if isinstance(nested, dict):
        candidate = nested

    edge_id = (
        _normalize_id(candidate.get("id"))
        or _normalize_id(payload.get("edge_id"))
        or _normalize_id(payload.get("edgeId"))
        or _normalize_id(related_edge_id)
    )
    if edge_id is None:
        return None

    from_node_id = (
        _normalize_id(candidate.get("from_node_id"))
        or _normalize_id(candidate.get("fromNodeId"))
        or _normalize_id(candidate.get("sourceNodeId"))
        or _normalize_id(payload.get("from_node_id"))
        or _normalize_id(payload.get("fromNodeId"))
    )
    to_node_id = (
        _normalize_id(candidate.get("to_node_id"))
        or _normalize_id(candidate.get("toNodeId"))
        or _normalize_id(candidate.get("targetNodeId"))
        or _normalize_id(payload.get("to_node_id"))
        or _normalize_id(payload.get("toNodeId"))
    )
    relation_type = candidate.get("relation_type") or candidate.get("relationType")
    if relation_type is None:
        relation_type = payload.get("relation_type") or payload.get("relationType")

    return {
        "id": edge_id,
        "from_node_id": from_node_id,
        "to_node_id": to_node_id,
        "fromNodeId": from_node_id,
        "toNodeId": to_node_id,
        "sourceNodeId": from_node_id,
        "targetNodeId": to_node_id,
        "relation_type": relation_type,
        "relationType": relation_type,
        "label": candidate.get("label") or payload.get("label"),
        "metadata": candidate.get("metadata") or payload.get("metadata"),
        "canvas_id": candidate.get("canvas_id") or candidate.get("canvasId"),
    }


def _build_turn_response(turn: Turn) -> TurnResponse:
    payload = turn.get_payload()
    response_type = resolve_response_type(turn.type, turn.actor, payload)
    event_type = resolve_event_type(turn.type, turn.actor, payload)
    return TurnResponse(
        id=turn.id,
        sessionId=turn.session_id,
        sequenceNumber=turn.sequence_number,
        timestamp=turn.timestamp.isoformat(),
        actor=getattr(turn.actor, "value", str(turn.actor)),
        type=getattr(turn.type, "value", str(turn.type)),
        summary=turn.summary,
        payload=payload,
        responseType=response_type.value if response_type else None,
        eventType=event_type,
        originSequenceNumber=turn.origin_sequence_number,
        relatedNodeId=turn.related_node_id,
        relatedEdgeId=turn.related_edge_id,
    )


def _build_event_response(event: Event) -> EventResponse:
    return EventResponse(**event.to_dict())


async def _broadcast_turn_updates_async(
    turn_response: TurnResponse,
    event_response: EventResponse | None,
    turn_type: TurnType,
    turn_payload: dict[str, Any],
    related_node_id: int | None,
    related_edge_id: int | None,
) -> None:
    from app.agui import (
        EdgeCreatedMessage,
        EdgeDeletedMessage,
        EdgeUpdatedMessage,
        EventCreatedMessage,
        NodeCreatedMessage,
        NodeDeletedMessage,
        NodeUpdatedMessage,
        TurnCreatedMessage,
    )
    from app.ws.websocket import manager

    await manager.broadcast_agui(TurnCreatedMessage(payload=turn_response))
    if event_response is not None:
        await manager.broadcast_agui(EventCreatedMessage(payload=event_response))

    if turn_type in {TurnType.NODE_CREATED, TurnType.NODE_UPDATED, TurnType.NODE_DELETED}:
        node_payload = _normalize_node_payload(turn_payload, related_node_id)
        if node_payload:
            if turn_type == TurnType.NODE_CREATED:
                await manager.broadcast_agui(NodeCreatedMessage(payload=node_payload))
            elif turn_type == TurnType.NODE_UPDATED:
                await manager.broadcast_agui(NodeUpdatedMessage(payload=node_payload))
            else:
                await manager.broadcast_agui(NodeDeletedMessage(payload=node_payload))

    if turn_type in {TurnType.EDGE_CREATED, TurnType.EDGE_UPDATED, TurnType.EDGE_DELETED}:
        edge_payload = _normalize_edge_payload(turn_payload, related_edge_id)
        if edge_payload:
            if turn_type == TurnType.EDGE_CREATED:
                await manager.broadcast_agui(EdgeCreatedMessage(payload=edge_payload))
            elif turn_type == TurnType.EDGE_UPDATED:
                await manager.broadcast_agui(EdgeUpdatedMessage(payload=edge_payload))
            else:
                await manager.broadcast_agui(EdgeDeletedMessage(payload=edge_payload))


def _broadcast_turn_updates_sync(
    turn_response: TurnResponse,
    event_response: EventResponse | None,
    turn_type: TurnType,
    turn_payload: dict[str, Any],
    related_node_id: int | None,
    related_edge_id: int | None,
) -> None:
    try:
        from anyio import from_thread

        from_thread.run(
            _broadcast_turn_updates_async,
            turn_response,
            event_response,
            turn_type,
            turn_payload,
            related_node_id,
            related_edge_id,
        )
    except RuntimeError:
        logger.debug("No event loop available for turn broadcast")
    except Exception:
        logger.warning("Failed to broadcast turn updates", exc_info=True)


def log_turn_with_session_id_sync(
    db: Session,
    *,
    session_id: str,
    actor: TurnActor,
    turn_type: TurnType,
    summary: str,
    payload: dict[str, Any] | None = None,
    related_node_id: int | None = None,
    related_edge_id: int | None = None,
    origin_sequence_number: int | None = None,
    sequence_number: int | None = None,
    client_request_id: str | None = None,
) -> Turn | None:
    """Create a turn for a known session_id, logging failures."""
    try:
        repo = TurnRepository(db)
        if client_request_id:
            existing = repo.get_turn_by_client_request_id(
                session_id, client_request_id
            )
            if existing:
                return existing
        turn = repo.create_turn(
            session_id=session_id,
            actor=actor,
            turn_type=turn_type,
            summary=summary,
            payload=payload,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
            origin_sequence_number=origin_sequence_number,
            sequence_number=sequence_number,
            client_request_id=client_request_id,
        )
        if client_request_id and getattr(turn, "_was_existing", False):
            return turn
        _persist_turn_snapshot_sync(db, session_id, turn)
        event = _emit_event_for_turn_sync(db, turn)
        turn_response = _build_turn_response(turn)
        event_response = _build_event_response(event) if event else None
        turn_payload = turn.get_payload()
        _broadcast_turn_updates_sync(
            turn_response,
            event_response,
            turn.type,
            turn_payload,
            related_node_id,
            related_edge_id,
        )
        return turn
    except Exception:
        logger.warning(
            "Failed to persist turn for session %s (%s)",
            session_id,
            turn_type,
            exc_info=True,
        )
        return None


def log_turn_for_user_sync(
    db: Session,
    *,
    user_id: str | None,
    workspace_id: int | str | None = None,
    session_id: str | None = None,
    actor: TurnActor,
    turn_type: TurnType,
    summary: str,
    payload: dict[str, Any] | None = None,
    related_node_id: int | None = None,
    related_edge_id: int | None = None,
    origin_sequence_number: int | None = None,
    sequence_number: int | None = None,
    client_request_id: str | None = None,
) -> Turn | None:
    """Resolve session and log a turn, logging failures."""
    resolved_session_id = resolve_session_id_sync(
        db,
        user_id=user_id,
        workspace_id=workspace_id,
        session_id=session_id,
    )
    if not resolved_session_id:
        logger.warning("No session_id available for turn %s", turn_type)
        return None
    return log_turn_with_session_id_sync(
        db,
        session_id=resolved_session_id,
        actor=actor,
        turn_type=turn_type,
        summary=summary,
        payload=payload,
        related_node_id=related_node_id,
        related_edge_id=related_edge_id,
        origin_sequence_number=origin_sequence_number,
        sequence_number=sequence_number,
        client_request_id=client_request_id,
    )


async def log_turn_with_session_id_async(
    db: AsyncSession,
    *,
    session_id: str,
    actor: TurnActor,
    turn_type: TurnType,
    summary: str,
    payload: dict[str, Any] | None = None,
    related_node_id: int | None = None,
    related_edge_id: int | None = None,
    origin_sequence_number: int | None = None,
    sequence_number: int | None = None,
    client_request_id: str | None = None,
) -> Turn | None:
    """Create a turn for a known session_id, logging failures."""
    try:
        repo = AsyncTurnRepository(db)
        if client_request_id:
            existing = await repo.get_turn_by_client_request_id(
                session_id, client_request_id
            )
            if existing:
                return existing
        turn = await repo.create_turn(
            session_id=session_id,
            actor=actor,
            turn_type=turn_type,
            summary=summary,
            payload=payload,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
            origin_sequence_number=origin_sequence_number,
            sequence_number=sequence_number,
            client_request_id=client_request_id,
        )
        if client_request_id and getattr(turn, "_was_existing", False):
            return turn
        await _persist_turn_snapshot_async(db, session_id, turn)
        event = await _emit_event_for_turn_async(db, turn)
        turn_response = _build_turn_response(turn)
        event_response = _build_event_response(event) if event else None
        turn_payload = turn.get_payload()
        await _broadcast_turn_updates_async(
            turn_response,
            event_response,
            turn.type,
            turn_payload,
            related_node_id,
            related_edge_id,
        )
        return turn
    except Exception:
        logger.warning(
            "Failed to persist turn for session %s (%s)",
            session_id,
            turn_type,
            exc_info=True,
        )
        return None


async def log_turn_for_user_async(
    db: AsyncSession,
    *,
    user_id: str | None,
    workspace_id: int | str | None = None,
    session_id: str | None = None,
    actor: TurnActor,
    turn_type: TurnType,
    summary: str,
    payload: dict[str, Any] | None = None,
    related_node_id: int | None = None,
    related_edge_id: int | None = None,
    origin_sequence_number: int | None = None,
    sequence_number: int | None = None,
    client_request_id: str | None = None,
) -> Turn | None:
    """Resolve session and log a turn, logging failures."""
    resolved_session_id = await resolve_session_id_async(
        db,
        user_id=user_id,
        workspace_id=workspace_id,
        session_id=session_id,
    )
    if not resolved_session_id:
        logger.warning("No session_id available for turn %s", turn_type)
        return None
    return await log_turn_with_session_id_async(
        db,
        session_id=resolved_session_id,
        actor=actor,
        turn_type=turn_type,
        summary=summary,
        payload=payload,
        related_node_id=related_node_id,
        related_edge_id=related_edge_id,
        origin_sequence_number=origin_sequence_number,
        sequence_number=sequence_number,
        client_request_id=client_request_id,
    )


async def log_turn_with_new_async_session(
    *,
    session_id: str,
    actor: TurnActor,
    turn_type: TurnType,
    summary: str,
    payload: dict[str, Any] | None = None,
    related_node_id: int | None = None,
    related_edge_id: int | None = None,
    origin_sequence_number: int | None = None,
    sequence_number: int | None = None,
    client_request_id: str | None = None,
) -> Turn | None:
    """Log a turn using a new AsyncSessionLocal session."""
    async with AsyncSessionLocal() as db:
        return await log_turn_with_session_id_async(
            db,
            session_id=session_id,
            actor=actor,
            turn_type=turn_type,
            summary=summary,
            payload=payload,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
            origin_sequence_number=origin_sequence_number,
            sequence_number=sequence_number,
            client_request_id=client_request_id,
        )


def _persist_turn_snapshot_sync(db: Session, session_id: str, turn: Turn) -> None:
    session_repo = SessionRepository(db)
    session = session_repo.get_by_session_id(session_id)
    if session is None:
        return
    try:
        data_store = get_user_data_store()
        data_store.persist_turn(
            user_id=session.user_id or "default",
            session_id=session.session_id,
            sequence_number=turn.sequence_number,
            origin_sequence_number=turn.origin_sequence_number,
            actor=getattr(turn.actor, "value", str(turn.actor)),
            turn_type=getattr(turn.type, "value", str(turn.type)),
            summary=turn.summary,
            payload=turn.get_payload(),
            timestamp=turn.timestamp.isoformat(),
            workspace_id=session.workspace_id,
            related_node_id=turn.related_node_id,
            related_edge_id=turn.related_edge_id,
        )
    except Exception:
        logger.warning(
            "Failed to persist turn snapshot for session %s", session_id, exc_info=True
        )


async def _persist_turn_snapshot_async(
    db: AsyncSession, session_id: str, turn: Turn
) -> None:
    session_repo = AsyncSessionRepository(db)
    session = await session_repo.get_by_session_id(session_id)
    if session is None:
        return
    data_store = get_user_data_store()
    try:
        await asyncio.to_thread(
            data_store.persist_turn,
            user_id=session.user_id or "default",
            session_id=session.session_id,
            sequence_number=turn.sequence_number,
            origin_sequence_number=turn.origin_sequence_number,
            actor=getattr(turn.actor, "value", str(turn.actor)),
            turn_type=getattr(turn.type, "value", str(turn.type)),
            summary=turn.summary,
            payload=turn.get_payload(),
            timestamp=turn.timestamp.isoformat(),
            workspace_id=session.workspace_id,
            related_node_id=turn.related_node_id,
            related_edge_id=turn.related_edge_id,
        )
    except Exception:
        logger.warning(
            "Failed to persist turn snapshot for session %s", session_id, exc_info=True
        )


def _emit_event_for_turn_sync(db: Session, turn: Turn) -> Event | None:
    try:
        return create_event_from_turn_sync(db, turn=turn)
    except Exception:
        logger.warning(
            "Failed to emit event for turn %s",
            turn.id,
            exc_info=True,
        )
    return None


async def _emit_event_for_turn_async(db: AsyncSession, turn: Turn) -> Event | None:
    try:
        return await create_event_from_turn_async(db, turn=turn)
    except Exception:
        logger.warning(
            "Failed to emit event for turn %s",
            turn.id,
            exc_info=True,
        )
    return None
