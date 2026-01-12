"""Intent index lookup utilities for confidence adjustment."""

from __future__ import annotations

import difflib
import json
import logging
import math
import os
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.intent import UserIntent

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "default_user"
DEFAULT_SIMILARITY_THRESHOLD = 0.7
DEFAULT_RECENCY_DECAY = 0.99
DEFAULT_MAX_MATCHES = 5
DEFAULT_CANDIDATE_LIMIT = 50

_WORD_RE = re.compile(r"[a-z0-9]+")


def _is_pgvector_available() -> bool:
    """Check if pgvector is available for native similarity queries.

    Returns True when:
    - DATABASE_URL is PostgreSQL
    - pgvector module is installed

    This enables native vector similarity queries using the <=> operator.
    """
    database_url = os.getenv("DATABASE_URL", "")
    is_postgres = database_url.startswith("postgresql://") or database_url.startswith(
        "postgresql+asyncpg://"
    )
    if not is_postgres:
        return False
    try:
        import importlib.util

        return importlib.util.find_spec("pgvector") is not None
    except Exception:
        return False


EmbeddingProvider = Callable[[str], Sequence[float] | None]


@dataclass(frozen=True)
class IntentIndexMatch:
    """Scored match from the intent index."""

    resolution: str | None
    similarity: float
    recency_weight: float
    score: float


