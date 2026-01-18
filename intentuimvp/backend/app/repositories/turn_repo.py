"""Repository for turn operations with session scoping.

Turns represent state changes in the system and are scoped to sessions.
This repository provides CRUD operations and session-scoped queries.
"""

from logging import getLogger
from typing import Any

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.turn import Turn, TurnActor, TurnType
from app.services.turn_filters import JOB_TURN_TYPES

logger = getLogger(__name__)


def _normalize_actor_groups(actor_groups: list[str] | None) -> list[str]:
    if not actor_groups:
        return []
    normalized: list[str] = []
    for group in actor_groups:
        if not group:
            continue
        cleaned = group.strip().lower()
        if cleaned:
            normalized.append(cleaned)
    return sorted(set(normalized))


def _apply_actor_group_filters(
    query,
    actor_groups: list[str] | None,
):
    normalized = _normalize_actor_groups(actor_groups)
    if actor_groups is None:
        return query
    if not normalized:
        return query.filter(false())

    conditions = []
    for group in normalized:
        if group == "job":
            conditions.append(Turn.type.in_(JOB_TURN_TYPES))
        elif group == "user":
            conditions.append(
                and_(
                    Turn.actor == TurnActor.USER,
                    ~Turn.type.in_(JOB_TURN_TYPES),
                )
            )
        elif group == "external":
            conditions.append(
                and_(
                    Turn.actor == TurnActor.MCP,
                    ~Turn.type.in_(JOB_TURN_TYPES),
                )
            )
        elif group == "system":
            conditions.append(
                and_(
                    Turn.actor.in_([TurnActor.SYSTEM, TurnActor.AGENT]),
                    ~Turn.type.in_(JOB_TURN_TYPES),
                )
            )

    if not conditions:
        return query.filter(false())

    return query.filter(or_(*conditions))


