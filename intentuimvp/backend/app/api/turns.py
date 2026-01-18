"""Turn query API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models.turn import TurnActor, TurnType
from app.repositories.turn_repo import AsyncTurnRepository
from app.schemas.turn import TurnListResponse, TurnResponse
from app.services.events import resolve_event_type

router = APIRouter()


@router.get("/api/turns", response_model=TurnListResponse)
async def list_turns(
    session_id: str = Query(..., description="Session ID to fetch turns for"),
    actor: TurnActor | None = Query(
        default=None, description="Optional actor filter"
    ),
    turn_type: TurnType | None = Query(
        default=None,
        alias="type",
        description="Optional turn type filter",
    ),
    after_sequence: int | None = Query(
        default=None,
        ge=0,
        description="Optional sequence number to start after (exclusive)",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Max turns to return",
    ),
    db: AsyncSession = Depends(get_async_db),
) -> TurnListResponse:
    """List turns for a session with optional filters."""
    repo = AsyncTurnRepository(db)
    turns = await repo.get_turns_for_session(
        session_id=session_id,
        limit=limit,
        after_sequence=after_sequence,
        actor=actor,
        turn_type=turn_type,
    )
    return TurnListResponse(
        turns=[
            TurnResponse(
                **{
                    **turn.to_dict(),
                    "eventType": resolve_event_type(
                        turn.type, turn.actor, turn.get_payload()
                    ),
                }
            )
            for turn in turns
        ],
        count=len(turns),
    )
