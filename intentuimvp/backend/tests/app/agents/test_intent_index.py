"""Tests for intent index lookup utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.intent_index import IntentIndexLookup
from app.models.intent import UserIntent


class DummySession:
    """Minimal async context manager for lookup tests."""

    async def __aenter__(self) -> DummySession:
        return self

    async def __aexit__(self, exc_type, exc, exc_tb) -> None:
        return None


class StubIntentIndex(IntentIndexLookup):
    """Intent index lookup with stubbed candidates."""

    def __init__(self, candidates: list[UserIntent], **kwargs) -> None:
        super().__init__(session_factory=lambda: DummySession(), **kwargs)
        self._candidates = candidates

    async def _fetch_candidates(self, session, user_id: str) -> list[UserIntent]:
        return list(self._candidates)


@pytest.mark.asyncio
async def test_intent_index_lookup_uses_embeddings_when_available() -> None:
    """Matches should use embedding similarity when provided."""
    now = datetime.now(UTC)
    candidate = UserIntent(
        user_id="user",
        intent_text="completely different text",
        intent_type="research",
        created_at=now,
        embedding="[1, 0]",
    )
    lookup = StubIntentIndex(
        [candidate],
        similarity_threshold=0.8,
        embedding_provider=lambda text: [1.0, 0.0],
    )

    matches = await lookup.lookup("user", "alpha")

    assert len(matches) == 1
    assert matches[0].resolution == "research"
    assert matches[0].similarity == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_intent_index_lookup_falls_back_to_text_similarity() -> None:
    """Text similarity should be used if embeddings are unavailable."""
    now = datetime.now(UTC)
    candidate = UserIntent(
        user_id="user",
        intent_text="alpha beta",
        intent_type="research",
        created_at=now,
        embedding="not-a-vector",
    )
    lookup = StubIntentIndex(
        [candidate],
        similarity_threshold=0.8,
        embedding_provider=lambda text: None,
    )

    matches = await lookup.lookup("user", "alpha beta")

    assert len(matches) == 1
    assert matches[0].similarity == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_intent_index_lookup_ranks_by_recency() -> None:
    """Recent matches should outrank older ones with equal similarity."""
    now = datetime.now(UTC)
    recent = UserIntent(
        user_id="user",
        intent_text="alpha",
        intent_type="research",
        created_at=now - timedelta(days=1),
        embedding="[1, 0]",
    )
    older = UserIntent(
        user_id="user",
        intent_text="alpha",
        intent_type="create",
        created_at=now - timedelta(days=10),
        embedding="[1, 0]",
    )
    lookup = StubIntentIndex(
        [older, recent],
        similarity_threshold=0.5,
        embedding_provider=lambda text: [1.0, 0.0],
    )

    matches = await lookup.lookup("user", "alpha")

    assert len(matches) == 2
    assert matches[0].recency_weight > matches[1].recency_weight
    assert matches[0].score > matches[1].score
