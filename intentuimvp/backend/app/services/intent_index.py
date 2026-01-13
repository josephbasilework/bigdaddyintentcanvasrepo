"""Intent index persistence helpers for insert/update/prune operations.

Implements PRD §15.2 Intent Index lifecycle management:
- Insert: Save new intents with embeddings when assumptions are approved
- Update: Modify intent text (with re-embedding) or outcome/resolution
- Prune: Remove old failed intents per data retention policy (90 days)

The IntentIndexStore provides a high-level interface for intent persistence
that handles embedding generation, serialization, and database operations.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import String, and_, delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.intent import IntentOutcome, UserIntent
from app.services.embedding import create_embedding_provider

logger = logging.getLogger(__name__)

EmbeddingProvider = Callable[[str], Sequence[float] | None]

DEFAULT_PRUNE_DAYS = 90
DEFAULT_PAGE_LIMIT = 100


class IntentIndexStore:
    """Persist user intents for intent index updates."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession] = AsyncSessionLocal,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider

    async def insert_intent(
        self,
        *,
        user_id: str,
        intent_text: str,
        resolution: object | None = None,
        intent_type: str | None = None,
        handler: str | None = None,
        confidence: float | None = None,
        context: dict[str, Any] | None = None,
        outcome: IntentOutcome | str | None = None,
        executed: bool | None = None,
        created_at: datetime | None = None,
    ) -> UserIntent:
        """Insert a user intent into the index."""
        if not user_id or not user_id.strip():
            raise ValueError("user_id is required to insert intent index entries")
        if not intent_text or not intent_text.strip():
            raise ValueError("intent_text is required to insert intent index entries")

        provider = self._embedding_provider or create_embedding_provider()
        embedding = None
        if provider is not None:
            try:
                embedding = provider(intent_text)
            except Exception:
                logger.warning("Intent index embedding generation failed", exc_info=True)
                embedding = None

        serialized_embedding = _serialize_embedding(embedding)
        if embedding is not None and serialized_embedding is None:
            logger.warning("Intent index embedding serialization failed; storing None")

        payload: dict[str, Any] = {
            "user_id": user_id.strip(),
            "intent_text": intent_text.strip(),
            "intent_type": intent_type,
            "handler": handler,
            "confidence": confidence,
            "context": context or {},
            "embedding": serialized_embedding,
            "resolution": resolution,
            "outcome": _normalize_outcome(outcome),
        }
        if executed is not None:
            payload["executed"] = executed
        if created_at is not None:
            payload["created_at"] = created_at

        async with self._session_factory() as session:
            record = UserIntent(**payload)
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def get_intent(self, intent_id: int) -> UserIntent | None:
        """Get an intent by its ID.

        Args:
            intent_id: Primary key identifier.

        Returns:
            UserIntent if found, None otherwise.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserIntent).where(UserIntent.id == intent_id)
            )
            return result.scalar_one_or_none()

    async def update_outcome(
        self,
        intent_id: int,
        outcome: IntentOutcome | str,
        *,
        resolution: object | None = None,
        handler: str | None = None,
        intent_type: str | None = None,
        executed: bool | None = None,
    ) -> UserIntent | None:
        """Update the outcome metadata for an existing intent.

        Called after action completion to track success/failure/modified status
        per PRD §15.2 update strategy.

        Args:
            intent_id: Primary key identifier.
            outcome: Success/failure/modified outcome.
            resolution: Updated resolution data (optional).
            handler: Handler that processed this intent (optional).
            intent_type: Type of intent (optional).
            executed: Whether the intent was executed (optional).

        Returns:
            Updated UserIntent if found, None otherwise.

        Raises:
            ValueError: If outcome is not a valid IntentOutcome.
        """
        normalized_outcome = _normalize_outcome(outcome)
        if normalized_outcome is None:
            raise ValueError("outcome is required to update intent index entries")

        async with self._session_factory() as session:
            result = await session.execute(
                select(UserIntent).where(UserIntent.id == intent_id)
            )
            record = result.scalar_one_or_none()
            if record is None:
                return None

            record.outcome = normalized_outcome
            if resolution is not None:
                record.resolution = resolution
            if handler is not None:
                record.handler = handler
            if intent_type is not None:
                record.intent_type = intent_type
            if executed is not None:
                record.executed = executed

            await session.commit()
            await session.refresh(record)
            return record

    async def update_intent(
        self,
        intent_id: int,
        *,
        intent_text: str | None = None,
        resolution: object | None = None,
        intent_type: str | None = None,
        handler: str | None = None,
        confidence: float | None = None,
        context: dict[str, Any] | None = None,
        outcome: IntentOutcome | str | None = None,
        executed: bool | None = None,
    ) -> UserIntent | None:
        """Update an intent, optionally re-generating embedding if text changes.

        Use this method when the intent text or metadata needs modification.
        If intent_text is provided, a new embedding is generated for similarity
        search accuracy.

        Args:
            intent_id: Primary key identifier.
            intent_text: New intent text (triggers re-embedding if provided).
            resolution: Updated resolution data.
            intent_type: Type of intent.
            handler: Handler that processed this intent.
            confidence: Confidence score.
            context: Additional context data.
            outcome: Success/failure/modified outcome.
            executed: Whether the intent was executed.

        Returns:
            Updated UserIntent if found, None otherwise.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserIntent).where(UserIntent.id == intent_id)
            )
            record = result.scalar_one_or_none()
            if record is None:
                return None

            if intent_text is not None and intent_text.strip():
                record.intent_text = intent_text.strip()
                provider = self._embedding_provider or create_embedding_provider()
                embedding = None
                if provider is not None:
                    try:
                        embedding = provider(intent_text)
                    except Exception:
                        logger.warning(
                            "Intent index embedding re-generation failed",
                            exc_info=True,
                        )
                serialized = _serialize_embedding(embedding)
                record.embedding = serialized

            if resolution is not None:
                record.resolution = resolution
            if intent_type is not None:
                record.intent_type = intent_type
            if handler is not None:
                record.handler = handler
            if confidence is not None:
                record.confidence = confidence
            if context is not None:
                record.context = context
            if outcome is not None:
                record.outcome = _normalize_outcome(outcome)
            if executed is not None:
                record.executed = executed

            await session.commit()
            await session.refresh(record)
            return record

    async def list_user_intents(
        self,
        user_id: str,
        *,
        outcome: IntentOutcome | str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> list[UserIntent]:
        """List intents for a specific user with optional outcome filter.

        Args:
            user_id: User identifier.
            outcome: Filter by outcome status (optional).
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of UserIntent instances, ordered by created_at descending.
        """
        if not user_id or not user_id.strip():
            return []

        async with self._session_factory() as session:
            stmt = (
                select(UserIntent)
                .where(UserIntent.user_id == user_id.strip())
                .order_by(desc(UserIntent.created_at))
                .offset(offset)
                .limit(limit)
            )

            if outcome is not None:
                normalized = _normalize_outcome(outcome)
                if normalized is not None:
                    stmt = stmt.where(UserIntent.outcome == normalized)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def delete_intent(self, intent_id: int) -> bool:
        """Delete an intent by its ID.

        Args:
            intent_id: Primary key identifier.

        Returns:
            True if deleted, False if not found.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserIntent).where(UserIntent.id == intent_id)
            )
            record = result.scalar_one_or_none()
            if record is None:
                return False

            await session.delete(record)
            await session.commit()
            return True

    async def prune_failed(
        self,
        *,
        cutoff_days: int = DEFAULT_PRUNE_DAYS,
        user_id: str | None = None,
        now: datetime | None = None,
    ) -> int:
        """Prune failed intent entries older than the cutoff.

        Per PRD §15.2, removes intents with outcome='failure' older than
        the cutoff period (default 90 days). This helps maintain index
        quality by removing unsuccessful interactions.

        Args:
            cutoff_days: Number of days to retain failed intents (default 90).
            user_id: Optional user scope for cleanup.
            now: Current time for testing (defaults to datetime.utcnow()).

        Returns:
            Number of intents deleted.
        """
        if cutoff_days <= 0:
            return 0
        cutoff = (now or datetime.utcnow()) - timedelta(days=cutoff_days)

        async with self._session_factory() as session:
            conditions = [
                UserIntent.outcome == IntentOutcome.FAILURE,
                UserIntent.created_at < cutoff,
            ]
            if user_id:
                conditions.append(UserIntent.user_id == user_id)

            stmt = select(UserIntent.id).where(and_(*conditions))
            result = await session.execute(stmt)
            ids = list(result.scalars().all())
            if not ids:
                return 0

            await session.execute(delete(UserIntent).where(UserIntent.id.in_(ids)))
            await session.commit()

            logger.info(
                "Pruned %d failed intents older than %d days%s",
                len(ids),
                cutoff_days,
                f" for user {user_id}" if user_id else "",
            )
            return len(ids)

    async def prune_all_old(
        self,
        *,
        cutoff_days: int = DEFAULT_PRUNE_DAYS * 4,
        user_id: str | None = None,
        now: datetime | None = None,
    ) -> int:
        """Prune all intent entries older than the cutoff regardless of outcome.

        Use for general data retention cleanup. Default cutoff is 360 days.

        Args:
            cutoff_days: Number of days to retain intents (default 360).
            user_id: Optional user scope for cleanup.
            now: Current time for testing (defaults to datetime.utcnow()).

        Returns:
            Number of intents deleted.
        """
        if cutoff_days <= 0:
            return 0
        cutoff = (now or datetime.utcnow()) - timedelta(days=cutoff_days)

        async with self._session_factory() as session:
            conditions = [UserIntent.created_at < cutoff]
            if user_id:
                conditions.append(UserIntent.user_id == user_id)

            stmt = select(UserIntent.id).where(and_(*conditions))
            result = await session.execute(stmt)
            ids = list(result.scalars().all())
            if not ids:
                return 0

            await session.execute(delete(UserIntent).where(UserIntent.id.in_(ids)))
            await session.commit()

            logger.info(
                "Pruned %d old intents older than %d days%s",
                len(ids),
                cutoff_days,
                f" for user {user_id}" if user_id else "",
            )
            return len(ids)


_intent_index_store: IntentIndexStore | None = None


def get_intent_index_store() -> IntentIndexStore:
    """Get the singleton intent index store."""
    global _intent_index_store
    if _intent_index_store is None:
        _intent_index_store = IntentIndexStore()
    return _intent_index_store


def _serialize_embedding(
    embedding: Sequence[float] | None,
) -> list[float] | str | None:
    if embedding is None:
        return None
    try:
        values = [float(value) for value in embedding]
    except (TypeError, ValueError):
        return None
    if _should_store_embedding_as_json():
        return json.dumps(values)
    return values


def _should_store_embedding_as_json() -> bool:
    embedding_type = UserIntent.__table__.c.embedding.type
    return isinstance(embedding_type, String)


def _normalize_outcome(
    outcome: IntentOutcome | str | None,
) -> IntentOutcome | None:
    if outcome is None:
        return None
    if isinstance(outcome, IntentOutcome):
        return outcome
    try:
        return IntentOutcome(outcome)
    except ValueError as exc:
        raise ValueError(f"Invalid intent outcome: {outcome}") from exc
