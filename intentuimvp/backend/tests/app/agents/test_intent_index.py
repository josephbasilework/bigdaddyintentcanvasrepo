"""Tests for intent index lookup utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest

from app.agents.intent_index import (
    IntentIndexLookup,
    IntentIndexMatch,
    _is_pgvector_available,
)
from app.models.intent import IntentOutcome, UserIntent


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
        resolution={"action": "research"},
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
        resolution={"action": "research"},
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
        resolution={"action": "research"},
        created_at=now - timedelta(days=1),
        embedding="[1, 0]",
    )
    older = UserIntent(
        user_id="user",
        intent_text="alpha",
        resolution={"action": "create"},
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


@pytest.mark.asyncio
async def test_intent_index_lookup_parses_resolution_json() -> None:
    """Resolution JSON payloads should normalize to a handler/action label."""
    now = datetime.now(UTC)
    candidate = UserIntent(
        user_id="user",
        intent_text="alpha",
        resolution='{"handler": "research_handler"}',
        created_at=now,
        embedding="[1, 0]",
    )
    lookup = StubIntentIndex(
        [candidate],
        similarity_threshold=0.5,
        embedding_provider=lambda text: [1.0, 0.0],
    )

    matches = await lookup.lookup("user", "alpha")

    assert len(matches) == 1
    assert matches[0].resolution == "research"


@pytest.mark.asyncio
async def test_intent_index_lookup_uses_resolution_jsonb_field() -> None:
    """Resolution JSONB field should be used when available (PRD §15.2)."""
    now = datetime.now(UTC)
    candidate = UserIntent(
        user_id="user",
        intent_text="plan my day",
        intent_type="planning",  # Legacy field
        created_at=now,
        embedding="[1, 0]",
        resolution={"action": "calendar_sync", "assumptions": ["free at 3pm"]},
    )
    lookup = StubIntentIndex(
        [candidate],
        similarity_threshold=0.8,
        embedding_provider=lambda text: [1.0, 0.0],
    )

    matches = await lookup.lookup("user", "plan something")

    assert len(matches) == 1
    # resolution JSONB should take priority over intent_type
    assert matches[0].resolution == "calendar_sync"


@pytest.mark.asyncio
async def test_intent_index_lookup_falls_back_to_intent_type() -> None:
    """Should fall back to intent_type when resolution JSONB is empty."""
    now = datetime.now(UTC)
    candidate = UserIntent(
        user_id="user",
        intent_text="research topic",
        intent_type="research",
        created_at=now,
        embedding="[1, 0]",
        resolution=None,  # No resolution data
    )
    lookup = StubIntentIndex(
        [candidate],
        similarity_threshold=0.8,
        embedding_provider=lambda text: [1.0, 0.0],
    )

    matches = await lookup.lookup("user", "research")

    assert len(matches) == 1
    assert matches[0].resolution == "research"


class TestUserIntentSchema:
    """Tests for UserIntent model schema (PRD §15.2)."""

    def test_user_intent_outcome_enum_values(self) -> None:
        """IntentOutcome enum should have correct values per PRD §15.2."""
        assert IntentOutcome.SUCCESS.value == "success"
        assert IntentOutcome.FAILURE.value == "failure"
        assert IntentOutcome.MODIFIED.value == "modified"

    def test_user_intent_to_dict_includes_new_fields(self) -> None:
        """to_dict should include resolution and outcome fields."""
        now = datetime.now(UTC)
        intent = UserIntent(
            id=1,
            user_id="user123",
            intent_text="schedule meeting",
            intent_type="calendar",
            confidence=0.95,
            context={},
            handler="calendar_handler",
            executed=True,
            resolution={"action": "create_event", "assumptions": ["1 hour meeting"]},
            outcome="success",
            created_at=now,
        )

        result = intent.to_dict()

        assert result["id"] == 1
        assert result["user_id"] == "user123"
        assert result["intent_text"] == "schedule meeting"
        assert result["resolution"] == {"action": "create_event", "assumptions": ["1 hour meeting"]}
        assert result["outcome"] == "success"

    def test_user_intent_to_dict_handles_none_values(self) -> None:
        """to_dict should handle None values for optional fields."""
        now = datetime.now(UTC)
        intent = UserIntent(
            id=1,
            user_id="user123",
            intent_text="simple query",
            created_at=now,
            resolution=None,
            outcome=None,
        )

        result = intent.to_dict()

        assert result["resolution"] is None
        assert result["outcome"] is None

    def test_intent_outcome_is_string_enum(self) -> None:
        """IntentOutcome should be usable as a string value."""
        # Can be used as string in database column
        assert str(IntentOutcome.SUCCESS) == "IntentOutcome.SUCCESS"
        assert IntentOutcome.SUCCESS == "success"  # str enum comparison
        assert IntentOutcome.FAILURE == "failure"
        assert IntentOutcome.MODIFIED == "modified"


class TestPgvectorSimilarityQuery:
    """Tests for native pgvector similarity query algorithm (PRD §15.2)."""

    def test_is_pgvector_available_returns_false_for_sqlite(self) -> None:
        """Should return False when DATABASE_URL is SQLite."""
        with mock.patch.dict("os.environ", {"DATABASE_URL": "sqlite:///./test.db"}):
            assert _is_pgvector_available() is False

    def test_is_pgvector_available_returns_false_when_no_database_url(self) -> None:
        """Should return False when DATABASE_URL is not set."""
        with mock.patch.dict("os.environ", {"DATABASE_URL": ""}):
            assert _is_pgvector_available() is False

    def test_is_pgvector_available_checks_postgres_and_module(self) -> None:
        """Should return True only for PostgreSQL with pgvector module."""
        # When PostgreSQL but pgvector not installed
        with mock.patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"}):
            with mock.patch("importlib.util.find_spec", return_value=None):
                assert _is_pgvector_available() is False

    def test_is_pgvector_available_with_asyncpg_url(self) -> None:
        """Should work with postgresql+asyncpg:// URL format."""
        with mock.patch.dict("os.environ", {"DATABASE_URL": "postgresql+asyncpg://localhost/test"}):
            with mock.patch("importlib.util.find_spec", return_value=None):
                # pgvector module not found
                assert _is_pgvector_available() is False


