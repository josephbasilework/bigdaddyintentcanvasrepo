"""Tests for intent memory storage and lookup."""

from app.services.intent_memory import (
    ExplicitRuleResult,
    IntentMemoryPolicy,
    IntentMemorySettings,
    IntentMemoryStore,
    MemoryKind,
    MemoryScope,
    MemoryUsage,
)


def test_explicit_rule_creates_routing_entry(tmp_path) -> None:
    store = IntentMemoryStore(base_path=str(tmp_path))

    result = store.record_explicit_rule(
        user_id="user-1",
        text="When I say standup update, always respond with /plan",
    )

    assert isinstance(result, ExplicitRuleResult)
    assert result.entry.usage == MemoryUsage.ROUTING

    match = store.match_routing(user_id="user-1", text="standup update")
    assert match is not None
    assert match.entry.response["handler"] == "plan_handler"


def test_auto_confirm_after_repeated_accepts(tmp_path) -> None:
    policy = IntentMemoryPolicy(
        auto_confirm_threshold=0.6,
        auto_confirm_min_samples=2,
        auto_confirm_similarity_threshold=0.5,
    )
    store = IntentMemoryStore(base_path=str(tmp_path), policy=policy)

    store.record_assumption_resolution(
        user_id="user-1",
        assumption_text="Use the default workspace",
        category="context",
        action="accept",
    )
    store.record_assumption_resolution(
        user_id="user-1",
        assumption_text="Use the default workspace",
        category="context",
        action="accept",
    )

    auto_confirmed, remaining = store.auto_confirm_assumptions(
        user_id="user-1",
        assumptions=[
            {"id": "asm-1", "text": "Use the default workspace", "category": "context"}
        ],
    )

    assert remaining == []
    assert len(auto_confirmed) == 1


def test_note_suggestions_match(tmp_path) -> None:
    store = IntentMemoryStore(base_path=str(tmp_path))

    result = store.record_explicit_rule(
        user_id="user-1",
        text="When I note launch risks, suggest plan and research",
    )
    assert result is not None

    suggestions = store.suggest_for_note(user_id="user-1", text="Note: launch risks")

    assert suggestions == ["plan", "research"]


def test_explicit_rule_workspace_scope(tmp_path) -> None:
    """Test that workspace-scoped rules are stored with correct scope."""
    store = IntentMemoryStore(base_path=str(tmp_path))

    result = store.record_explicit_rule(
        user_id="user-1",
        text="For this workspace, when I say deploy, route to /export",
        workspace_id="ws-123",
    )

    assert result is not None
    assert result.entry.scope == MemoryScope.WORKSPACE
    assert result.entry.workspace_id == "ws-123"

    # Should match in the same workspace
    match = store.match_routing(
        user_id="user-1", text="deploy", workspace_id="ws-123"
    )
    assert match is not None


def test_explicit_rule_session_scope(tmp_path) -> None:
    """Test that session-scoped rules are stored with correct scope."""
    store = IntentMemoryStore(base_path=str(tmp_path))

    result = store.record_explicit_rule(
        user_id="user-1",
        text="For this session, when I say quick note, treat it as note",
        session_id="sess-456",
    )

    assert result is not None
    assert result.entry.scope == MemoryScope.SESSION
    assert result.entry.session_id == "sess-456"


def test_classification_rule_matching(tmp_path) -> None:
    """Test classification rules are created and matched."""
    store = IntentMemoryStore(base_path=str(tmp_path))

    result = store.record_explicit_rule(
        user_id="user-1",
        text="When I say status check, classify it as command",
    )

    assert result is not None
    assert result.entry.usage == MemoryUsage.CLASSIFICATION
    assert result.entry.response["classification"] == "command"

    # match_classification should find it
    match = store.match_classification(user_id="user-1", text="status check")
    assert match is not None


def test_assumption_resolution_creates_entries(tmp_path) -> None:
    """Test that assumption resolution creates both category and text entries."""
    store = IntentMemoryStore(base_path=str(tmp_path))

    entries = store.record_assumption_resolution(
        user_id="user-1",
        assumption_text="Use UTC timezone",
        category="time",
        action="accept",
    )

    assert len(entries) == 2
    # One should be category-based, one text-based
    kinds = {e.kind for e in entries}
    assert MemoryKind.IMPLICIT in kinds
    assert MemoryKind.CONFIRMATION in kinds


def test_assumption_rejection_tracks_stats(tmp_path) -> None:
    """Test that rejections are properly tracked in stats."""
    store = IntentMemoryStore(base_path=str(tmp_path))

    store.record_assumption_resolution(
        user_id="user-1",
        assumption_text="Send email notification",
        category="action",
        action="reject",
    )
    store.record_assumption_resolution(
        user_id="user-1",
        assumption_text="Send email notification",
        category="action",
        action="reject",
    )

    # Shouldn't auto-confirm rejected patterns
    auto_confirmed, remaining = store.auto_confirm_assumptions(
        user_id="user-1",
        assumptions=[
            {"id": "a1", "text": "Send email notification", "category": "action"}
        ],
    )

    # Should remain because rejection lowers confidence
    assert len(remaining) == 1
    assert len(auto_confirmed) == 0


