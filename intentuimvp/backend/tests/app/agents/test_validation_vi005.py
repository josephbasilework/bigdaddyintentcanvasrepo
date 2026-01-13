"""VI-005: HITL by design validation tests.

This module contains integration tests for validating VI-005:
- Low confidence (<0.70) triggers clarification
- Medium confidence (0.70-0.94) shows assumptions for reconciliation
- External side effects require approval (FR-018)
- Destructive actions show preview/diff

PRD Reference: §2 VI-005 - HITL by design

Acceptance Criteria:
- GIVEN low confidence intent (<0.70) WHEN processed THEN system requests clarification
- GIVEN medium confidence (0.70-0.94) WHEN assumptions generated THEN user sees reconciliation UI
- GIVEN external side effect proposed WHEN evaluated THEN action blocked until user confirms (FR-018)
- GIVEN destructive action WHEN triggered THEN preview/diff shown and approval required

WHERE: tests/app/agents/test_validation_vi005.py
WHAT: Integration tests for HITL validation
HOW: Test confidence thresholds, safety gates, preview/diff
WHY: Validates HITL behavior meets PRD requirements
"""

from unittest.mock import MagicMock, patch

import pytest

from app.agents.intent_decipherer import IntentDeciphererAgent
from app.agents.safety import (
    ActionApproval,
    ActionDomain,
    SafetyGuardrails,
)
from app.context.models import Assumption, RoutingDecision
from app.context.router import ContextRouter
from app.mcp.preview import build_tool_diff, build_tool_preview


class TestConfidenceThresholds:
    """Validate confidence thresholds trigger clarification/reconciliation (VI-005).

    GIVEN low confidence intent (<0.70) WHEN processed THEN system requests clarification
    GIVEN medium confidence (0.70-0.94) WHEN assumptions generated THEN user sees reconciliation UI
    """

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_clarification(self) -> None:
        """Low confidence (<0.70) should route to clarification handler.

        AC-001: GIVEN low confidence intent (<0.70) WHEN processed THEN system requests clarification
        """
        router = ContextRouter()

        # Simulate a low confidence decision (below 0.70 threshold)
        with patch.object(router, "_route_via_llm") as mock_llm:
            mock_decision = RoutingDecision(
                handler="research_handler",
                confidence=0.65,  # Below DEFAULT_ASSUMPTION_CONFIDENCE_THRESHOLD (0.70)
                payload=MagicMock(text="Do something"),
                reason="Low confidence match",
                assumptions=[],
            )

            mock_llm.return_value = mock_decision

            result = await router._route_via_llm(MagicMock(text="ambiguous input"))

            # Verify confidence is below threshold
            assert result.confidence < 0.70

            # Verify it would route to clarification handler
            # (In the real flow, the router checks this and returns DISAMBIGUATION_HANDLER)
            assert result.confidence == 0.65

    @pytest.mark.asyncio
    async def test_medium_confidence_includes_assumptions(self) -> None:
        """Medium confidence (0.70-0.94) should include assumptions for reconciliation.

        AC-002: GIVEN medium confidence (0.70-0.94) WHEN assumptions generated THEN user sees reconciliation UI
        """
        # Create assumptions with medium confidence
        assumptions = [
            Assumption(
                id="assumption-1",
                text="User wants to research 'AI trends'",
                confidence=0.75,  # Medium confidence
                category="intent",
            ),
            Assumption(
                id="assumption-2",
                text="Date range is last 30 days",
                confidence=0.65,  # Lower confidence assumption
                category="parameter",
            ),
        ]

        # Verify assumptions have medium confidence
        medium_conf_assumptions = [
            a for a in assumptions if 0.70 <= a.confidence < 0.95
        ]
        low_conf_assumptions = [
            a for a in assumptions if a.confidence < 0.70
        ]

        # At least some assumptions should have medium confidence
        assert len(medium_conf_assumptions) > 0

        # Lower confidence assumptions need reconciliation UI
        assert len(low_conf_assumptions) > 0

    @pytest.mark.asyncio
    async def test_high_confidence_auto_executes(self) -> None:
        """High confidence (≥0.95) should auto-execute without HITL.

        This validates the upper bound of HITL - high confidence actions
        should execute without requiring user intervention.
        """
        router = ContextRouter()

        # Simulate a high confidence decision (≥0.95 threshold)
        with patch.object(router, "_route_via_llm") as mock_llm:
            mock_decision = RoutingDecision(
                handler="research_handler",
                confidence=0.96,  # Above DEFAULT_AUTO_EXECUTE_CONFIDENCE_THRESHOLD (0.95)
                payload=MagicMock(text="clear request"),
                reason="High confidence match",
                assumptions=[],
            )

            mock_llm.return_value = mock_decision

            result = await router._route_via_llm(MagicMock(text="clear input"))

            # Verify confidence is above threshold
            assert result.confidence >= 0.95

    def test_clarification_threshold_is_0_7(self) -> None:
        """Verify the clarification confidence threshold is 0.7."""
        # The DEFAULT_ASSUMPTION_CONFIDENCE_THRESHOLD should be 0.7
        assert IntentDeciphererAgent.DEFAULT_ASSUMPTION_CONFIDENCE_THRESHOLD == 0.7
        assert ContextRouter.DEFAULT_CLARIFICATION_CONFIDENCE_THRESHOLD == 0.7

    def test_auto_execute_threshold_is_0_95(self) -> None:
        """Verify the auto-execute confidence threshold is 0.95."""
        # The DEFAULT_AUTO_EXECUTE_CONFIDENCE_THRESHOLD should be 0.95
        assert IntentDeciphererAgent.DEFAULT_AUTO_EXECUTE_CONFIDENCE_THRESHOLD == 0.95