class IntentIndexLookup:
    """Lookup similar intents from the user's intent index."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession] = AsyncSessionLocal,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_matches: int = DEFAULT_MAX_MATCHES,
        candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
        recency_decay: float = DEFAULT_RECENCY_DECAY,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialize lookup configuration."""
        self._session_factory = session_factory
        self._similarity_threshold = similarity_threshold
        self._max_matches = max_matches
        self._candidate_limit = candidate_limit
        self._recency_decay = recency_decay
        self._embedding_provider = embedding_provider

    async def lookup(self, user_id: str, input_text: str) -> list[IntentIndexMatch]:
        """Return top intent index matches for the input text.

        Uses native pgvector similarity search when PostgreSQL with pgvector
        is available (PRD §15.2), falling back to in-memory scoring for SQLite.
        """
        normalized_input = _normalize_text(input_text)
        if not normalized_input:
            return []

        input_embedding: list[float] | None = None
        if self._embedding_provider is not None:
            try:
                input_embedding = _parse_embedding(self._embedding_provider(input_text))
            except Exception:
                logger.warning("Intent index embedding generation failed", exc_info=True)
                input_embedding = None

        # Use native pgvector similarity query when available (PRD §15.2)
        if input_embedding is not None and _is_pgvector_available():
            try:
                async with self._session_factory() as session:
                    return await self._fetch_similar_pgvector(session, user_id, input_embedding)
            except Exception:
                logger.warning(
                    "pgvector similarity query failed, falling back to in-memory",
                    exc_info=True,
                )
                # Fall through to in-memory scoring

        # Fallback: fetch candidates and score in-memory
        try:
            async with self._session_factory() as session:
                candidates = await self._fetch_candidates(session, user_id)
        except Exception:
            logger.warning("Intent index lookup failed", exc_info=True)
            return []

        return self._score_candidates(normalized_input, candidates, input_embedding=input_embedding)

    async def _fetch_candidates(self, session: AsyncSession, user_id: str) -> list[UserIntent]:
        stmt = (
            select(UserIntent)
            .where(UserIntent.user_id == user_id)
            .order_by(UserIntent.created_at.desc())
            .limit(self._candidate_limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _fetch_similar_pgvector(
        self,
        session: AsyncSession,
        user_id: str,
        query_embedding: Sequence[float],
    ) -> list[IntentIndexMatch]:
        """Fetch similar intents using native pgvector cosine similarity.

        Implements PRD §15.2 query algorithm:
        - Cosine similarity: SELECT * WHERE 1 - (embedding <=> query) > threshold
        - Rank by similarity * recency_weight (decay: 0.99^days_old)
        - Return top max_matches results

        Args:
            session: Async database session
            user_id: User identifier for scoping
            query_embedding: Input text embedding vector

        Returns:
            List of IntentIndexMatch with similarity scores from pgvector
        """
        # Format embedding as PostgreSQL array literal for pgvector
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # Native pgvector query per PRD §15.2:
        # - <=> is cosine distance (0 = identical, 2 = opposite)
        # - 1 - (embedding <=> query) gives cosine similarity
        # - Apply threshold filter in SQL for efficiency
        # - Compute recency weight: decay^days_old where days_old = EXTRACT days from now - created_at
        # - Order by similarity * recency_weight descending
        query = text("""
            SELECT
                id, intent_text, intent_type, handler, resolution, created_at,
                (1 - (embedding <=> :query_embedding::vector)) AS similarity,
                POWER(:decay, EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0) AS recency_weight
            FROM user_intents
            WHERE user_id = :user_id
              AND embedding IS NOT NULL
              AND (1 - (embedding <=> :query_embedding::vector)) > :threshold
            ORDER BY
                (1 - (embedding <=> :query_embedding::vector)) *
                POWER(:decay, EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0) DESC
            LIMIT :limit
        """)

        result = await session.execute(
            query,
            {
                "user_id": user_id,
                "query_embedding": embedding_str,
                "threshold": self._similarity_threshold,
                "decay": self._recency_decay,
                "limit": self._max_matches,
            },
        )

        matches: list[IntentIndexMatch] = []
        for row in result:
            # Create a minimal UserIntent-like object for resolution normalization
            candidate = UserIntent(
                id=row.id,
                intent_text=row.intent_text,
                intent_type=row.intent_type,
                handler=row.handler,
                resolution=row.resolution,
                created_at=row.created_at,
            )
            similarity = float(row.similarity)
            recency_weight = float(row.recency_weight)
            score = similarity * recency_weight

            matches.append(
                IntentIndexMatch(
                    resolution=_normalize_resolution(candidate),
                    similarity=similarity,
                    recency_weight=recency_weight,
                    score=score,
                )
            )

        return matches

    def _score_candidates(
        self,
        normalized_input: str,
        candidates: Iterable[UserIntent],
        *,
        input_embedding: Sequence[float] | None = None,
    ) -> list[IntentIndexMatch]:
        now = datetime.now(UTC)
        matches: list[IntentIndexMatch] = []
        for candidate in candidates:
            intent_text = cast(str, candidate.intent_text)
            if not intent_text:
                continue
            similarity = _candidate_similarity(normalized_input, candidate, input_embedding)
            if similarity < self._similarity_threshold:
                continue
            created_at = cast(datetime, candidate.created_at)
            recency_weight = _recency_weight(created_at, now=now, decay=self._recency_decay)
            score = similarity * recency_weight
            matches.append(
                IntentIndexMatch(
                    resolution=_normalize_resolution(candidate),
                    similarity=similarity,
                    recency_weight=recency_weight,
                    score=score,
                )
            )

        matches.sort(key=lambda match: match.score, reverse=True)
        return matches[: self._max_matches]


_intent_index_lookup: IntentIndexLookup | None = None


def get_intent_index_lookup() -> IntentIndexLookup:
    """Get the singleton intent index lookup."""
    global _intent_index_lookup
    if _intent_index_lookup is None:
        _intent_index_lookup = IntentIndexLookup()
    return _intent_index_lookup


def _normalize_text(text: str) -> str:
    tokens = _WORD_RE.findall(text.lower())
    return " ".join(tokens)


def _normalize_resolution(candidate: UserIntent) -> str | None:
    """Extract and normalize resolution from a UserIntent."""
    resolution = _extract_resolution_value(getattr(candidate, "resolution", None))
    if not resolution:
        intent_type = cast(str | None, candidate.intent_type)
        handler = cast(str | None, candidate.handler)
        resolution = intent_type or handler
    if not resolution:
        return None
    normalized = resolution.strip().lower()
    if normalized.endswith("_handler"):
        normalized = normalized[: -len("_handler")]
    return normalized or None


def _extract_resolution_value(resolution: object) -> str | None:
    payload = _parse_resolution_payload(resolution)
    if payload is None:
        return None
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("action", "handler", "intent_type", "intent", "resolution", "label", "name"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        actions = payload.get("actions")
        if isinstance(actions, list):
            for action in actions:
                value = _extract_resolution_value(action)
                if value:
                    return value
        return None
    if isinstance(payload, list):
        for item in payload:
            value = _extract_resolution_value(item)
            if value:
                return value
    return None


def _parse_resolution_payload(resolution: object) -> object | None:
    if resolution is None:
        return None
    if isinstance(resolution, str):
        raw = resolution.strip()
        if not raw:
            return None
        if raw[0] in "[{" and raw[-1] in "]}":
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return resolution
            return parsed
        return resolution
    return resolution


def _candidate_similarity(
    normalized_input: str,
    candidate: UserIntent,
    input_embedding: Sequence[float] | None,
) -> float:
    if input_embedding:
        candidate_embedding = _parse_embedding(candidate.embedding)
        similarity = _embedding_similarity(input_embedding, candidate_embedding)
        if similarity is not None:
            return similarity
    intent_text = cast(str, candidate.intent_text)
    normalized_candidate = _normalize_text(intent_text)
    return _similarity(normalized_input, normalized_candidate)


def _parse_embedding(embedding: object) -> list[float] | None:
    if embedding is None:
        return None
    if isinstance(embedding, list | tuple):
        return _coerce_embedding(embedding)
    if not isinstance(embedding, str):
        return None
    raw = embedding.strip()
    if not raw:
        return None
    if raw[0] in "[{" and raw[-1] in "]}":
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        else:
            if isinstance(parsed, list):
                return _coerce_embedding(parsed)
    cleaned = raw.strip("[](){}")
    parts = [part for part in re.split(r"[,\s]+", cleaned) if part]
    return _coerce_embedding(parts)


def _coerce_embedding(values: Sequence[object]) -> list[float] | None:
    if not values:
        return None
    coerced: list[float] = []
    for value in values:
        if not isinstance(value, int | float | str):
            return None
        try:
            coerced.append(float(value))
        except (TypeError, ValueError):
            return None
    return coerced


def _embedding_similarity(
    input_embedding: Sequence[float],
    candidate_embedding: Sequence[float] | None,
) -> float | None:
    if not candidate_embedding:
        return None
    if len(input_embedding) != len(candidate_embedding):
        return None
    left_norm = _vector_norm(input_embedding)
    right_norm = _vector_norm(candidate_embedding)
    if left_norm == 0.0 or right_norm == 0.0:
        return None
    dot = sum(left * right for left, right in zip(input_embedding, candidate_embedding))
    similarity = dot / (left_norm * right_norm)
    if math.isnan(similarity):
        return None
    return max(min(similarity, 1.0), -1.0)


def _vector_norm(values: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, left, right).ratio()


def _recency_weight(created_at: datetime | None, *, now: datetime, decay: float) -> float:
    if created_at is None:
        return 1.0
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    days_old = max((now - created_at).total_seconds() / 86400.0, 0.0)
    return decay**days_old
