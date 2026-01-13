"""Tests for intent index persistence helpers.

Tests for IntentIndexStore insert/update/prune operations per PRD §15.2.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.intent_index import _parse_embedding
from app.models.intent import Base as IntentBase
from app.models.intent import IntentOutcome, UserIntent
from app.services.intent_index import IntentIndexStore

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async test engine with in-memory database."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(IntentBase.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(IntentBase.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def session_factory(async_engine):
    """Create async session factory for tests."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture(scope="function")
async def store(session_factory):
    """Create an IntentIndexStore with a stub embedding provider."""
    return IntentIndexStore(
        session_factory=session_factory,
        embedding_provider=lambda text: [0.1, 0.2, 0.3],
    )


@pytest.mark.asyncio
async def test_insert_intent_stores_embedding_and_resolution(session_factory) -> None:
    """Insert should persist embeddings and resolution metadata."""
    store = IntentIndexStore(
        session_factory=session_factory,
        embedding_provider=lambda text: [0.1, 0.2],
    )

    record = await store.insert_intent(
        user_id="user-1",
        intent_text="Find sources",
        resolution={"action": "research"},
        context={"source": "hitl"},
    )

    assert record.id is not None
    assert record.user_id == "user-1"
    assert record.resolution == {"action": "research"}
    assert _parse_embedding(record.embedding) == [0.1, 0.2]


@pytest.mark.asyncio
async def test_update_outcome_updates_fields(session_factory) -> None:
    """Outcome updates should persist status and metadata changes."""
    store = IntentIndexStore(
        session_factory=session_factory,
        embedding_provider=lambda text: None,
    )

    record = await store.insert_intent(
        user_id="user-2",
        intent_text="Plan my day",
        resolution=None,
    )

    updated = await store.update_outcome(
        record.id,
        IntentOutcome.SUCCESS,
        resolution={"action": "plan"},
        executed=True,
    )

    assert updated is not None
    assert updated.outcome == IntentOutcome.SUCCESS
    assert updated.executed is True
    assert updated.resolution == {"action": "plan"}


@pytest.mark.asyncio
async def test_prune_failed_removes_old_failures(session_factory) -> None:
    """Prune should remove only stale failure entries."""
    store = IntentIndexStore(
        session_factory=session_factory,
        embedding_provider=lambda text: None,
    )
    now = datetime.utcnow()

    old_failure = await store.insert_intent(
        user_id="user-3",
        intent_text="Old failed",
        outcome=IntentOutcome.FAILURE,
        created_at=now - timedelta(days=100),
    )
    recent_failure = await store.insert_intent(
        user_id="user-3",
        intent_text="Recent failed",
        outcome=IntentOutcome.FAILURE,
        created_at=now - timedelta(days=10),
    )
    old_success = await store.insert_intent(
        user_id="user-3",
        intent_text="Old success",
        outcome=IntentOutcome.SUCCESS,
        created_at=now - timedelta(days=100),
    )

    pruned = await store.prune_failed(cutoff_days=90, now=now)
    assert pruned == 1

    async with session_factory() as session:
        result = await session.execute(select(UserIntent))
        remaining = result.scalars().all()

    remaining_ids = {intent.id for intent in remaining}
    assert remaining_ids == {recent_failure.id, old_success.id}
    assert old_failure.id not in remaining_ids


class TestGetIntent:
    """Tests for get_intent method."""

    @pytest.mark.asyncio
    async def test_get_intent_returns_existing(self, store) -> None:
        """Get should return intent when it exists."""
        record = await store.insert_intent(
            user_id="user-get",
            intent_text="Test intent",
        )

        result = await store.get_intent(record.id)

        assert result is not None
        assert result.id == record.id
        assert result.intent_text == "Test intent"

    @pytest.mark.asyncio
    async def test_get_intent_returns_none_for_missing(self, store) -> None:
        """Get should return None when intent doesn't exist."""
        result = await store.get_intent(99999)
        assert result is None