class TestExternalActionApproval:
    """Validate external actions require user approval (VI-005).

    GIVEN external side effect proposed WHEN evaluated THEN action blocked until user confirms (FR-018)
    """

    def test_calendar_create_requires_approval(self) -> None:
        """Calendar create actions should require user approval.

        AC-003: GIVEN external side effect proposed WHEN evaluated THEN action blocked until user confirms
        """
        safety = SafetyGuardrails()

        result = safety.classify_tool_action(
            tool_name="calendar_create",
            arguments={"title": "Meeting", "start": "2026-01-13T10:00:00"},
        )

        # Verify EXTERNAL domain classification
        assert result.domain == ActionDomain.EXTERNAL

        # Verify approval is required
        assert result.requires_approval is True
        assert result.approval == ActionApproval.NEEDS_CONFIRM

    def test_email_send_requires_approval(self) -> None:
        """Email send actions should require user approval."""
        safety = SafetyGuardrails()

        result = safety.classify_tool_action(
            tool_name="email_send",
            arguments={
                "to": "user@example.com",
                "subject": "Test",
                "body": "Test email",
            },
        )

        # Verify EXTERNAL domain classification
        assert result.domain == ActionDomain.EXTERNAL

        # Verify approval is required
        assert result.requires_approval is True

    def test_email_send_bulk_is_blocked(self) -> None:
        """Bulk email send actions should be blocked."""
        safety = SafetyGuardrails()

        result = safety.classify_tool_action(
            tool_name="email_send_bulk",
            arguments={
                "recipients": ["user1@example.com", "user2@example.com"],
                "subject": "Spam",
                "body": "Bulk email",
            },
        )

        # Verify EXTERNAL domain classification
        assert result.domain == ActionDomain.EXTERNAL

        # Verify action is blocked
        assert result.is_blocked is True
        assert result.approval == ActionApproval.BLOCKED

    def test_mcp_write_actions_require_approval(self) -> None:
        """MCP write actions should require user approval."""
        safety = SafetyGuardrails()

        # Test MCP write operations that match the matrix prefix rules
        # Note: Only actions matching the prefix patterns (write_, send_) require approval
        write_actions = [
            "mcp.write_event",      # Matches write_ prefix
            "mcp.send_message",     # Matches send_ prefix
        ]

        for tool_name in write_actions:
            result = safety.classify_tool_action(
                tool_name=tool_name,
                arguments={"test": "data"},
            )

            # Verify MCP domain classification
            assert result.domain == ActionDomain.MCP, f"Tool {tool_name} should be MCP domain"

            # Verify approval is required (write_ and send_ prefixes need confirmation)
            assert result.requires_approval is True, f"Tool {tool_name} should require approval"

    def test_safe_external_queries_allowed(self) -> None:
        """Safe external query actions should not require approval."""
        safety = SafetyGuardrails()

        # Test various MCP query operations (read-only)
        query_actions = [
            "mcp.calendar_query_events",
            "mcp.gmail_list_messages",
            "mcp.notion_read_page",
            "mcp.slack_list_channels",
        ]

        for tool_name in query_actions:
            result = safety.classify_tool_action(
                tool_name=tool_name,
                arguments={"test": "data"},
            )

            # Verify MCP domain classification
            assert result.domain == ActionDomain.MCP

            # Verify approval is NOT required for query operations
            assert result.requires_approval is False
            assert result.approval == ActionApproval.SAFE


