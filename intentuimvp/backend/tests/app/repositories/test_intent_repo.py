"""Tests for IntentRepository insert/update/prune operations."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.intent import Base, IntentOutcome
from app.repositories.intent_repo import IntentRepository


@pytest_asyncio.fixture
async def async_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine):
    """Create a test database session."""
    async_session_maker = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service for testing."""
    mock = MagicMock()
    mock.encode.return_value = [0.1] * 384  # 384-dim embedding
    return mock


def _mock_get_embedding_service(mock: MagicMock) -> Callable[[], Any]:
    """Create a typed lambda for patching get_embedding_service."""
    return lambda: mock


@pytest.mark.asyncio
class TestIntentRepository:
    """Tests for IntentRepository."""

    async def test_insert_intent_creates_record_with_embedding(
        self, db_session, mock_embedding_service
    ):
        """Test insert_intent creates a UserIntent with embedding."""
        # Patch get_embedding_service to return mock
        import app.repositories.intent_repo

        original_get = app.repositories.intent_repo.get_embedding_service
        app.repositories.intent_repo.get_embedding_service = _mock_get_embedding_service(
            mock_embedding_service
        )

        try:
            repo = IntentRepository(db_session)

            intent = await repo.insert_intent(
                user_id="user123",
                intent_text="Create a new canvas",
                intent_type="create_canvas",
                confidence=0.9,
                context={"node_id": "abc"},
                handler="CanvasHandler",
            )

            assert intent.id is not None
            assert intent.user_id == "user123"
            assert intent.intent_text == "Create a new canvas"
            assert intent.intent_type == "create_canvas"
            assert intent.confidence == 0.9
            assert intent.context == {"node_id": "abc"}
            assert intent.handler == "CanvasHandler"
            assert intent.executed is False
            assert intent.outcome is None
            # Embedding stored as comma-separated string for SQLite
            assert intent.embedding == ",".join(str(0.1) for _ in range(384))

            mock_embedding_service.encode.assert_called_once_with(
                "Create a new canvas"
            )
        finally:
            app.repositories.intent_repo.get_embedding_service = original_get

    async def test_insert_intent_with_resolution(self, db_session, mock_embedding_service):
        """Test insert_intent stores resolution data."""
        import app.repositories.intent_repo

        original_get = app.repositories.intent_repo.get_embedding_service
        app.repositories.intent_repo.get_embedding_service = _mock_get_embedding_service(
    mock_embedding_service
)

        try:
            repo = IntentRepository(db_session)

            resolution = {
                "assumptions": [
                    {"id": "a1", "text": "Use default settings", "action": "accept"}
                ],
                "action": "create_canvas",
            }

            intent = await repo.insert_intent(
                user_id="user456",
                intent_text="Make a canvas",
                resolution=resolution,
            )

            assert intent.resolution == resolution
        finally:
            app.repositories.intent_repo.get_embedding_service = original_get

    async def test_insert_intent_empty_text_raises_error(self, db_session):
        """Test insert_intent raises ValueError for empty intent_text."""
        repo = IntentRepository(db_session)

        with pytest.raises(ValueError, match="intent_text cannot be empty"):
            await repo.insert_intent(user_id="user123", intent_text="   ")

    async def test_update_outcome_success(self, db_session, mock_embedding_service):
        """Test update_outcome modifies intent outcome."""
        import app.repositories.intent_repo

        original_get = app.repositories.intent_repo.get_embedding_service
        app.repositories.intent_repo.get_embedding_service = _mock_get_embedding_service(
    mock_embedding_service
)

        try:
            repo = IntentRepository(db_session)

            # First insert an intent
            intent = await repo.insert_intent(
                user_id="user789",
                intent_text="Update this intent",
            )

            # Update outcome
            updated = await repo.update_outcome(
                intent_id=intent.id,
                outcome=IntentOutcome.SUCCESS,
                resolution={"result": "canvas_created"},
            )

            assert updated is not None
            assert updated.id == intent.id
            assert updated.outcome == IntentOutcome.SUCCESS
            assert updated.executed is True
            assert updated.resolution == {"result": "canvas_created"}
        finally:
            app.repositories.intent_repo.get_embedding_service = original_get

    async def test_update_outcome_failure(self, db_session, mock_embedding_service):
        """Test update_outcome with failure outcome."""
        import app.repositories.intent_repo

        original_get = app.repositories.intent_repo.get_embedding_service
        app.repositories.intent_repo.get_embedding_service = _mock_get_embedding_service(
    mock_embedding_service
)

        try:
            repo = IntentRepository(db_session)

            intent = await repo.insert_intent(
                user_id="user999",
                intent_text="This will fail",
            )

            updated = await repo.update_outcome(
                intent_id=intent.id,
                outcome=IntentOutcome.FAILURE,
            )

            assert updated.outcome == IntentOutcome.FAILURE
            assert updated.executed is True
        finally:
            app.repositories.intent_repo.get_embedding_service = original_get

    async def test_update_outcome_nonexistent_returns_none(self, db_session):
        """Test update_outcome returns None for non-existent intent."""
        repo = IntentRepository(db_session)

        result = await repo.update_outcome(
            intent_id=99999, outcome=IntentOutcome.SUCCESS
        )

        assert result is None

    async def test_prune_old_failed_intents(self, db_session, mock_embedding_service):
        """Test prune_old_failed_intents removes old failed intents."""
        import app.repositories.intent_repo

        original_get = app.repositories.intent_repo.get_embedding_service
        app.repositories.intent_repo.get_embedding_service = _mock_get_embedding_service(
    mock_embedding_service
)

        try:
            repo = IntentRepository(db_session)

            # Create old failed intent (manually set created_at)
            old_failed = await repo.insert_intent(
                user_id="user_old",
                intent_text="Old failed intent",
            )
            old_failed.outcome = IntentOutcome.FAILURE
            old_failed.created_at = datetime.utcnow() - timedelta(days=100)
            db_session.add(old_failed)
            await db_session.commit()

            # Create recent failed intent
            recent_failed = await repo.insert_intent(
                user_id="user_recent",
                intent_text="Recent failed intent",
            )
            recent_failed.outcome = IntentOutcome.FAILURE
            db_session.add(recent_failed)
            await db_session.commit()

            # Create successful intent
            success_intent = await repo.insert_intent(
                user_id="user_success",
                intent_text="Success intent",
            )
            success_intent.outcome = IntentOutcome.SUCCESS
            success_intent.created_at = datetime.utcnow() - timedelta(days=100)
            db_session.add(success_intent)
            await db_session.commit()

            # Prune with 90-day cutoff
            deleted_count = await repo.prune_old_failed_intents(cutoff_days=90)

            # Should only delete the old failed intent
            assert deleted_count == 1

            # Verify old failed intent is gone
            remaining = await repo.list_by_user("user_old")
            assert len(remaining) == 0

            # Verify recent failed intent still exists
            remaining = await repo.list_by_user("user_recent")
            assert len(remaining) == 1

            # Verify success intent still exists
            remaining = await repo.list_by_user("user_success")
            assert len(remaining) == 1
        finally:
            app.repositories.intent_repo.get_embedding_service = original_get

    async def test_prune_returns_zero_when_no_matching_intents(
        self, db_session, mock_embedding_service
    ):
        """Test prune returns 0 when no intents match criteria."""
        import app.repositories.intent_repo

        original_get = app.repositories.intent_repo.get_embedding_service
        app.repositories.intent_repo.get_embedding_service = _mock_get_embedding_service(
    mock_embedding_service
)

        try:
            repo = IntentRepository(db_session)

            # Create recent failed intent
            intent = await repo.insert_intent(
                user_id="user_recent",
                intent_text="Recent failed intent",
            )
            intent.outcome = IntentOutcome.FAILURE
            db_session.add(intent)
            await db_session.commit()

            # Prune with large cutoff - nothing should be deleted
            deleted_count = await repo.prune_old_failed_intents(cutoff_days=365)

            assert deleted_count == 0
        finally:
            app.repositories.intent_repo.get_embedding_service = original_get

    async def test_list_by_user(self, db_session, mock_embedding_service):
        """Test list_by_user returns user's intents in descending order."""
        import app.repositories.intent_repo

        original_get = app.repositories.intent_repo.get_embedding_service
        app.repositories.intent_repo.get_embedding_service = _mock_get_embedding_service(
    mock_embedding_service
)

        try:
            repo = IntentRepository(db_session)

            # Create multiple intents for same user
            await repo.insert_intent(user_id="user_list", intent_text="First intent")
            await repo.insert_intent(user_id="user_list", intent_text="Second intent")
            await repo.insert_intent(
                user_id="user_other", intent_text="Other user intent"
            )

            intents = await repo.list_by_user("user_list")

            assert len(intents) == 2
            assert all(i.user_id == "user_list" for i in intents)
            # Should be in descending created_at order
            assert intents[0].created_at >= intents[1].created_at
        finally:
            app.repositories.intent_repo.get_embedding_service = original_get

    async def test_get_by_user_and_outcome(self, db_session, mock_embedding_service):
        """Test get_by_user_and_outcome filters correctly."""
        import app.repositories.intent_repo

        original_get = app.repositories.intent_repo.get_embedding_service
        app.repositories.intent_repo.get_embedding_service = _mock_get_embedding_service(
    mock_embedding_service
)

        try:
            repo = IntentRepository(db_session)

            # Create intents with different outcomes
            success1 = await repo.insert_intent(
                user_id="user_filter", intent_text="Success 1"
            )
            success1.outcome = IntentOutcome.SUCCESS
            db_session.add(success1)

            failed1 = await repo.insert_intent(
                user_id="user_filter", intent_text="Failed 1"
            )
            failed1.outcome = IntentOutcome.FAILURE
            db_session.add(failed1)

            success2 = await repo.insert_intent(
                user_id="user_filter", intent_text="Success 2"
            )
            success2.outcome = IntentOutcome.SUCCESS
            db_session.add(success2)

            await db_session.commit()

            # Get only successful intents
            success_intents = await repo.get_by_user_and_outcome(
                "user_filter", IntentOutcome.SUCCESS
            )
            assert len(success_intents) == 2

            # Get only failed intents
            failed_intents = await repo.get_by_user_and_outcome(
                "user_filter", IntentOutcome.FAILURE
            )
            assert len(failed_intents) == 1
        finally:
            app.repositories.intent_repo.get_embedding_service = original_get

    async def test_count_returns_total_intents(self, db_session, mock_embedding_service):
        """Test count returns total number of intents."""
        import app.repositories.intent_repo

        original_get = app.repositories.intent_repo.get_embedding_service
        app.repositories.intent_repo.get_embedding_service = _mock_get_embedding_service(
    mock_embedding_service
)

        try:
            repo = IntentRepository(db_session)

            initial_count = await repo.count()

            await repo.insert_intent(user_id="user1", intent_text="Intent 1")
            await repo.insert_intent(user_id="user2", intent_text="Intent 2")

            final_count = await repo.count()
            assert final_count == initial_count + 2
        finally:
            app.repositories.intent_repo.get_embedding_service = original_get