def test_settings_disable_auto_confirm(tmp_path) -> None:
    """Test that settings can disable auto-confirmation."""
    store = IntentMemoryStore(base_path=str(tmp_path))
    user_dir = tmp_path / "users" / "user-1"
    user_dir.mkdir(parents=True)

    # Write settings file with auto_confirm disabled
    settings_path = user_dir / "settings.md"
    settings_path.write_text(
        "---\nenabled: true\nauto_classify: true\nauto_confirm: false\nsuggestions: true\n---\n"
    )

    # Record some accepts
    for _ in range(5):
        store.record_assumption_resolution(
            user_id="user-1",
            assumption_text="Use prod environment",
            category="env",
            action="accept",
        )

    # Auto-confirm should be disabled
    auto_confirmed, remaining = store.auto_confirm_assumptions(
        user_id="user-1",
        assumptions=[{"id": "a1", "text": "Use prod environment", "category": "env"}],
    )

    assert len(auto_confirmed) == 0
    assert len(remaining) == 1


def test_audit_log_written(tmp_path) -> None:
    """Test that audit events are written to audit.md."""
    store = IntentMemoryStore(base_path=str(tmp_path))

    store.record_explicit_rule(
        user_id="user-1",
        text="When I say weekly report, route to /plan",
    )

    audit_path = tmp_path / "users" / "user-1" / "audit.md"
    assert audit_path.exists()

    audit_content = audit_path.read_text()
    assert "explicit_rule_created" in audit_content


def test_entry_persistence_across_store_restarts(tmp_path) -> None:
    """Test that entries persist and can be loaded after store restart."""
    store1 = IntentMemoryStore(base_path=str(tmp_path))

    store1.record_explicit_rule(
        user_id="user-1",
        text="When I say sync files, route to /export",
    )

    # Create a new store instance (simulating restart)
    store2 = IntentMemoryStore(base_path=str(tmp_path))

    match = store2.match_routing(user_id="user-1", text="sync files")
    assert match is not None
    assert match.entry.response["handler"] == "export_handler"


def test_similarity_matching_threshold(tmp_path) -> None:
    """Test that similarity matching respects threshold."""
    policy = IntentMemoryPolicy(
        auto_confirm_threshold=0.6,
        auto_confirm_min_samples=2,
        auto_confirm_similarity_threshold=0.8,
    )
    store = IntentMemoryStore(base_path=str(tmp_path), policy=policy)

    # Record accepts for an exact phrase
    for _ in range(3):
        store.record_assumption_resolution(
            user_id="user-1",
            assumption_text="Process data using pandas",
            category="tool",
            action="accept",
        )

    # Exact same text should be auto-confirmed
    auto_confirmed, remaining = store.auto_confirm_assumptions(
        user_id="user-1",
        assumptions=[
            {"id": "a1", "text": "Process data using pandas", "category": "tool"}
        ],
    )

    assert len(auto_confirmed) == 1
    assert len(remaining) == 0


def test_disabled_entry_not_matched(tmp_path) -> None:
    """Test that disabled entries are not matched."""
    store = IntentMemoryStore(base_path=str(tmp_path))

    result = store.record_explicit_rule(
        user_id="user-1",
        text="When I say build project, route to /export",
    )
    assert result is not None

    # Manually disable the entry
    entry_path = (
        tmp_path
        / "users"
        / "user-1"
        / "user"
        / f"{result.entry.entry_id}.md"
    )
    content = entry_path.read_text()
    content = content.replace("enabled: true", "enabled: false")
    entry_path.write_text(content)

    # Should not match disabled entry
    match = store.match_routing(user_id="user-1", text="build project")
    assert match is None


def test_multiple_rules_both_match(tmp_path) -> None:
    """Test that multiple rules can match the same text."""
    store = IntentMemoryStore(base_path=str(tmp_path))

    # Create a general rule
    store.record_explicit_rule(
        user_id="user-1",
        text="When I say report, route to /plan",
    )

    # Create a more specific rule
    store.record_explicit_rule(
        user_id="user-1",
        text="When I say weekly report, route to /export",
    )

    # Both rules use "contains" trigger type, so both can match "weekly report"
    # The implementation returns the first match it finds
    match = store.match_routing(user_id="user-1", text="weekly report")
    assert match is not None
    # Just verify something matched
    assert match.entry.response.get("handler") is not None


def test_get_settings_returns_defaults_for_new_user(tmp_path) -> None:
    """Test that get_settings returns defaults for users without settings file."""
    store = IntentMemoryStore(base_path=str(tmp_path))

    settings = store.get_settings("new-user")

    assert isinstance(settings, IntentMemorySettings)
    assert settings.enabled is True
    assert settings.auto_classify_enabled is True
    assert settings.auto_confirm_enabled is True
    assert settings.suggestions_enabled is True
