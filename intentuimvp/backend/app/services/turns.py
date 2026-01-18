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
from app.models.session import WorkspaceSession
from app.models.turn import Turn, TurnActor, TurnType
from app.repositories.canvas import CanvasRepository as SyncCanvasRepository
from app.repositories.canvas_repo import CanvasRepository as AsyncCanvasRepository
from app.repositories.session_repo import AsyncSessionRepository, SessionRepository
from app.repositories.turn_repo import AsyncTurnRepository, TurnRepository
from app.services.events import create_event_from_turn_async, create_event_from_turn_sync
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
) -> Turn | None:
    """Create a turn for a known session_id, logging failures."""
    try:
        repo = TurnRepository(db)
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
        )
        _persist_turn_snapshot_sync(db, session_id, turn)
        _emit_event_for_turn_sync(db, turn)
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
) -> Turn | None:
    """Create a turn for a known session_id, logging failures."""
    try:
        repo = AsyncTurnRepository(db)
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
        )
        await _persist_turn_snapshot_async(db, session_id, turn)
        await _emit_event_for_turn_async(db, turn)
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


def _emit_event_for_turn_sync(db: Session, turn: Turn) -> None:
    try:
        create_event_from_turn_sync(db, turn=turn)
    except Exception:
        logger.warning(
            "Failed to emit event for turn %s",
            turn.id,
            exc_info=True,
        )


async def _emit_event_for_turn_async(db: AsyncSession, turn: Turn) -> None:
    try:
        await create_event_from_turn_async(db, turn=turn)
    except Exception:
        logger.warning(
            "Failed to emit event for turn %s",
            turn.id,
            exc_info=True,
        )