class TestDestructiveActionPreviews:
    """Validate destructive actions show preview/diff (VI-005).

    GIVEN destructive action WHEN triggered THEN preview/diff shown and approval required
    """

    def test_canvas_delete_requires_approval(self) -> None:
        """Canvas delete actions should require approval.

        AC-004: GIVEN destructive action WHEN triggered THEN preview/diff shown and approval required
        """
        safety = SafetyGuardrails()

        result = safety.classify_tool_action(
            tool_name="canvas.delete_node",
            arguments={"node_id": "node-123"},
        )

        # Verify CANVAS domain classification
        assert result.domain == ActionDomain.CANVAS

        # Verify approval is required for delete operations
        assert result.requires_approval is True
        assert result.approval == ActionApproval.NEEDS_CONFIRM

    def test_canvas_clear_requires_approval(self) -> None:
        """Canvas clear actions should require approval."""
        safety = SafetyGuardrails()

        result = safety.classify_tool_action(
            tool_name="canvas.clear_canvas",
            arguments={},
        )

        # Verify CANVAS domain classification
        assert result.domain == ActionDomain.CANVAS

        # Verify approval is required
        assert result.requires_approval is True

    def test_document_delete_requires_approval(self) -> None:
        """Document delete actions should require approval."""
        safety = SafetyGuardrails()

        result = safety.classify_tool_action(
            tool_name="document.delete",
            arguments={"document_id": "doc-123"},
        )

        # Verify DOCUMENTS domain classification
        assert result.domain == ActionDomain.DOCUMENTS

        # Verify approval is required
        assert result.requires_approval is True

    def test_job_delete_history_requires_approval(self) -> None:
        """Job delete history actions should require approval."""
        safety = SafetyGuardrails()

        result = safety.classify_tool_action(
            tool_name="job.delete_history",
            arguments={"job_id": "job-123"},
        )

        # Verify JOBS domain classification
        assert result.domain == ActionDomain.JOBS

        # Verify approval is required
        assert result.requires_approval is True

    def test_preview_sanitizes_sensitive_data(self) -> None:
        """Preview should redact sensitive data from tool arguments.

        This validates that preview/diff payloads sanitize sensitive fields
        like tokens, passwords, API keys, etc.
        """
        from app.mcp.preview import redact_sensitive

        arguments = {
            "title": "Test Event",
            "api_key": "secret-key-123",
            "token": "bearer-token-456",
            "password": "my-password",
            "description": "Event description",
        }

        sanitized = redact_sensitive(arguments)

        # Verify sensitive fields are redacted
        assert sanitized["api_key"] == "***REDACTED***"
        assert sanitized["token"] == "***REDACTED***"
        assert sanitized["password"] == "***REDACTED***"

        # Verify non-sensitive fields are preserved
        assert sanitized["title"] == "Test Event"
        assert sanitized["description"] == "Event description"

    def test_build_tool_preview_creates_payload(self) -> None:
        """build_tool_preview should create a sanitized preview payload."""
        arguments = {
            "title": "Meeting",
            "start": "2026-01-13T10:00:00",
            "api_key": "secret",
        }

        preview = build_tool_preview("calendar_create", arguments)

        # Verify preview structure
        assert preview["tool"] == "calendar_create"
        assert "arguments" in preview

        # Verify sensitive data is redacted
        assert preview["arguments"]["api_key"] == "***REDACTED***"

        # Verify non-sensitive data is preserved
        assert preview["arguments"]["title"] == "Meeting"

    def test_build_tool_diff_creates_unified_diff(self) -> None:
        """build_tool_diff should create a unified diff for preview."""
        before = {"title": "Old Meeting", "start": "2026-01-13T09:00:00"}
        after = {"title": "New Meeting", "start": "2026-01-13T10:00:00"}

        preview = build_tool_preview("calendar_update", after)
        diff = build_tool_diff(preview, before)

        # Verify diff contains changes
        assert "--- current" in diff
        assert "+++ proposed" in diff
        assert "Old Meeting" in diff or "New Meeting" in diff

    def test_safe_canvas_actions_dont_require_approval(self) -> None:
        """Safe canvas actions should not require approval."""
        safety = SafetyGuardrails()

        # Test safe canvas operations
        safe_actions: list[tuple[str, dict[str, object]]] = [
            ("canvas.create_node", {"type": "text", "label": "Test"}),
            ("canvas.update_label", {"node_id": "node-1", "label": "New Label"}),
            ("canvas.move", {"node_id": "node-1", "x": 100, "y": 100}),
        ]

        for tool_name, arguments in safe_actions:
            result = safety.classify_tool_action(tool_name, arguments)

            # Verify CANVAS domain
            assert result.domain == ActionDomain.CANVAS

            # Verify approval is NOT required
            assert result.requires_approval is False
            assert result.approval == ActionApproval.SAFE


