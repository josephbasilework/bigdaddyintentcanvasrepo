"""Repository for UserIntent with insert/update/prune operations.

Implements PRD §15.2 Intent Index lifecycle management:
- Insert: Save new intents with embeddings when assumptions are approved
- Update: Modify outcome/resolution after execution or assumption changes
- Prune: Remove old failed intents per data retention policy (90 days)
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import and_, delete, desc, select

from app.models.intent import IntentOutcome, UserIntent
from app.repositories.base import BaseRepository
from app.services.embedding import get_embedding_service

logger = logging.getLogger(__name__)


# Placeholder schemas for BaseRepository Generic types
class CreateIntentSchema(BaseModel):
    """Placeholder create schema for BaseRepository."""

    pass


class UpdateIntentSchema(BaseModel):
    """Placeholder update schema for BaseRepository."""

    pass


class IntentRepository(BaseRepository[UserIntent, CreateIntentSchema, UpdateIntentSchema]):
    """Repository for UserIntent lifecycle management.

    Provides methods for:
    - Inserting new intents with embeddings
    - Updating intent outcomes and resolutions
    - Pruning old failed intents per retention policy
    """

    @property
    def model(self) -> type[UserIntent]:
        """Return the UserIntent model."""
        return UserIntent

    async def insert_intent(
        self,
        user_id: str,
        intent_text: str,
        resolution: dict[str, Any] | None = None,
        intent_type: str | None = None,
        confidence: float | None = None,
        context: dict[str, Any] | None = None,
        handler: str | None = None,
    ) -> UserIntent:
        """Insert a new intent with embedding.

        Generates an embedding for the intent_text using the EmbeddingService
        and stores the intent in the database.

        Args:
            user_id: User identifier.
            intent_text: Original user input text.
            resolution: Approved assumptions and actions (JSON).
            intent_type: Type of intent (optional).
            confidence: Confidence score from decipherer (optional).
            context: Additional context data (optional).
            handler: Handler that processed this intent (optional).

        Returns:
            Created UserIntent instance.

        Raises:
            ValueError: If intent_text is empty.
            RuntimeError: If embedding generation fails.
        """
        if not intent_text or not intent_text.strip():
            raise ValueError("intent_text cannot be empty")

        # Generate embedding
        embedding_service = get_embedding_service()
        try:
            embedding = embedding_service.encode(intent_text)
        except Exception as e:
            logger.error("Failed to generate embedding for intent: %s", e)
            raise RuntimeError(f"Failed to generate embedding: {e}") from e

        # Convert embedding to comma-separated string for SQLite compatibility
        # (PostgreSQL/pgvector handles lists natively)
        embedding_str = ",".join(str(x) for x in embedding) if embedding else None

        return await self.create(
            user_id=user_id,
            intent_text=intent_text,
            intent_type=intent_type,
            confidence=confidence,
            embedding=embedding_str,
            resolution=resolution or {},
            context=context or {},
            handler=handler,
            executed=False,
            outcome=None,
        )

    async def update_outcome(
        self,
        intent_id: int,
        outcome: IntentOutcome,
        resolution: dict[str, Any] | None = None,
        executed: bool = True,
    ) -> UserIntent | None:
        """Update the outcome of an intent after execution.

        Args:
            intent_id: Intent primary key.
            outcome: Success/failure/modified outcome.
            resolution: Updated resolution data (optional).
            executed: Whether the intent was executed (default True).

        Returns:
            Updated UserIntent if found, None otherwise.
        """
        update_kwargs: dict[str, Any] = {"outcome": outcome, "executed": executed}
        if resolution is not None:
            update_kwargs["resolution"] = resolution

        return await self.update(intent_id, **update_kwargs)

    async def prune_old_failed_intents(
        self, cutoff_days: int = 90
    ) -> int:
        """Prune (delete) old failed intents per data retention policy.

        Per PRD §15.3, removes intents with outcome='failure' older than
        the cutoff period.

        Args:
            cutoff_days: Number of days to retain failed intents (default 90).

        Returns:
            Number of intents deleted.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_days)

        stmt = delete(UserIntent).where(
            and_(
                UserIntent.outcome == IntentOutcome.FAILURE,
                UserIntent.created_at < cutoff_date,
            )
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        deleted_count = result.rowcount
        if deleted_count > 0:
            logger.info(
                "Pruned %d failed intents older than %d days",
                deleted_count,
                cutoff_days,
            )

        return deleted_count

    async def list_by_user(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[UserIntent]:
        """List intents for a specific user.

        Args:
            user_id: User identifier.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of UserIntent instances for the user.
        """
        stmt = (
            select(UserIntent)
            .where(UserIntent.user_id == user_id)
            .order_by(desc(UserIntent.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user_and_outcome(
        self,
        user_id: str,
        outcome: IntentOutcome,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[UserIntent]:
        """Get intents for a user filtered by outcome.

        Args:
            user_id: User identifier.
            outcome: Outcome status to filter by.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of UserIntent instances matching the criteria.
        """
        stmt = (
            select(UserIntent)
            .where(
                and_(
                    UserIntent.user_id == user_id,
                    UserIntent.outcome == outcome,
                )
            )
            .order_by(desc(UserIntent.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
