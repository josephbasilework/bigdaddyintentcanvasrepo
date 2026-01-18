"""Turn query API endpoints."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models.turn import Turn, TurnActor, TurnType
from app.repositories.turn_repo import AsyncTurnRepository
from app.schemas.turn import TurnListResponse, TurnResponse
from app.services.events import resolve_event_type
from app.services.turn_filters import (
    map_categories_to_turn_types,
    map_event_types_to_turn_types,
    normalize_filter_values,
    resolve_turn_category,
)

router = APIRouter()

ALLOWED_ACTOR_GROUPS = {"user", "system", "job", "external"}
ALLOWED_CATEGORIES = {"input", "response", "proposal", "crud", "other"}


def _build_turn_type_filter(
    turn_type: TurnType | None,
    categories: list[str],
    event_types: list[str],
) -> set[TurnType] | None:
    turn_types: set[TurnType] | None = None
    if categories:
        category_turn_types = map_categories_to_turn_types(categories)
        if not category_turn_types:
            return set()
        turn_types = category_turn_types if turn_types is None else turn_types & category_turn_types
    if event_types:
        event_turn_types = map_event_types_to_turn_types(event_types)
        if not event_turn_types:
            return set()
        turn_types = event_turn_types if turn_types is None else turn_types & event_turn_types
    if turn_type is not None:
        turn_types = {turn_type} if turn_types is None else turn_types & {turn_type}
    return turn_types


def _build_post_filter(
    categories: list[str],
    event_types: list[str],
) -> Callable[[Turn], bool] | None:
    if not categories and not event_types:
        return None
    category_set = set(categories) if categories else None
    event_type_set = set(event_types) if event_types else None

    def predicate(turn: Turn) -> bool:
        if category_set and resolve_turn_category(turn) not in category_set:
            return False
        if event_type_set:
            resolved = resolve_event_type(
                turn.type,
                turn.actor,
                turn.get_payload(),
            ).lower()
            if resolved not in event_type_set:
                return False
        return True

    return predicate


async def _fetch_turns_with_post_filter(
    repo: AsyncTurnRepository,
    *,
    session_id: str,
    limit: int,
    after_sequence: int | None,
    actor: TurnActor | None,
    actor_groups: list[str] | None,
    turn_types: list[TurnType] | None,
    related_node_id: int | None,
    related_edge_id: int | None,
    post_filter: Callable[[Turn], bool],
) -> list[Turn]:
    results = []
    current_after = after_sequence
    page_size = min(500, max(limit, 200))

    while True:
        page = await repo.get_turns_for_session(
            session_id=session_id,
            limit=page_size,
            after_sequence=current_after,
            actor=actor,
            turn_types=turn_types,
            actor_groups=actor_groups,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
        )
        if not page:
            break

        current_after = page[-1].sequence_number
        for turn in page:
            if post_filter(turn):
                results.append(turn)
                if len(results) >= limit:
                    return results[:limit]

        if len(page) < page_size:
            break

    return results


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
    actor_group: list[str] | None = Query(
        default=None,
        description="Optional actor group filters",
    ),
    category: list[str] | None = Query(
        default=None,
        description="Optional category filters",
    ),
    event_type: list[str] | None = Query(
        default=None,
        description="Optional event type filters",
    ),
    related_node_id: int | None = Query(
        default=None,
        description="Optional related node filter",
    ),
    related_edge_id: int | None = Query(
        default=None,
        description="Optional related edge filter",
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
    actor_groups = None
    if actor_group is not None:
        actor_groups = [
            group
            for group in normalize_filter_values(actor_group)
            if group in ALLOWED_ACTOR_GROUPS
        ]
        if not actor_groups:
            return TurnListResponse(turns=[], count=0)

    categories = []
    if category is not None:
        categories = [
            value
            for value in normalize_filter_values(category)
            if value in ALLOWED_CATEGORIES
        ]
        if not categories:
            return TurnListResponse(turns=[], count=0)

    event_types = normalize_filter_values(event_type)
    if event_type is None:
        event_types = []

    turn_types = _build_turn_type_filter(turn_type, categories, event_types)
    if turn_types is not None and not turn_types:
        return TurnListResponse(turns=[], count=0)

    post_filter = _build_post_filter(categories, event_types)
    if post_filter is None:
        turns = await repo.get_turns_for_session(
            session_id=session_id,
            limit=limit,
            after_sequence=after_sequence,
            actor=actor,
            turn_type=turn_type,
            turn_types=list(turn_types) if turn_types else None,
            actor_groups=actor_groups,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
        )
    else:
        turns = await _fetch_turns_with_post_filter(
            repo,
            session_id=session_id,
            limit=limit,
            after_sequence=after_sequence,
            actor=actor,
            actor_groups=actor_groups,
            turn_types=list(turn_types) if turn_types else None,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
            post_filter=post_filter,
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