class TurnRepository:
    """Repository for Turn CRUD operations with session scoping.

    Uses SQLAlchemy ORM for database access. All queries are scoped
    to a session_id for proper session isolation.
    """

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session (sync)
        """
        self.db = db

    def get_next_sequence_number(self, session_id: str) -> int:
        """Get the next sequence number for a session.

        Args:
            session_id: The session identifier

        Returns:
            Next sequence number (1-indexed, starts at 1 for new sessions)
        """
        result = (
            self.db.query(func.max(Turn.sequence_number))
            .filter(Turn.session_id == session_id)
            .scalar()
        )
        return (result or 0) + 1

    def get_turn_by_client_request_id(
        self, session_id: str, client_request_id: str
    ) -> Turn | None:
        """Get a turn by client request ID (idempotency key)."""
        if not client_request_id:
            return None
        return (
            self.db.query(Turn)
            .filter(
                Turn.session_id == session_id,
                Turn.client_request_id == client_request_id,
            )
            .first()
        )

    def create_turn(
        self,
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
    ) -> Turn:
        """Create a new turn in the session.

        Args:
            session_id: The session this turn belongs to
            actor: Who/what created this turn
            turn_type: Type of state change
            summary: Human-readable summary
            payload: Optional JSON payload with turn-specific data
            related_node_id: Optional reference to a related node
            related_edge_id: Optional reference to a related edge
            origin_sequence_number: Sequence number of the turn being modified/deleted
            sequence_number: Explicit sequence number (must match next sequential value)

        Returns:
            Created Turn
        """
        if client_request_id:
            existing = (
                self.db.query(Turn)
                .filter(
                    Turn.session_id == session_id,
                    Turn.client_request_id == client_request_id,
                )
                .first()
            )
            if existing:
                setattr(existing, "_was_existing", True)
                return existing

        explicit_sequence_number = sequence_number is not None
        if origin_sequence_number is not None:
            origin_turn = self.get_turn_by_sequence(session_id, origin_sequence_number)
            if origin_turn is None:
                raise ValueError(
                    f"Origin sequence number {origin_sequence_number} not found"
                )

        expected_sequence_number = self.get_next_sequence_number(session_id)
        if sequence_number is None:
            sequence_number = expected_sequence_number
        elif sequence_number != expected_sequence_number:
            raise ValueError(
                "Sequence number must match the next sequential value "
                f"({expected_sequence_number})"
            )
        if origin_sequence_number is not None and origin_sequence_number >= sequence_number:
            raise ValueError("Origin sequence number must precede the new turn")

        attempt = 0
        while True:
            turn = Turn(
                session_id=session_id,
                sequence_number=sequence_number,
                actor=actor,
                type=turn_type,
                summary=summary,
                related_node_id=related_node_id,
                related_edge_id=related_edge_id,
                origin_sequence_number=origin_sequence_number,
                client_request_id=client_request_id,
            )
            if payload:
                turn.set_payload(payload)

            self.db.add(turn)
            try:
                self.db.commit()
                self.db.refresh(turn)
                break
            except IntegrityError:
                self.db.rollback()
                if client_request_id:
                    existing = (
                        self.db.query(Turn)
                        .filter(
                            Turn.session_id == session_id,
                            Turn.client_request_id == client_request_id,
                        )
                        .first()
                    )
                    if existing:
                        setattr(existing, "_was_existing", True)
                        return existing
                if explicit_sequence_number:
                    raise
                attempt += 1
                if attempt >= 3 or sequence_number != expected_sequence_number:
                    raise
                expected_sequence_number = self.get_next_sequence_number(session_id)
                sequence_number = expected_sequence_number

        logger.debug(
            f"Created turn {turn.id} (session={session_id}, seq={sequence_number}, "
            f"type={turn_type})"
        )
        return turn

    def get_turns_for_session(
        self,
        session_id: str,
        limit: int | None = None,
        after_sequence: int | None = None,
        actor: TurnActor | None = None,
        turn_type: TurnType | None = None,
        actors: list[TurnActor] | None = None,
        turn_types: list[TurnType] | None = None,
        actor_groups: list[str] | None = None,
        related_node_id: int | None = None,
        related_edge_id: int | None = None,
    ) -> list[Turn]:
        """Get turns for a session, ordered by sequence number.

        Args:
            session_id: The session to get turns for
            limit: Optional maximum number of turns to return
            after_sequence: Optional sequence number to start after (exclusive)
            actor: Optional actor filter
            turn_type: Optional type filter
            actors: Optional actor list filter
            turn_types: Optional list of types filter
            actor_groups: Optional actor group filters
            related_node_id: Optional node scope filter
            related_edge_id: Optional edge scope filter

        Returns:
            List of Turn objects ordered by sequence_number
        """
        query = self.db.query(Turn).filter(Turn.session_id == session_id)

        if after_sequence is not None:
            query = query.filter(Turn.sequence_number > after_sequence)

        query = _apply_actor_group_filters(query, actor_groups)

        if actor is not None:
            if actors is not None and actor not in actors:
                return []
            query = query.filter(Turn.actor == actor)
        elif actors:
            query = query.filter(Turn.actor.in_(actors))

        if turn_type is not None:
            if turn_types is not None and turn_type not in turn_types:
                return []
            query = query.filter(Turn.type == turn_type)
        elif turn_types:
            query = query.filter(Turn.type.in_(turn_types))

        if related_node_id is not None:
            query = query.filter(Turn.related_node_id == related_node_id)

        if related_edge_id is not None:
            query = query.filter(Turn.related_edge_id == related_edge_id)

        query = query.order_by(Turn.sequence_number.asc())

        if limit:
            query = query.limit(limit)

        return list(query.all())

    def get_turns_by_type(
        self,
        session_id: str,
        turn_type: TurnType,
        limit: int | None = None,
    ) -> list[Turn]:
        """Get turns of a specific type for a session.

        Args:
            session_id: The session to get turns for
            turn_type: The type of turns to retrieve
            limit: Optional maximum number of turns to return

        Returns:
            List of Turn objects matching the type
        """
        query = (
            self.db.query(Turn)
            .filter(Turn.session_id == session_id, Turn.type == turn_type)
            .order_by(Turn.sequence_number.asc())
        )

        if limit:
            query = query.limit(limit)

        return list(query.all())

    def get_latest_turn(self, session_id: str) -> Turn | None:
        """Get the most recent turn for a session.

        Args:
            session_id: The session to get the latest turn for

        Returns:
            The latest Turn, or None if no turns exist
        """
        return (
            self.db.query(Turn)
            .filter(Turn.session_id == session_id)
            .order_by(Turn.sequence_number.desc())
            .first()
        )

    def get_latest_turn_for_node(
        self,
        session_id: str,
        node_id: int,
        turn_types: list[TurnType] | None = None,
    ) -> Turn | None:
        """Get the most recent turn for a node within a session."""
        query = self.db.query(Turn).filter(
            Turn.session_id == session_id,
            Turn.related_node_id == node_id,
        )
        if turn_types:
            query = query.filter(Turn.type.in_(turn_types))
        return query.order_by(Turn.sequence_number.desc()).first()

    def get_latest_turn_for_edge(
        self,
        session_id: str,
        edge_id: int,
        turn_types: list[TurnType] | None = None,
    ) -> Turn | None:
        """Get the most recent turn for an edge within a session."""
        query = self.db.query(Turn).filter(
            Turn.session_id == session_id,
            Turn.related_edge_id == edge_id,
        )
        if turn_types:
            query = query.filter(Turn.type.in_(turn_types))
        return query.order_by(Turn.sequence_number.desc()).first()

    def count_turns(self, session_id: str) -> int:
        """Count the number of turns in a session.

        Args:
            session_id: The session to count turns for

        Returns:
            Number of turns in the session
        """
        return self.db.query(Turn).filter(Turn.session_id == session_id).count()

    def get_turn_by_sequence(
        self, session_id: str, sequence_number: int
    ) -> Turn | None:
        """Get a specific turn by session and sequence number.

        Args:
            session_id: The session identifier
            sequence_number: The sequence number within the session

        Returns:
            The Turn if found, None otherwise
        """
        return (
            self.db.query(Turn)
            .filter(
                Turn.session_id == session_id,
                Turn.sequence_number == sequence_number,
            )
            .first()
        )


class AsyncTurnRepository:
    """Async repository for Turn CRUD operations with session scoping.

    Uses SQLAlchemy async ORM for database access.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with async database session.

        Args:
            db: SQLAlchemy async session
        """
        self.db = db

    async def get_next_sequence_number(self, session_id: str) -> int:
        """Get the next sequence number for a session.

        Args:
            session_id: The session identifier

        Returns:
            Next sequence number (1-indexed, starts at 1 for new sessions)
        """
        result = await self.db.execute(
            select(func.max(Turn.sequence_number)).filter(Turn.session_id == session_id)
        )
        max_seq = result.scalar()
        return (max_seq or 0) + 1

    async def get_turn_by_client_request_id(
        self, session_id: str, client_request_id: str
    ) -> Turn | None:
        """Get a turn by client request ID (idempotency key)."""
        if not client_request_id:
            return None
        result = await self.db.execute(
            select(Turn).filter(
                Turn.session_id == session_id,
                Turn.client_request_id == client_request_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_turn(
        self,
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
    ) -> Turn:
        """Create a new turn in the session.

        Args:
            session_id: The session this turn belongs to
            actor: Who/what created this turn
            turn_type: Type of state change
            summary: Human-readable summary
            payload: Optional JSON payload with turn-specific data
            related_node_id: Optional reference to a related node
            related_edge_id: Optional reference to a related edge
            origin_sequence_number: Sequence number of the turn being modified/deleted
            sequence_number: Explicit sequence number (must match next sequential value)

        Returns:
            Created Turn
        """
        if client_request_id:
            existing_result = await self.db.execute(
                select(Turn).filter(
                    Turn.session_id == session_id,
                    Turn.client_request_id == client_request_id,
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing:
                setattr(existing, "_was_existing", True)
                return existing

        explicit_sequence_number = sequence_number is not None
        if origin_sequence_number is not None:
            origin_turn = await self.db.execute(
                select(Turn).filter(
                    Turn.session_id == session_id,
                    Turn.sequence_number == origin_sequence_number,
                )
            )
            if origin_turn.scalar_one_or_none() is None:
                raise ValueError(
                    f"Origin sequence number {origin_sequence_number} not found"
                )

        expected_sequence_number = await self.get_next_sequence_number(session_id)
        if sequence_number is None:
            sequence_number = expected_sequence_number
        elif sequence_number != expected_sequence_number:
            raise ValueError(
                "Sequence number must match the next sequential value "
                f"({expected_sequence_number})"
            )
        if origin_sequence_number is not None and origin_sequence_number >= sequence_number:
            raise ValueError("Origin sequence number must precede the new turn")

        attempt = 0
        while True:
            turn = Turn(
                session_id=session_id,
                sequence_number=sequence_number,
                actor=actor,
                type=turn_type,
                summary=summary,
                related_node_id=related_node_id,
                related_edge_id=related_edge_id,
                origin_sequence_number=origin_sequence_number,
                client_request_id=client_request_id,
            )
            if payload:
                turn.set_payload(payload)

            self.db.add(turn)
            try:
                await self.db.commit()
                await self.db.refresh(turn)
                break
            except IntegrityError:
                await self.db.rollback()
                if client_request_id:
                    existing_result = await self.db.execute(
                        select(Turn).filter(
                            Turn.session_id == session_id,
                            Turn.client_request_id == client_request_id,
                        )
                    )
                    existing = existing_result.scalar_one_or_none()
                    if existing:
                        setattr(existing, "_was_existing", True)
                        return existing
                if explicit_sequence_number:
                    raise
                attempt += 1
                if attempt >= 3 or sequence_number != expected_sequence_number:
                    raise
                expected_sequence_number = await self.get_next_sequence_number(session_id)
                sequence_number = expected_sequence_number

        logger.debug(
            f"Created turn {turn.id} (session={session_id}, seq={sequence_number}, "
            f"type={turn_type})"
        )
        return turn

    async def get_turns_for_session(
        self,
        session_id: str,
        limit: int | None = None,
        after_sequence: int | None = None,
        actor: TurnActor | None = None,
        turn_type: TurnType | None = None,
        actors: list[TurnActor] | None = None,
        turn_types: list[TurnType] | None = None,
        actor_groups: list[str] | None = None,
        related_node_id: int | None = None,
        related_edge_id: int | None = None,
    ) -> list[Turn]:
        """Get turns for a session, ordered by sequence number.

        Args:
            session_id: The session to get turns for
            limit: Optional maximum number of turns to return
            after_sequence: Optional sequence number to start after (exclusive)
            actor: Optional actor filter
            turn_type: Optional type filter
            actors: Optional actor list filter
            turn_types: Optional list of types filter
            actor_groups: Optional actor group filters
            related_node_id: Optional node scope filter
            related_edge_id: Optional edge scope filter

        Returns:
            List of Turn objects ordered by sequence_number
        """
        stmt = select(Turn).filter(Turn.session_id == session_id)

        if after_sequence is not None:
            stmt = stmt.filter(Turn.sequence_number > after_sequence)

        stmt = _apply_actor_group_filters(stmt, actor_groups)

        if actor is not None:
            if actors is not None and actor not in actors:
                return []
            stmt = stmt.filter(Turn.actor == actor)
        elif actors:
            stmt = stmt.filter(Turn.actor.in_(actors))

        if turn_type is not None:
            if turn_types is not None and turn_type not in turn_types:
                return []
            stmt = stmt.filter(Turn.type == turn_type)
        elif turn_types:
            stmt = stmt.filter(Turn.type.in_(turn_types))

        if related_node_id is not None:
            stmt = stmt.filter(Turn.related_node_id == related_node_id)

        if related_edge_id is not None:
            stmt = stmt.filter(Turn.related_edge_id == related_edge_id)

        stmt = stmt.order_by(Turn.sequence_number.asc())

        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_turn(self, session_id: str) -> Turn | None:
        """Get the most recent turn for a session.

        Args:
            session_id: The session to get the latest turn for

        Returns:
            The latest Turn, or None if no turns exist
        """
        result = await self.db.execute(
            select(Turn)
            .filter(Turn.session_id == session_id)
            .order_by(Turn.sequence_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_turn_for_node(
        self,
        session_id: str,
        node_id: int,
        turn_types: list[TurnType] | None = None,
    ) -> Turn | None:
        """Get the most recent turn for a node within a session."""
        stmt = select(Turn).filter(
            Turn.session_id == session_id,
            Turn.related_node_id == node_id,
        )
        if turn_types:
            stmt = stmt.filter(Turn.type.in_(turn_types))
        stmt = stmt.order_by(Turn.sequence_number.desc()).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_turn_for_edge(
        self,
        session_id: str,
        edge_id: int,
        turn_types: list[TurnType] | None = None,
    ) -> Turn | None:
        """Get the most recent turn for an edge within a session."""
        stmt = select(Turn).filter(
            Turn.session_id == session_id,
            Turn.related_edge_id == edge_id,
        )
        if turn_types:
            stmt = stmt.filter(Turn.type.in_(turn_types))
        stmt = stmt.order_by(Turn.sequence_number.desc()).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def count_turns(self, session_id: str) -> int:
        """Count the number of turns in a session.

        Args:
            session_id: The session to count turns for

        Returns:
            Number of turns in the session
        """
        result = await self.db.execute(
            select(func.count(Turn.id)).filter(Turn.session_id == session_id)
        )
        return result.scalar() or 0