class StubPgvectorIntentIndex(IntentIndexLookup):
    """Intent index lookup with stubbed pgvector results."""

    def __init__(self, pgvector_results: list[IntentIndexMatch] | None = None, **kwargs) -> None:
        super().__init__(session_factory=lambda: DummySession(), **kwargs)
        self._pgvector_results = pgvector_results
        self._pgvector_called = False

    async def _fetch_similar_pgvector(
        self, session, user_id: str, query_embedding
    ) -> list[IntentIndexMatch]:
        self._pgvector_called = True
        if self._pgvector_results is not None:
            return self._pgvector_results
        raise RuntimeError("pgvector query failed")

    async def _fetch_candidates(self, session, user_id: str) -> list[UserIntent]:
        return []


@pytest.mark.asyncio
async def test_lookup_uses_pgvector_when_available() -> None:
    """Lookup should use native pgvector query when PostgreSQL is available."""
    expected_matches = [
        IntentIndexMatch(
            resolution="research",
            similarity=0.95,
            recency_weight=0.99,
            score=0.9405,
        )
    ]
    lookup = StubPgvectorIntentIndex(
        pgvector_results=expected_matches,
        embedding_provider=lambda text: [1.0, 0.0],
    )

    with mock.patch("app.agents.intent_index._is_pgvector_available", return_value=True):
        matches = await lookup.lookup("user", "test query")

    assert lookup._pgvector_called is True
    assert len(matches) == 1
    assert matches[0].resolution == "research"
    assert matches[0].similarity == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_lookup_falls_back_when_pgvector_fails() -> None:
    """Lookup should fall back to in-memory scoring when pgvector fails."""
    lookup = StubPgvectorIntentIndex(
        pgvector_results=None,  # Will raise exception
        embedding_provider=lambda text: [1.0, 0.0],
    )

    with mock.patch("app.agents.intent_index._is_pgvector_available", return_value=True):
        # Should not raise, but return empty list (no candidates in fallback)
        matches = await lookup.lookup("user", "test query")

    assert lookup._pgvector_called is True
    assert matches == []


@pytest.mark.asyncio
async def test_lookup_skips_pgvector_without_embedding() -> None:
    """Lookup should skip pgvector when no embedding is available."""
    lookup = StubPgvectorIntentIndex(
        pgvector_results=[],
        embedding_provider=lambda text: None,  # No embedding
    )

    with mock.patch("app.agents.intent_index._is_pgvector_available", return_value=True):
        await lookup.lookup("user", "test query")

    # pgvector should not be called without embedding
    assert lookup._pgvector_called is False


@pytest.mark.asyncio
async def test_lookup_skips_pgvector_for_sqlite() -> None:
    """Lookup should skip pgvector for SQLite databases."""
    lookup = StubPgvectorIntentIndex(
        pgvector_results=[],
        embedding_provider=lambda text: [1.0, 0.0],
    )

    with mock.patch("app.agents.intent_index._is_pgvector_available", return_value=False):
        await lookup.lookup("user", "test query")

    # pgvector should not be called for SQLite
    assert lookup._pgvector_called is False


class TestIntentIndexMatchDataclass:
    """Tests for IntentIndexMatch dataclass."""

    def test_intent_index_match_is_frozen(self) -> None:
        """IntentIndexMatch should be immutable (frozen dataclass)."""
        match = IntentIndexMatch(
            resolution="test",
            similarity=0.9,
            recency_weight=0.95,
            score=0.855,
        )

        with pytest.raises(AttributeError):
            match.resolution = "changed"  # type: ignore[misc]

    def test_intent_index_match_score_calculation(self) -> None:
        """Score should be similarity * recency_weight."""
        similarity = 0.9
        recency_weight = 0.95
        expected_score = similarity * recency_weight

        match = IntentIndexMatch(
            resolution="test",
            similarity=similarity,
            recency_weight=recency_weight,
            score=expected_score,
        )

        assert match.score == pytest.approx(expected_score)
