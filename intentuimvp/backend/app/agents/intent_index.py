"""Intent index lookup utilities for confidence adjustment."""

from __future__ import annotations

import difflib
import json
import logging
import math
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
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
        """Return top intent index matches for the input text."""
        normalized_input = _normalize_text(input_text)
        if not normalized_input:
            return []

        input_embedding: list[float] | None = None
        if self._embedding_provider is not None:
            try:
                input_embedding = _parse_embedding(
                    self._embedding_provider(input_text)
                )
            except Exception:
                logger.warning(
                    "Intent index embedding generation failed", exc_info=True
                )
                input_embedding = None

        try:
            async with self._session_factory() as session:
                candidates = await self._fetch_candidates(session, user_id)
        except Exception:
            logger.warning("Intent index lookup failed", exc_info=True)
            return []

        return self._score_candidates(
            normalized_input, candidates, input_embedding=input_embedding
        )

    async def _fetch_candidates(
        self, session: AsyncSession, user_id: str
    ) -> list[UserIntent]:
        stmt = (
            select(UserIntent)
            .where(UserIntent.user_id == user_id)
            .order_by(UserIntent.created_at.desc())
            .limit(self._candidate_limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

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
            if not candidate.intent_text:
                continue
            similarity = _candidate_similarity(
                normalized_input, candidate, input_embedding
            )
            if similarity < self._similarity_threshold:
                continue
            recency_weight = _recency_weight(
                candidate.created_at, now=now, decay=self._recency_decay
            )
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
    resolution = candidate.intent_type or candidate.handler
    if not resolution:
        return None
    normalized = resolution.strip().lower()
    if normalized.endswith("_handler"):
        normalized = normalized[: -len("_handler")]
    return normalized or None


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
    normalized_candidate = _normalize_text(candidate.intent_text)
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
    dot = sum(
        left * right for left, right in zip(input_embedding, candidate_embedding)
    )
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


def _recency_weight(
    created_at: datetime | None, *, now: datetime, decay: float
) -> float:
    if created_at is None:
        return 1.0
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    days_old = max((now - created_at).total_seconds() / 86400.0, 0.0)
    return decay**days_old
