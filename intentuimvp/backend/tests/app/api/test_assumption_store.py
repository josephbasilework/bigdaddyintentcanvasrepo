"""Tests for assumption store with intent memory integration."""

import pytest

from app.api.assumption_store import AssumptionStore


def test_create_session_with_user_and_workspace() -> None:
    """Test that session stores user_id and workspace_id."""
    store = AssumptionStore(intent_memory_store=None)

    session_id = store.create_session(
        session_id="test-session",
        assumptions=[{"id": "a1", "text": "Test assumption", "category": "test"}],
        user_id="test-user",
        workspace_id="ws-123",
    )

    session = store.get_session(session_id)
    assert session is not None
    assert session["user_id"] == "test-user"
    assert session["workspace_id"] == "ws-123"


def test_resolve_assumption_records_to_intent_memory(tmp_path) -> None:
    """Test that resolving assumptions records to intent memory."""
    from app.services.intent_memory import IntentMemoryStore

    memory_store = IntentMemoryStore(base_path=str(tmp_path))
    store = AssumptionStore(intent_memory_store=memory_store)

    session_id = store.create_session(
        session_id="test-session",
        assumptions=[
            {"id": "a1", "text": "Use UTC timezone", "category": "time"}
        ],
        user_id="test-user",
    )

    store.resolve_assumption(
        session_id=session_id,
        assumption_id="a1",
        action="accept",
        original_text="Use UTC timezone",
        category="time",
    )

    # Check that intent memory has the resolution recorded
    auto_confirmed, remaining = memory_store.auto_confirm_assumptions(
        user_id="test-user",
        assumptions=[
            {"id": "a2", "text": "Use UTC timezone", "category": "time"}
        ],
    )

    # After one accept, should not auto-confirm (needs min samples)
    assert len(remaining) == 1


def test_apply_auto_confirm_with_learned_patterns(tmp_path) -> None:
    """Test auto-confirmation applies learned patterns."""
    from app.services.intent_memory import IntentMemoryPolicy, IntentMemoryStore

    policy = IntentMemoryPolicy(
        auto_confirm_threshold=0.6,
        auto_confirm_min_samples=2,
        auto_confirm_similarity_threshold=0.5,
    )
    memory_store = IntentMemoryStore(base_path=str(tmp_path), policy=policy)
    store = AssumptionStore(intent_memory_store=memory_store)

    # Record accepts directly to memory to establish pattern
    memory_store.record_assumption_resolution(
        user_id="test-user",
        assumption_text="Use production database",
        category="environment",
        action="accept",
    )
    memory_store.record_assumption_resolution(
        user_id="test-user",
        assumption_text="Use production database",
        category="environment",
        action="accept",
    )

    # Create session with similar assumption
    session_id = store.create_session(
        session_id="test-session",
        assumptions=[
            {"id": "a1", "text": "Use production database", "category": "environment"}
        ],
        user_id="test-user",
    )

    auto_confirmed, remaining = store.apply_auto_confirm(session_id)

    assert len(auto_confirmed) == 1
    assert auto_confirmed[0]["id"] == "a1"
    assert len(remaining) == 0

    # Check that auto-confirmed assumption was recorded as resolved
    resolved = store.get_resolved_assumptions(session_id)
    assert len(resolved) == 1
    assert resolved[0]["action"] == "accept"
    assert resolved[0]["source"] == "auto_confirm"


def test_apply_auto_confirm_returns_remaining(tmp_path) -> None:
    """Test that apply_auto_confirm returns assumptions that need user confirmation."""
    from app.services.intent_memory import IntentMemoryStore

    memory_store = IntentMemoryStore(base_path=str(tmp_path))
    store = AssumptionStore(intent_memory_store=memory_store)

    session_id = store.create_session(
        session_id="test-session",
        assumptions=[
            {"id": "a1", "text": "Use staging database", "category": "environment"},
            {"id": "a2", "text": "Process in batch mode", "category": "mode"},
        ],
        user_id="test-user",
    )

    # No patterns learned yet, so all should remain
    auto_confirmed, remaining = store.apply_auto_confirm(session_id)

    assert len(auto_confirmed) == 0
    assert len(remaining) == 2


def test_apply_auto_confirm_without_user_id(tmp_path) -> None:
    """Test that apply_auto_confirm works without user_id (returns all as remaining)."""
    from app.services.intent_memory import IntentMemoryStore

    memory_store = IntentMemoryStore(base_path=str(tmp_path))
    store = AssumptionStore(intent_memory_store=memory_store)

    # Create session without user_id
    session_id = store.create_session(
        session_id="test-session",
        assumptions=[{"id": "a1", "text": "Test", "category": "test"}],
    )

    auto_confirmed, remaining = store.apply_auto_confirm(session_id)

    assert len(auto_confirmed) == 0
    assert len(remaining) == 1


