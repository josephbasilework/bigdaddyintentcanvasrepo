"""Tests for telemetry events module (JM-8).

Tests structured event emission for the 7 success metrics defined in PRD §5.2:
1. Task Completion Rate (>80%): intent.executed events
2. Assumption Accuracy (>70%): assumption.created/resolved events
3. Time-to-Value (<30s): Simple task execution duration
4. Session Continuity (>60%): workspace reuse tracking
5. Research Job Completion (>75%): job.completed events for deep_research
6. Command vs Chat Ratio (>3:1): interaction_mode classification
7. MCP Adoption (>30%): mcp.configured events

Reference: intentuimvp/docs/telemetry_spec.md
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from app.telemetry_events import (
    AssumptionCreatedEventData,
    AssumptionResolvedEventData,
    EventName,
    MCPConfiguredEventData,
    TelemetryEvent,
    emit_assumption_created,
    emit_assumption_resolved,
    emit_intent_executed,
    emit_intent_submitted,
    emit_job_completed,
    emit_job_enqueued,
    emit_mcp_configured,
    emit_session_started,
    emit_telemetry_event,
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = Mock()
    settings.environment = "test"
    settings.app_name = "test-app"
    settings.app_version = "0.1.0"
    return settings


@pytest.fixture
def mock_logfire():
    """Mock logfire module."""
    with patch("app.telemetry_events.logfire") as m:
        m.info = Mock()
        yield m


@pytest.fixture
def mock_correlation_id():
    """Mock correlation ID."""
    with patch("app.telemetry_events.get_correlation_id", return_value="test-cid-123"):
        yield "test-cid-123"


@pytest.fixture
def mock_logger():
    """Mock logger."""
    with patch("app.telemetry_events.logger") as m:
        m.info = Mock()
        m.warning = Mock()
        yield m


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "user-123"


@pytest.fixture
def sample_session_id():
    """Sample session ID for testing."""
    return "session-abc-456"


@pytest.fixture
def sample_workspace_id():
    """Sample workspace ID for testing."""
    return "workspace-xyz-789"


@pytest.fixture
def sample_run_id():
    """Sample run ID for testing."""
    return "run-def-012"


# ============================================================================
# TelemetryEvent Tests
# ============================================================================

class TestTelemetryEvent:
    """Tests for TelemetryEvent dataclass."""

    def test_event_initialization_with_defaults(self):
        """TelemetryEvent should initialize with required fields."""
        event = TelemetryEvent(
            event_name="test.event",
            event_data={"key": "value"},
        )

        assert event.event_name == "test.event"
        assert event.event_data == {"key": "value"}
        assert event.correlation_id is not None  # Should generate UUID
        assert event.event_id is not None  # Should generate UUID
        assert event.event_timestamp is not None  # Should generate ISO timestamp

    def test_event_initialization_with_all_fields(self):
        """TelemetryEvent should accept all optional fields."""
        event_id = "event-123"
        timestamp = datetime.now(UTC).isoformat()

        event = TelemetryEvent(
            event_name="test.event",
            event_id=event_id,
            event_timestamp=timestamp,
            user_id="user-123",
            session_id="session-456",
            workspace_id="workspace-789",
            run_id="run-012",
            correlation_id="corr-345",
            event_data={"key": "value"},
            source_service="test-service",
            environment="production",
        )

        assert event.event_name == "test.event"
        assert event.event_id == event_id
        assert event.event_timestamp == timestamp
        assert event.user_id == "user-123"
        assert event.session_id == "session-456"
        assert event.workspace_id == "workspace-789"
        assert event.run_id == "run-012"
        assert event.correlation_id == "corr-345"
        assert event.event_data == {"key": "value"}
        assert event.source_service == "test-service"
        assert event.environment == "production"

    def test_to_logfire_attrs_includes_all_fields(self, mock_correlation_id):
        """to_logfire_attrs should include all event fields."""
        event = TelemetryEvent(
            event_name="test.event",
            user_id="user-123",
            session_id="session-456",
            workspace_id="workspace-789",
            run_id="run-012",
            correlation_id=mock_correlation_id,
            event_data={"test_key": "test_value"},
        )

        attrs = event.to_logfire_attrs()

        assert attrs["event_name"] == "test.event"
        assert attrs["user_id"] == "user-123"
        assert attrs["session_id"] == "session-456"
        assert attrs["workspace_id"] == "workspace-789"
        assert attrs["run_id"] == "run-012"
        assert attrs["correlation_id"] == mock_correlation_id
        assert attrs["test_key"] == "test_value"
        assert "event_id" in attrs
        assert "event_timestamp" in attrs
        assert "source_service" in attrs
        assert "environment" in attrs

    def test_to_logfire_attrs_sanitizes_pii(self, mock_correlation_id):
        """to_logfire_attrs should redact PII from event data."""
        event = TelemetryEvent(
            event_name="test.event",
            event_data={
                "email": "user@example.com",
                "safe_field": "safe_value",
                "message": "Send email to john@example.com about the project",
            },
        )

        attrs = event.to_logfire_attrs()

        # Email should be redacted
        assert "[EMAIL_REDACTED]" in attrs["email"]
        # PII in message should be redacted
        assert "[EMAIL_REDACTED]" in attrs["message"]
        # Safe field should be unchanged
        assert attrs["safe_field"] == "safe_value"

    def test_to_logfire_attrs_sanitizes_nested_dicts(self):
        """to_logfire_attrs should redact PII in nested dictionaries."""
        event = TelemetryEvent(
            event_name="test.event",
            event_data={
                "nested": {
                    "email": "user@example.com",
                    "deep": {
                        "phone": "555-123-4567",
                    },
                },
            },
        )

        attrs = event.to_logfire_attrs()

        assert "[EMAIL_REDACTED]" in attrs["nested"]["email"]
        assert "[PHONE_REDACTED]" in attrs["nested"]["deep"]["phone"]


# ============================================================================
# Event Emission Tests
# ============================================================================

class TestEmitTelemetryEvent:
    """Tests for emit_telemetry_event function."""

    def test_emit_event_logs_to_logfire(self, mock_logfire, mock_logger, mock_correlation_id):
        """emit_telemetry_event should log event to Logfire."""
        event = TelemetryEvent(
            event_name="test.event",
            event_data={"test": "value"},
        )

        emit_telemetry_event(event)

        mock_logfire.info.assert_called_once()
        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["event_name"] == "test.event"
        assert "test" in call_kwargs

    def test_emit_event_logs_to_logger(self, mock_logfire, mock_logger, mock_correlation_id):
        """emit_telemetry_event should also log to structured logger."""
        event = TelemetryEvent(
            event_name="test.event",
            user_id="user-123",
            workspace_id="workspace-789",
        )

        emit_telemetry_event(event)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0]
        assert "Telemetry event emitted: test.event" in call_args[0]

    def test_emit_event_handles_logfire_failure_gracefully(self, mock_logfire, mock_logger):
        """emit_telemetry_event should not raise if Logfire fails."""
        mock_logfire.info.side_effect = Exception("Logfire failed")

        event = TelemetryEvent(event_name="test.event")

        # Should not raise
        emit_telemetry_event(event)

        # Should log warning about failure
        mock_logger.warning.assert_called_once()
        assert "Failed to emit telemetry event" in mock_logger.warning.call_args[0][0]


# ============================================================================
# Intent Events Tests
# ============================================================================

class TestEmitIntentSubmitted:
    """Tests for emit_intent_submitted function."""

    def test_emit_intent_submitted_basic(
        self,
        mock_logfire,
        mock_logger,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
    ):
        """emit_intent_submitted should emit event with basic fields."""
        emit_intent_submitted(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            intent_type="research",
            interaction_mode="command",
        )

        mock_logfire.info.assert_called_once()
        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["event_name"] == EventName.INTENT_SUBMITTED
        assert call_kwargs["user_id"] == sample_user_id
        assert call_kwargs["session_id"] == sample_session_id
        assert call_kwargs["workspace_id"] == sample_workspace_id
        assert call_kwargs["intent_type"] == "research"
        assert call_kwargs["interaction_mode"] == "command"

    def test_emit_intent_submitted_with_attachments(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
    ):
        """emit_intent_submitted should include attachment info."""
        emit_intent_submitted(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            intent_type="execute",
            interaction_mode="command",
            has_attachments=True,
        )

        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["has_attachments"] is True

    def test_emit_intent_submitted_redacts_pii_in_input_text(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
    ):
        """emit_intent_submitted should redact PII from input text."""
        emit_intent_submitted(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            intent_type="execute",
            interaction_mode="command",
            input_text="Send email to john@example.com about the project",
        )

        call_kwargs = mock_logfire.info.call_args[1]
        assert "input_text_redacted" in call_kwargs
        assert "[EMAIL_REDACTED]" in call_kwargs["input_text_redacted"]


class TestEmitIntentExecuted:
    """Tests for emit_intent_executed function."""

    def test_emit_intent_executed_success(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
        sample_run_id,
    ):
        """emit_intent_executed should emit success event."""
        emit_intent_executed(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            run_id=sample_run_id,
            status="success",
            intent_type="research",
            execution_duration_ms=1500.0,
        )

        mock_logfire.info.assert_called_once()
        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["event_name"] == EventName.INTENT_EXECUTED
        assert call_kwargs["status"] == "success"
        assert call_kwargs["intent_type"] == "research"
        assert call_kwargs["execution_duration_ms"] == 1500.0
        assert call_kwargs["run_id"] == sample_run_id

    def test_emit_intent_executed_failed(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
        sample_run_id,
    ):
        """emit_intent_executed should include failure reason."""
        emit_intent_executed(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            run_id=sample_run_id,
            status="failed",
            intent_type="plan",
            execution_duration_ms=5000.0,
            failure_reason="Gateway timeout",
        )

        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["status"] == "failed"
        assert call_kwargs["failure_reason"] == "Gateway timeout"

    def test_emit_intent_executed_simple_task(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
        sample_run_id,
    ):
        """emit_intent_executed should mark simple tasks for Time-to-Value metric."""
        emit_intent_executed(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            run_id=sample_run_id,
            status="success",
            intent_type="execute",
            execution_duration_ms=500.0,
            is_simple_task=True,
        )

        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["is_simple_task"] is True


# ============================================================================
# Assumption Events Tests
# ============================================================================

class TestEmitAssumptionCreated:
    """Tests for emit_assumption_created function."""

    def test_emit_assumption_created(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
        sample_run_id,
    ):
        """emit_assumption_created should emit event with assumption details."""
        emit_assumption_created(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            run_id=sample_run_id,
            assumption_id="assumption-123",
            assumption_type="context_gap",
        )

        mock_logfire.info.assert_called_once()
        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["event_name"] == EventName.ASSUMPTION_CREATED
        assert call_kwargs["assumption_id"] == "assumption-123"
        assert call_kwargs["assumption_type"] == "context_gap"
        assert call_kwargs["run_id"] == sample_run_id


class TestEmitAssumptionResolved:
    """Tests for emit_assumption_resolved function."""

    def test_emit_assumption_resolved_accepted(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
    ):
        """emit_assumption_resolved should emit accepted resolution."""
        emit_assumption_resolved(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            assumption_id="assumption-123",
            resolution="accepted_as_is",
        )

        mock_logfire.info.assert_called_once()
        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["event_name"] == EventName.ASSUMPTION_RESOLVED
        assert call_kwargs["assumption_id"] == "assumption-123"
        assert call_kwargs["resolution"] == "accepted_as_is"

    def test_emit_assumption_resolved_modified(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
    ):
        """emit_assumption_resolved should include modification count."""
        emit_assumption_resolved(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            assumption_id="assumption-123",
            resolution="modified",
            modifications_made=2,
        )

        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["resolution"] == "modified"
        assert call_kwargs["modifications_made"] == 2

    def test_emit_assumption_resolved_rejected(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
    ):
        """emit_assumption_resolved should emit rejected resolution."""
        emit_assumption_resolved(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            assumption_id="assumption-123",
            resolution="rejected",
        )

        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["resolution"] == "rejected"


# ============================================================================
# Session Events Tests
# ============================================================================

class TestEmitSessionStarted:
    """Tests for emit_session_started function."""

    def test_emit_session_started_new_workspace(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
    ):
        """emit_session_started should indicate new workspace."""
        emit_session_started(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            workspace_is_new=True,
        )

        mock_logfire.info.assert_called_once()
        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["event_name"] == EventName.SESSION_STARTED
        assert call_kwargs["workspace_is_new"] is True
        assert "workspace_age_days" not in call_kwargs

    def test_emit_session_started_resuming_workspace(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
        sample_workspace_id,
    ):
        """emit_session_started should include workspace age when resuming."""
        emit_session_started(
            user_id=sample_user_id,
            session_id=sample_session_id,
            workspace_id=sample_workspace_id,
            workspace_is_new=False,
            workspace_age_days=5,
            previous_session_id="previous-session-123",
        )

        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["workspace_is_new"] is False
        assert call_kwargs["workspace_age_days"] == 5
        assert call_kwargs["previous_session_id"] == "previous-session-123"


# ============================================================================
# Job Events Tests
# ============================================================================

class TestEmitJobEnqueued:
    """Tests for emit_job_enqueued function."""

    def test_emit_job_enqueued(
        self,
        mock_logfire,
        sample_user_id,
        sample_workspace_id,
    ):
        """emit_job_enqueued should emit event with job details."""
        job_params = {"query": "test query", "max_results": 10}
        emit_job_enqueued(
            user_id=sample_user_id,
            workspace_id=sample_workspace_id,
            job_id="job-123",
            job_type="deep_research",
            job_params=job_params,
        )

        mock_logfire.info.assert_called_once()
        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["event_name"] == EventName.JOB_ENQUEUED
        assert call_kwargs["job_id"] == "job-123"
        assert call_kwargs["job_type"] == "deep_research"
        assert call_kwargs["job_params"] == job_params


class TestEmitJobCompleted:
    """Tests for emit_job_completed function."""

    def test_emit_job_completed_success(
        self,
        mock_logfire,
        sample_user_id,
        sample_workspace_id,
    ):
        """emit_job_completed should emit success event."""
        emit_job_completed(
            user_id=sample_user_id,
            workspace_id=sample_workspace_id,
            job_id="job-123",
            job_type="deep_research",
            status="success",
            execution_duration_ms=30000.0,
        )

        mock_logfire.info.assert_called_once()
        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["event_name"] == EventName.JOB_COMPLETED
        assert call_kwargs["status"] == "success"
        assert call_kwargs["job_type"] == "deep_research"
        assert call_kwargs["execution_duration_ms"] == 30000.0

    def test_emit_job_completed_failed(
        self,
        mock_logfire,
        sample_user_id,
        sample_workspace_id,
    ):
        """emit_job_completed should include failure reason."""
        emit_job_completed(
            user_id=sample_user_id,
            workspace_id=sample_workspace_id,
            job_id="job-123",
            job_type="synthesis",
            status="failed",
            execution_duration_ms=15000.0,
            failure_reason="Insufficient context",
        )

        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["status"] == "failed"
        assert call_kwargs["failure_reason"] == "Insufficient context"


# ============================================================================
# MCP Events Tests
# ============================================================================

class TestEmitMCPConfigured:
    """Tests for emit_mcp_configured function."""

    def test_emit_mcp_configured(
        self,
        mock_logfire,
        sample_user_id,
        sample_session_id,
    ):
        """emit_mcp_configured should emit event with MCP details."""
        emit_mcp_configured(
            user_id=sample_user_id,
            session_id=sample_session_id,
            mcp_id="mcp-123",
            mcp_type="calendar",
            mcp_name="My Calendar",
            is_active=True,
        )

        mock_logfire.info.assert_called_once()
        call_kwargs = mock_logfire.info.call_args[1]
        assert call_kwargs["event_name"] == EventName.MCP_CONFIGURED
        assert call_kwargs["mcp_id"] == "mcp-123"
        assert call_kwargs["mcp_type"] == "calendar"
        assert call_kwargs["mcp_name"] == "My Calendar"
        assert call_kwargs["is_active"] is True


# ============================================================================
# PII Redaction Integration Tests
# ============================================================================

class TestPIIRedactionIntegration:
    """Tests for PII redaction integration in event emission."""

    def test_event_data_redacts_email(self):
        """Event data should redact email addresses."""
        event = TelemetryEvent(
            event_name="test.event",
            event_data={"email": "user@example.com"},
        )
        attrs = event.to_logfire_attrs()
        assert "[EMAIL_REDACTED]" in attrs["email"]

    def test_event_data_redacts_phone(self):
        """Event data should redact phone numbers."""
        event = TelemetryEvent(
            event_name="test.event",
            event_data={"phone": "555-123-4567"},
        )
        attrs = event.to_logfire_attrs()
        assert "[PHONE_REDACTED]" in attrs["phone"]

    def test_event_data_redacts_ssn(self):
        """Event data should redact SSN."""
        event = TelemetryEvent(
            event_name="test.event",
            event_data={"ssn": "123-45-6789"},
        )
        attrs = event.to_logfire_attrs()
        assert "[SSN_REDACTED]" in attrs["ssn"]

    def test_event_data_redacts_credit_card(self):
        """Event data should redact credit card numbers."""
        event = TelemetryEvent(
            event_name="test.event",
            event_data={"card": "4111 1111 1111 1111"},
        )
        attrs = event.to_logfire_attrs()
        assert "[CREDIT_CARD_REDACTED]" in attrs["card"]

    def test_event_data_redacts_api_key(self):
        """Event data should redact API keys."""
        # Use a format that matches the PII detector's pattern (Anthropic API key)
        event = TelemetryEvent(
            event_name="test.event",
            event_data={"api_key": "sk-ant-api03-1234567890abcdef"},
        )
        attrs = event.to_logfire_attrs()
        assert "[API_KEY_REDACTED]" in attrs["api_key"]

    def test_event_data_preserves_safe_content(self):
        """Event data should preserve non-PII content."""
        event = TelemetryEvent(
            event_name="test.event",
            event_data={
                "message": "Hello, world!",
                "count": 42,
                "flag": True,
            },
        )
        attrs = event.to_logfire_attrs()
        assert attrs["message"] == "Hello, world!"
        assert attrs["count"] == 42
        assert attrs["flag"] is True

    def test_list_values_redacted(self):
        """Event data should redact PII in list values."""
        event = TelemetryEvent(
            event_name="test.event",
            event_data={
                "emails": ["user1@example.com", "user2@example.com"],
            },
        )
        attrs = event.to_logfire_attrs()
        assert all("[EMAIL_REDACTED]" in email for email in attrs["emails"])


# ============================================================================
# Event Data Classes Tests
# ============================================================================

class TestEventDataClasses:
    """Tests for event data dataclasses.

    Note: Event data classes are internal to telemetry_events.py and used
    for type documentation. The emit functions accept keyword arguments
    directly rather than these dataclass instances.
    """

    def test_assumption_created_event_data(self):
        """AssumptionCreatedEventData should hold all fields."""
        data = AssumptionCreatedEventData(
            assumption_id="asm-123",
            assumption_type="context_gap",
            run_id="run-456",
        )
        assert data.assumption_id == "asm-123"
        assert data.assumption_type == "context_gap"
        assert data.run_id == "run-456"

    def test_assumption_resolved_event_data(self):
        """AssumptionResolvedEventData should hold all fields."""
        data = AssumptionResolvedEventData(
            assumption_id="asm-123",
            resolution="modified",
            modifications_made=2,
        )
        assert data.assumption_id == "asm-123"
        assert data.resolution == "modified"
        assert data.modifications_made == 2

    def test_mcp_configured_event_data(self):
        """MCPConfiguredEventData should hold all fields."""
        data = MCPConfiguredEventData(
            mcp_id="mcp-789",
            mcp_type="calendar",
            mcp_name="My Calendar",
            is_active=True,
        )
        assert data.mcp_id == "mcp-789"
        assert data.mcp_type == "calendar"
        assert data.mcp_name == "My Calendar"
        assert data.is_active is True
