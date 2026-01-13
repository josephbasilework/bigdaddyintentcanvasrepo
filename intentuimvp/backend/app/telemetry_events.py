"""Telemetry event emission for PRD §5.2 Success Metrics (JM-8).

Implements structured event emission for the 7 success metrics defined in PRD §5.2:
1. Task Completion Rate (>80%): intent.executed events
2. Assumption Accuracy (>70%): assumption.created/resolved events
3. Time-to-Value (<30s): Simple task execution duration
4. Session Continuity (>60%): workspace reuse tracking
5. Research Job Completion (>75%): job.completed events for deep_research
6. Command vs Chat Ratio (>3:1): interaction_mode classification
7. MCP Adoption (>30%): mcp.configured events

All events conform to the canonical envelope schema defined in docs/telemetry_spec.md
and include:
- Correlation IDs for trace reconstruction (NFR-OBS-005)
- PII/secrets redaction (NFR-PRIV-004, NFR-SEC-003)
- OpenTelemetry compatibility (FR-022)
- Structured logging via Logfire

Reference: intentuimvp/docs/telemetry_spec.md
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import logfire

from app.config import get_settings
from app.logging_config import get_correlation_id
from app.pii_detector import PIIDetector, PIIMode, PIISeverity, redact_pii

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================================
# Event Name Constants
# ============================================================================

class EventName(str, Enum):
    """Canonical event names for telemetry emission."""

    # Intent lifecycle events
    INTENT_SUBMITTED = "intent.submitted"
    INTENT_EXECUTED = "intent.executed"

    # Assumption events
    ASSUMPTION_CREATED = "assumption.created"
    ASSUMPTION_RESOLVED = "assumption.resolved"

    # Session events
    SESSION_STARTED = "session.started"

    # Job lifecycle events
    JOB_ENQUEUED = "job.enqueued"
    JOB_COMPLETED = "job.completed"

    # MCP events
    MCP_CONFIGURED = "mcp.configured"

    # Audit events (PII/secrets detection)
    PII_REDACTED = "pii.redacted"
    SECRET_DETECTED = "secret.detected"


# ============================================================================
# Event Data Schemas
# ============================================================================

@dataclass
class IntentSubmittedEventData:
    """Event data for intent.submitted events.

    Metric: Command vs. Chat Ratio (>3:1)
    Reference: PRD §5.2, Metric 6
    """
    intent_type: str  # e.g., "research", "plan", "execute"
    interaction_mode: str  # "command" or "chat"
    input_length_chars: int
    has_attachments: bool


@dataclass
class IntentExecutedEventData:
    """Event data for intent.executed events.

    Metrics: Task Completion Rate (>80%), Time-to-Value (<30s)
    Reference: PRD §5.2, Metrics 1 & 3
    """
    status: str  # "success", "failed", "cancelled"
    failure_reason: str | None = None
    intent_type: str = ""  # e.g., "research", "plan", "execute"
    execution_duration_ms: float = 0.0
    is_simple_task: bool = False  # True for one-shot operations


@dataclass
class AssumptionCreatedEventData:
    """Event data for assumption.created events.

    Metric: Assumption Accuracy (>70%)
    Reference: PRD §5.2, Metric 2
    """
    assumption_id: str
    assumption_type: str  # e.g., "context_gap", "ambiguous_term"
    run_id: str


@dataclass
class AssumptionResolvedEventData:
    """Event data for assumption.resolved events.

    Metric: Assumption Accuracy (>70%)
    Reference: PRD §5.2, Metric 2
    """
    assumption_id: str
    resolution: str  # "accepted_as_is", "modified", "rejected"
    modifications_made: int | None = None


@dataclass
class SessionStartedEventData:
    """Event data for session.started events.

    Metrics: Session Continuity (>60%), MCP Adoption (>30%)
    Reference: PRD §5.2, Metrics 4 & 7
    """
    workspace_id: str
    workspace_is_new: bool
    workspace_age_days: int | None = None
    previous_session_id: str | None = None


@dataclass
class JobEnqueuedEventData:
    """Event data for job.enqueued events.

    Metric: Research Job Completion (>75%)
    Reference: PRD §5.2, Metric 5
    """
    job_id: str
    job_type: str  # "deep_research", "synthesis", "export", "transcription"
    job_params: dict[str, Any]


@dataclass
class JobCompletedEventData:
    """Event data for job.completed events.

    Metric: Research Job Completion (>75%)
    Reference: PRD §5.2, Metric 5
    """
    job_id: str
    job_type: str  # "deep_research", "synthesis", "export", "transcription"
    status: str  # "success", "failed", "cancelled"
    failure_reason: str | None = None
    execution_duration_ms: float = 0.0


@dataclass
class MCPConfiguredEventData:
    """Event data for mcp.configured events.

    Metric: MCP Adoption (>30%)
    Reference: PRD §5.2, Metric 7
    """
    mcp_id: str
    mcp_type: str  # e.g., "calendar", "filesystem", "database"
    mcp_name: str  # User-provided name
    is_active: bool


# ============================================================================
# Canonical Event Envelope
# ============================================================================

@dataclass
class TelemetryEvent:
    """Canonical telemetry event envelope.

    All events emitted for PRD §5.2 success metrics conform to this structure.

    Reference: docs/telemetry_spec.md - Canonical Event Envelope
    """
    # Event identification
    event_name: str
    event_timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Correlation & context
    user_id: str | None = None  # Redacted if PII (hash or UUID)
    session_id: str | None = None  # Ephemeral session identifier
    workspace_id: str | None = None  # Canvas/workspace identifier
    run_id: str | None = None  # Intent execution identifier
    correlation_id: str = field(default_factory=get_correlation_id)

    # Event-specific data
    event_data: dict[str, Any] = field(default_factory=dict)

    # Metadata
    source_service: str = "intent-api"
    environment: str = field(default_factory=lambda: settings.environment)

    def to_logfire_attrs(self) -> dict[str, Any]:
        """Convert to Logfire attributes for emission.

        Returns:
            Dictionary of attributes suitable for logfire.log().
        """
        attrs = {
            "event_name": self.event_name,
            "event_timestamp": self.event_timestamp,
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "source_service": self.source_service,
            "environment": self.environment,
        }

        # Add optional context fields
        if self.user_id:
            attrs["user_id"] = self.user_id
        if self.session_id:
            attrs["session_id"] = self.session_id
        if self.workspace_id:
            attrs["workspace_id"] = self.workspace_id
        if self.run_id:
            attrs["run_id"] = self.run_id

        # Add event data
        attrs.update(self._sanitize_event_data(self.event_data))

        return attrs

    def _sanitize_event_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize event data by redacting PII/secrets.

        Args:
            data: Raw event data dictionary.

        Returns:
            Sanitized event data with PII/secrets redacted.
        """
        sanitized: dict[str, Any] = {}
        pii_detector = PIIDetector(mode=PIIMode.REDACT, min_severity=PIISeverity.LOW)

        for key, value in data.items():
            if isinstance(value, str):
                # Check for PII and redact if found
                result = pii_detector.scan(value)
                if result.has_pii and result.redacted_text:
                    sanitized[key] = result.redacted_text
                    # Log PII redaction event
                    _log_pii_redaction(self.event_name, key, result)
                else:
                    sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_event_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_event_data(item) if isinstance(item, dict)
                    else redact_pii(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized


def _log_pii_redaction(event_name: str, field_name: str, pii_result: Any) -> None:
    """Log PII redaction as an audit event (NFR-PRIV-005).

    Args:
        event_name: Name of the event containing PII.
        field_name: Name of the field that was redacted.
        pii_result: PII detection result.
    """
    try:
        logfire.info(
            "pii_redacted",
            event_name=event_name,
            field_name=field_name,
            pii_types=[d.type.value for d in pii_result.detections],
            redaction_count=len(pii_result.detections),
            correlation_id=get_correlation_id(),
        )
    except Exception as e:
        # Don't fail telemetry if audit logging fails
        logger.warning(f"Failed to log PII redaction: {e}")


# ============================================================================
# Event Emission Functions
# ============================================================================

def emit_telemetry_event(event: TelemetryEvent) -> None:
    """Emit a telemetry event via Logfire.

    Args:
        event: TelemetryEvent to emit.
    """
    try:
        attrs = event.to_logfire_attrs()
        logfire.info(event.event_name, **attrs)

        # Also log to structured logger for local development
        logger.info(
            f"Telemetry event emitted: {event.event_name}",
            extra={
                "event_name": event.event_name,
                "event_id": event.event_id,
                "correlation_id": event.correlation_id,
                "user_id": event.user_id,
                "workspace_id": event.workspace_id,
            },
        )
    except Exception as e:
        # Don't fail application if telemetry emission fails
        logger.warning(f"Failed to emit telemetry event {event.event_name}: {e}")


# ============================================================================
# Intent Events
# ============================================================================

def emit_intent_submitted(
    user_id: str | None,
    session_id: str,
    workspace_id: str,
    *,
    intent_type: str,
    interaction_mode: str,
    input_text: str | None = None,
    has_attachments: bool = False,
) -> None:
    """Emit an intent.submitted event.

    Metric: Command vs. Chat Ratio (>3:1)
    Reference: PRD §5.2, Metric 6

    Args:
        user_id: User identifier (will be redacted if PII).
        session_id: Session identifier.
        workspace_id: Workspace identifier.
        intent_type: Type of intent (e.g., "research", "plan", "execute").
        interaction_mode: "command" or "chat".
        input_text: Optional raw input text (will be redacted if PII).
        has_attachments: Whether the submission includes attachments.
    """
    event_data = {
        "intent_type": intent_type,
        "interaction_mode": interaction_mode,
        "input_length_chars": len(input_text) if input_text else 0,
        "has_attachments": has_attachments,
    }

    # Redact PII from input_text if provided
    if input_text:
        event_data["input_text_redacted"] = redact_pii(input_text)

    event = TelemetryEvent(
        event_name=EventName.INTENT_SUBMITTED,
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace_id,
        event_data=event_data,
    )

    emit_telemetry_event(event)


def emit_intent_executed(
    user_id: str | None,
    session_id: str,
    workspace_id: str,
    run_id: str,
    *,
    status: str,
    intent_type: str,
    execution_duration_ms: float,
    failure_reason: str | None = None,
    is_simple_task: bool = False,
) -> None:
    """Emit an intent.executed event.

    Metrics: Task Completion Rate (>80%), Time-to-Value (<30s)
    Reference: PRD §5.2, Metrics 1 & 3

    Args:
        user_id: User identifier.
        session_id: Session identifier.
        workspace_id: Workspace identifier.
        run_id: Intent execution identifier.
        status: "success", "failed", or "cancelled".
        intent_type: Type of intent executed.
        execution_duration_ms: Execution time in milliseconds.
        failure_reason: Optional failure reason if status is "failed".
        is_simple_task: True for one-shot operations (Time-to-Value metric).
    """
    event_data = {
        "status": status,
        "intent_type": intent_type,
        "execution_duration_ms": execution_duration_ms,
        "is_simple_task": is_simple_task,
    }

    if failure_reason:
        event_data["failure_reason"] = failure_reason

    event = TelemetryEvent(
        event_name=EventName.INTENT_EXECUTED,
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace_id,
        run_id=run_id,
        event_data=event_data,
    )

    emit_telemetry_event(event)


# ============================================================================
# Assumption Events
# ============================================================================

def emit_assumption_created(
    user_id: str | None,
    session_id: str,
    workspace_id: str,
    run_id: str,
    *,
    assumption_id: str,
    assumption_type: str,
) -> None:
    """Emit an assumption.created event.

    Metric: Assumption Accuracy (>70%)
    Reference: PRD §5.2, Metric 2

    Args:
        user_id: User identifier.
        session_id: Session identifier.
        workspace_id: Workspace identifier.
        run_id: Intent execution identifier.
        assumption_id: Unique assumption identifier.
        assumption_type: Type of assumption (e.g., "context_gap", "ambiguous_term").
    """
    event_data = {
        "assumption_id": assumption_id,
        "assumption_type": assumption_type,
        "run_id": run_id,
    }

    event = TelemetryEvent(
        event_name=EventName.ASSUMPTION_CREATED,
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace_id,
        run_id=run_id,
        event_data=event_data,
    )

    emit_telemetry_event(event)


def emit_assumption_resolved(
    user_id: str | None,
    session_id: str,
    workspace_id: str,
    *,
    assumption_id: str,
    resolution: str,
    modifications_made: int | None = None,
) -> None:
    """Emit an assumption.resolved event.

    Metric: Assumption Accuracy (>70%)
    Reference: PRD §5.2, Metric 2

    Args:
        user_id: User identifier.
        session_id: Session identifier.
        workspace_id: Workspace identifier.
        assumption_id: Unique assumption identifier.
        resolution: "accepted_as_is", "modified", or "rejected".
        modifications_made: Number of modifications if resolution is "modified".
    """
    event_data: dict[str, Any] = {
        "assumption_id": assumption_id,
        "resolution": resolution,
    }

    if modifications_made is not None:
        event_data["modifications_made"] = modifications_made

    event = TelemetryEvent(
        event_name=EventName.ASSUMPTION_RESOLVED,
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace_id,
        event_data=event_data,
    )

    emit_telemetry_event(event)


# ============================================================================
# Session Events
# ============================================================================

def emit_session_started(
    user_id: str | None,
    session_id: str,
    workspace_id: str,
    *,
    workspace_is_new: bool,
    workspace_age_days: int | None = None,
    previous_session_id: str | None = None,
) -> None:
    """Emit a session.started event.

    Metrics: Session Continuity (>60%), MCP Adoption (>30%)
    Reference: PRD §5.2, Metrics 4 & 7

    Args:
        user_id: User identifier.
        session_id: New session identifier.
        workspace_id: Workspace identifier.
        workspace_is_new: True if workspace was created this session.
        workspace_age_days: Age of workspace in days (if resuming).
        previous_session_id: Previous session ID (if resuming).
    """
    event_data = {
        "workspace_id": workspace_id,
        "workspace_is_new": workspace_is_new,
    }

    if workspace_age_days is not None:
        event_data["workspace_age_days"] = workspace_age_days
    if previous_session_id:
        event_data["previous_session_id"] = previous_session_id

    event = TelemetryEvent(
        event_name=EventName.SESSION_STARTED,
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace_id,
        event_data=event_data,
    )

    emit_telemetry_event(event)


# ============================================================================
# Job Events
# ============================================================================

def emit_job_enqueued(
    user_id: str | None,
    workspace_id: str,
    *,
    job_id: str,
    job_type: str,
    job_params: dict[str, Any] | None = None,
) -> None:
    """Emit a job.enqueued event.

    Metric: Research Job Completion (>75%)
    Reference: PRD §5.2, Metric 5

    Args:
        user_id: User identifier.
        workspace_id: Workspace identifier.
        job_id: Unique job identifier.
        job_type: Type of job ("deep_research", "synthesis", "export", "transcription").
        job_params: Optional job parameters (will be sanitized).
    """
    event_data = {
        "job_id": job_id,
        "job_type": job_type,
        "job_params": job_params or {},
    }

    event = TelemetryEvent(
        event_name=EventName.JOB_ENQUEUED,
        user_id=user_id,
        workspace_id=workspace_id,
        event_data=event_data,
    )

    emit_telemetry_event(event)


def emit_job_completed(
    user_id: str | None,
    workspace_id: str,
    *,
    job_id: str,
    job_type: str,
    status: str,
    execution_duration_ms: float,
    failure_reason: str | None = None,
) -> None:
    """Emit a job.completed event.

    Metric: Research Job Completion (>75%)
    Reference: PRD §5.2, Metric 5

    Args:
        user_id: User identifier.
        workspace_id: Workspace identifier.
        job_id: Unique job identifier.
        job_type: Type of job ("deep_research", "synthesis", "export", "transcription").
        status: "success", "failed", or "cancelled".
        execution_duration_ms: Job execution time in milliseconds.
        failure_reason: Optional failure reason if status is "failed".
    """
    event_data = {
        "job_id": job_id,
        "job_type": job_type,
        "status": status,
        "execution_duration_ms": execution_duration_ms,
    }

    if failure_reason:
        event_data["failure_reason"] = failure_reason

    event = TelemetryEvent(
        event_name=EventName.JOB_COMPLETED,
        user_id=user_id,
        workspace_id=workspace_id,
        event_data=event_data,
    )

    emit_telemetry_event(event)


# ============================================================================
# MCP Events
# ============================================================================

def emit_mcp_configured(
    user_id: str | None,
    session_id: str,
    *,
    mcp_id: str,
    mcp_type: str,
    mcp_name: str,
    is_active: bool = True,
) -> None:
    """Emit an mcp.configured event.

    Metric: MCP Adoption (>30%)
    Reference: PRD §5.2, Metric 7

    Args:
        user_id: User identifier.
        session_id: Session identifier.
        mcp_id: Unique MCP server identifier.
        mcp_type: Type of MCP server ("calendar", "filesystem", "database", etc.).
        mcp_name: User-provided name for the MCP server.
        is_active: Whether the MCP server is currently active.
    """
    event_data = {
        "mcp_id": mcp_id,
        "mcp_type": mcp_type,
        "mcp_name": mcp_name,
        "is_active": is_active,
    }

    event = TelemetryEvent(
        event_name=EventName.MCP_CONFIGURED,
        user_id=user_id,
        session_id=session_id,
        event_data=event_data,
    )

    emit_telemetry_event(event)