def test_apply_auto_confirm_updates_expected_ids(tmp_path) -> None:
    """Test that auto-confirm updates expected_assumption_ids correctly."""
    from app.services.intent_memory import IntentMemoryPolicy, IntentMemoryStore

    policy = IntentMemoryPolicy(
        auto_confirm_threshold=0.6,
        auto_confirm_min_samples=2,
        auto_confirm_similarity_threshold=0.5,
    )
    memory_store = IntentMemoryStore(base_path=str(tmp_path), policy=policy)
    store = AssumptionStore(intent_memory_store=memory_store)

    # Learn a pattern
    for _ in range(3):
        memory_store.record_assumption_resolution(
            user_id="test-user",
            assumption_text="Use default settings",
            category="config",
            action="accept",
        )

    session_id = store.create_session(
        session_id="test-session",
        assumptions=[
            {"id": "a1", "text": "Use default settings", "category": "config"},
            {"id": "a2", "text": "Something new", "category": "other"},
        ],
        user_id="test-user",
    )

    store.apply_auto_confirm(session_id)

    session = store.get_session(session_id)
    # Only a2 should remain in expected_assumption_ids
    assert session["expected_assumption_ids"] == ["a2"]


def test_resolve_assumption_without_intent_memory() -> None:
    """Test that resolve_assumption works when intent memory is None."""
    store = AssumptionStore(intent_memory_store=None)

    session_id = store.create_session(
        session_id="test-session",
        assumptions=[{"id": "a1", "text": "Test", "category": "test"}],
        user_id="test-user",
    )

    # Should not raise even without intent memory
    resolution = store.resolve_assumption(
        session_id=session_id,
        assumption_id="a1",
        action="accept",
        original_text="Test",
        category="test",
    )

    assert resolution["action"] == "accept"


@pytest.mark.asyncio
async def test_wait_for_completion_after_auto_confirm(tmp_path) -> None:
    """Test that auto-confirm updates session state correctly."""
    from app.services.intent_memory import IntentMemoryPolicy, IntentMemoryStore

    policy = IntentMemoryPolicy(
        auto_confirm_threshold=0.6,
        auto_confirm_min_samples=2,
        auto_confirm_similarity_threshold=0.5,
    )
    memory_store = IntentMemoryStore(base_path=str(tmp_path), policy=policy)
    store = AssumptionStore(intent_memory_store=memory_store)

    # Learn pattern
    for _ in range(3):
        memory_store.record_assumption_resolution(
            user_id="test-user",
            assumption_text="Use JSON format",
            category="format",
            action="accept",
        )

    session_id = store.create_session(
        session_id="test-session",
        assumptions=[{"id": "a1", "text": "Use JSON format", "category": "format"}],
        user_id="test-user",
    )

    # Auto-confirm all assumptions
    auto_confirmed, remaining = store.apply_auto_confirm(session_id)

    # Verify auto-confirm worked
    assert len(auto_confirmed) == 1
    assert len(remaining) == 0

    # Verify resolved assumption was recorded
    resolved = store.get_resolved_assumptions(session_id)
    assert len(resolved) == 1
    assert resolved[0]["source"] == "auto_confirm"

    # Session should show no remaining expected assumptions
    session = store.get_session(session_id)
    assert session["expected_assumption_ids"] == []


def test_multiple_resolutions_accumulate_learning(tmp_path) -> None:
    """Test that multiple resolution actions accumulate learning."""
    from app.services.intent_memory import IntentMemoryPolicy, IntentMemoryStore

    policy = IntentMemoryPolicy(
        auto_confirm_threshold=0.6,
        auto_confirm_min_samples=3,
        auto_confirm_similarity_threshold=0.5,
    )
    memory_store = IntentMemoryStore(base_path=str(tmp_path), policy=policy)
    store = AssumptionStore(intent_memory_store=memory_store)

    # Create and resolve multiple sessions
    for i in range(3):
        session_id = store.create_session(
            session_id=f"session-{i}",
            assumptions=[{"id": "a1", "text": "Enable caching", "category": "perf"}],
            user_id="test-user",
        )
        store.resolve_assumption(
            session_id=session_id,
            assumption_id="a1",
            action="accept",
            original_text="Enable caching",
            category="perf",
        )

    # Now create new session with same assumption
    new_session = store.create_session(
        session_id="session-final",
        assumptions=[{"id": "a1", "text": "Enable caching", "category": "perf"}],
        user_id="test-user",
    )

    auto_confirmed, remaining = store.apply_auto_confirm(new_session)

    # Should auto-confirm based on accumulated learning
    assert len(auto_confirmed) == 1
    assert len(remaining) == 0