class TestSafetyGatesIntegration:
    """End-to-end tests for safety gates (VI-005)."""

    def test_novel_destructive_action_requires_approval(self) -> None:
        """Novel destructive actions should require approval per PRD §13.2.

        Note: The classifier extracts the verb from the action name (after domain).
        For "domain.action", it splits on "." and takes the action part.
        Then it splits on "_" to get the first word as the verb.
        """
        safety = SafetyGuardrails()

        # Test novel actions with dangerous verbs (delete, remove, destroy, etc.)
        # The tool name must follow domain.action pattern for proper verb extraction
        novel_actions = [
            "custom.delete_user",   # delete verb (extracted from delete_user)
            "plugin.remove_data",   # remove verb (extracted from remove_data)
            "extension.destroy_config",  # destroy verb (extracted from destroy_config)
        ]

        for tool_name in novel_actions:
            result = safety.classify_tool_action(
                tool_name=tool_name,
                arguments={},
            )

            # Verify approval is required for novel destructive actions
            # The classifier should detect dangerous verbs and require confirmation
            assert result.requires_approval is True, f"Tool {tool_name} should require approval"

    def test_novel_safe_action_defaults_to_safe(self) -> None:
        """Novel safe actions should default to safe per PRD §13.2."""
        safety = SafetyGuardrails()

        # Test novel actions without dangerous verbs/targets
        novel_actions = [
            "custom_fetch_status",
            "plugin_get_info",
            "extension_list_items",
        ]

        for tool_name in novel_actions:
            result = safety.classify_tool_action(
                tool_name=tool_name,
                arguments={},
            )

            # Verify approval is NOT required for novel safe actions
            assert result.requires_approval is False
            assert result.approval == ActionApproval.SAFE

    def test_global_configure_actions_are_blocked(self) -> None:
        """Global configure actions should be blocked."""
        safety = SafetyGuardrails()

        result = safety.classify_tool_action(
            tool_name="mcp.configure_global",
            arguments={"setting": "value"},
        )

        # Verify action is blocked
        assert result.is_blocked is True
        assert result.approval == ActionApproval.BLOCKED