class TestUpdateIntent:
    """Tests for update_intent method with re-embedding."""

    @pytest.mark.asyncio
    async def test_update_intent_text_regenerates_embedding(
        self, session_factory
    ) -> None:
        """Updating intent text should regenerate embedding."""
        embeddings_generated = []

        def track_embeddings(text: str) -> list[float]:
            embeddings_generated.append(text)
            return [float(len(text)), 0.5, 0.5]

        store = IntentIndexStore(
            session_factory=session_factory,
            embedding_provider=track_embeddings,
        )

        record = await store.insert_intent(
            user_id="user-update",
            intent_text="Original text",
        )
        original_embedding = _parse_embedding(record.embedding)

        updated = await store.update_intent(
            record.id,
            intent_text="New different text",
        )

        assert updated is not None
        assert updated.intent_text == "New different text"
        new_embedding = _parse_embedding(updated.embedding)
        assert new_embedding != original_embedding
        assert len(embeddings_generated) == 2

    @pytest.mark.asyncio
    async def test_update_intent_metadata_only(self, store) -> None:
        """Updating metadata should not change embedding."""
        record = await store.insert_intent(
            user_id="user-meta",
            intent_text="Keep this text",
        )
        original_embedding = record.embedding

        updated = await store.update_intent(
            record.id,
            resolution={"action": "updated"},
            handler="new_handler",
            confidence=0.95,
        )

        assert updated is not None
        assert updated.resolution == {"action": "updated"}
        assert updated.handler == "new_handler"
        assert updated.confidence == 0.95
        assert updated.embedding == original_embedding
        assert updated.intent_text == "Keep this text"

    @pytest.mark.asyncio
    async def test_update_intent_returns_none_for_missing(self, store) -> None:
        """Update should return None for non-existent intent."""
        result = await store.update_intent(
            99999,
            intent_text="Won't work",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_intent_outcome(self, store) -> None:
        """Updating outcome via update_intent should work."""
        record = await store.insert_intent(
            user_id="user-outcome",
            intent_text="Test outcome",
        )

        updated = await store.update_intent(
            record.id,
            outcome=IntentOutcome.SUCCESS,
            executed=True,
        )

        assert updated is not None
        assert updated.outcome == IntentOutcome.SUCCESS
        assert updated.executed is True


class TestListUserIntents:
    """Tests for list_user_intents method."""

    @pytest.mark.asyncio
    async def test_list_user_intents_returns_user_intents(self, store) -> None:
        """Should return only intents for the specified user."""
        await store.insert_intent(user_id="user-a", intent_text="Intent A1")
        await store.insert_intent(user_id="user-a", intent_text="Intent A2")
        await store.insert_intent(user_id="user-b", intent_text="Intent B1")

        results = await store.list_user_intents("user-a")

        assert len(results) == 2
        assert all(r.user_id == "user-a" for r in results)

    @pytest.mark.asyncio
    async def test_list_user_intents_filters_by_outcome(self, store) -> None:
        """Should filter by outcome when specified."""
        await store.insert_intent(
            user_id="user-filter",
            intent_text="Success",
            outcome=IntentOutcome.SUCCESS,
        )
        await store.insert_intent(
            user_id="user-filter",
            intent_text="Failure",
            outcome=IntentOutcome.FAILURE,
        )

        results = await store.list_user_intents(
            "user-filter", outcome=IntentOutcome.SUCCESS
        )

        assert len(results) == 1
        assert results[0].outcome == IntentOutcome.SUCCESS

    @pytest.mark.asyncio
    async def test_list_user_intents_pagination(self, store) -> None:
        """Should support pagination."""
        for i in range(5):
            await store.insert_intent(
                user_id="user-page", intent_text=f"Intent {i}"
            )

        page1 = await store.list_user_intents("user-page", offset=0, limit=2)
        page2 = await store.list_user_intents("user-page", offset=2, limit=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    @pytest.mark.asyncio
    async def test_list_user_intents_empty_user_id(self, store) -> None:
        """Should return empty list for empty user_id."""
        results = await store.list_user_intents("")
        assert results == []


class TestDeleteIntent:
    """Tests for delete_intent method."""

    @pytest.mark.asyncio
    async def test_delete_intent_removes_existing(self, store) -> None:
        """Delete should remove existing intent."""
        record = await store.insert_intent(
            user_id="user-del",
            intent_text="To delete",
        )

        result = await store.delete_intent(record.id)
        assert result is True

        retrieved = await store.get_intent(record.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_intent_returns_false_for_missing(self, store) -> None:
        """Delete should return False for non-existent intent."""
        result = await store.delete_intent(99999)
        assert result is False


class TestPruneAllOld:
    """Tests for prune_all_old method."""

    @pytest.mark.asyncio
    async def test_prune_all_old_removes_regardless_of_outcome(
        self, session_factory
    ) -> None:
        """Should remove all old intents regardless of outcome."""
        store = IntentIndexStore(
            session_factory=session_factory,
            embedding_provider=lambda text: None,
        )
        now = datetime.utcnow()

        await store.insert_intent(
            user_id="user-prune",
            intent_text="Old success",
            outcome=IntentOutcome.SUCCESS,
            created_at=now - timedelta(days=400),
        )
        await store.insert_intent(
            user_id="user-prune",
            intent_text="Old failure",
            outcome=IntentOutcome.FAILURE,
            created_at=now - timedelta(days=400),
        )
        recent = await store.insert_intent(
            user_id="user-prune",
            intent_text="Recent",
            created_at=now - timedelta(days=10),
        )

        pruned = await store.prune_all_old(cutoff_days=360, now=now)
        assert pruned == 2

        remaining = await store.list_user_intents("user-prune")
        assert len(remaining) == 1
        assert remaining[0].id == recent.id

    @pytest.mark.asyncio
    async def test_prune_all_old_respects_user_scope(
        self, session_factory
    ) -> None:
        """Should only prune for specified user when user_id provided."""
        store = IntentIndexStore(
            session_factory=session_factory,
            embedding_provider=lambda text: None,
        )
        now = datetime.utcnow()

        await store.insert_intent(
            user_id="user-x",
            intent_text="Old X",
            created_at=now - timedelta(days=400),
        )
        await store.insert_intent(
            user_id="user-y",
            intent_text="Old Y",
            created_at=now - timedelta(days=400),
        )

        pruned = await store.prune_all_old(cutoff_days=360, user_id="user-x", now=now)
        assert pruned == 1

        remaining_x = await store.list_user_intents("user-x")
        remaining_y = await store.list_user_intents("user-y")
        assert len(remaining_x) == 0
        assert len(remaining_y) == 1


class TestInsertIntentValidation:
    """Tests for insert_intent validation."""

    @pytest.mark.asyncio
    async def test_insert_intent_rejects_empty_user_id(self, store) -> None:
        """Should reject empty user_id."""
        with pytest.raises(ValueError, match="user_id is required"):
            await store.insert_intent(user_id="", intent_text="Test")

    @pytest.mark.asyncio
    async def test_insert_intent_rejects_empty_text(self, store) -> None:
        """Should reject empty intent_text."""
        with pytest.raises(ValueError, match="intent_text is required"):
            await store.insert_intent(user_id="user", intent_text="")

    @pytest.mark.asyncio
    async def test_insert_intent_strips_whitespace(self, store) -> None:
        """Should strip whitespace from user_id and intent_text."""
        record = await store.insert_intent(
            user_id="  user-ws  ",
            intent_text="  Test intent  ",
        )

        assert record.user_id == "user-ws"
        assert record.intent_text == "Test intent"


class TestUpdateOutcomeValidation:
    """Tests for update_outcome validation."""

    @pytest.mark.asyncio
    async def test_update_outcome_accepts_string_outcome(self, store) -> None:
        """Should accept string outcome values."""
        record = await store.insert_intent(
            user_id="user-str",
            intent_text="Test",
        )

        updated = await store.update_outcome(record.id, "success")

        assert updated is not None
        assert updated.outcome == IntentOutcome.SUCCESS

    @pytest.mark.asyncio
    async def test_update_outcome_rejects_invalid_outcome(self, store) -> None:
        """Should reject invalid outcome values."""
        record = await store.insert_intent(
            user_id="user-inv",
            intent_text="Test",
        )

        with pytest.raises(ValueError, match="Invalid intent outcome"):
            await store.update_outcome(record.id, "invalid_outcome")
