"""Repository for turn operations with session scoping.

Turns represent state changes in the system and are scoped to sessions.
This repository provides CRUD operations and session-scoped queries.
"""

from logging import getLogger
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.turn import Turn, TurnActor, TurnType

logger = getLogger(__name__)


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

    def create_turn(
        self,
        session_id: str,
        actor: TurnActor,
        turn_type: TurnType,
        summary: str,
        payload: dict[str, Any] | None = None,
        related_node_id: int | None = None,
        related_edge_id: int | None = None,
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

        Returns:
            Created Turn
        """
        sequence_number = self.get_next_sequence_number(session_id)

        turn = Turn(
            session_id=session_id,
            sequence_number=sequence_number,
            actor=actor,
            type=turn_type,
            summary=summary,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
        )
        if payload:
            turn.set_payload(payload)

        self.db.add(turn)
        self.db.commit()
        self.db.refresh(turn)

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
    ) -> list[Turn]:
        """Get turns for a session, ordered by sequence number.

        Args:
            session_id: The session to get turns for
            limit: Optional maximum number of turns to return
            after_sequence: Optional sequence number to start after (exclusive)

        Returns:
            List of Turn objects ordered by sequence_number
        """
        query = self.db.query(Turn).filter(Turn.session_id == session_id)

        if after_sequence is not None:
            query = query.filter(Turn.sequence_number > after_sequence)

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

    async def create_turn(
        self,
        session_id: str,
        actor: TurnActor,
        turn_type: TurnType,
        summary: str,
        payload: dict[str, Any] | None = None,
        related_node_id: int | None = None,
        related_edge_id: int | None = None,
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

        Returns:
            Created Turn
        """
        sequence_number = await self.get_next_sequence_number(session_id)

        turn = Turn(
            session_id=session_id,
            sequence_number=sequence_number,
            actor=actor,
            type=turn_type,
            summary=summary,
            related_node_id=related_node_id,
            related_edge_id=related_edge_id,
        )
        if payload:
            turn.set_payload(payload)

        self.db.add(turn)
        await self.db.commit()
        await self.db.refresh(turn)

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
    ) -> list[Turn]:
        """Get turns for a session, ordered by sequence number.

        Args:
            session_id: The session to get turns for
            limit: Optional maximum number of turns to return
            after_sequence: Optional sequence number to start after (exclusive)

        Returns:
            List of Turn objects ordered by sequence_number
        """
        stmt = select(Turn).filter(Turn.session_id == session_id)

        if after_sequence is not None:
            stmt = stmt.filter(Turn.sequence_number > after_sequence)

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
