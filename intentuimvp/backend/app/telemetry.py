"""Performance telemetry and metrics instrumentation.

Implements NFR-PERF targets with correlation ID tracking for all metrics.
Metrics are emitted via Logfire with p50/p95 aggregations available.

Performance Targets (NFR-PERF):
- NFR-PERF-001: Canvas initial load < 2 seconds
- NFR-PERF-002: State update propagation < 100ms
- NFR-PERF-003: Intent deciphering < 5 seconds
- NFR-PERF-004: Simple command execution < 30 seconds
- NFR-PERF-005: WebSocket reconnection < 5 seconds
- NFR-PERF-006: Canvas with 100 nodes smooth pan/zoom (60fps)

Success Metrics (JM-8, PRD §5.2):
- Task Completion Rate (>80%)
- Assumption Accuracy (>70%)
- Time-to-Value (<30s for simple tasks)
- Session Continuity (>60%)
- Research Job Completion (>75%)
- Command vs Chat Ratio (>3:1)
- MCP Adoption (>30%)

Reference:
- intentuimvp/docs/PERFORMANCE_BUDGET.md
- docs/telemetry_spec.md
"""

import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import logfire

from app.logging_config import get_correlation_id
from app.pii_detector import redact_pii

# Metric namespace for all performance metrics
PERF_NAMESPACE = "intentui.perf"
# Metric namespace for success metrics events
EVENT_NAMESPACE = "intentui.events"


def _redact_pii_in_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact PII from dictionary values.

    Serializes to JSON, redacts PII from string representation,
    then parses back to dict. This ensures all nested string values
    are scanned for PII patterns.

    Args:
        data: Dictionary possibly containing PII

    Returns:
        Dictionary with PII redacted from string values
    """
    # Serialize to JSON to get string representation
    json_str = json.dumps(data)

    # Redact PII from the JSON string
    redacted_json = redact_pii(json_str)

    # Parse back to dict
    try:
        return json.loads(redacted_json)
    except json.JSONDecodeError:
        # If redaction broke JSON, return original data
        return data


def initialize_logfire(settings: Any) -> None:
    """Initialize Logfire for performance metrics.

    Args:
        settings: Application settings containing Logfire configuration.
    """
    try:
        logfire.configure(
            send_to_logfire=settings.environment == "production",
            service_name=settings.app_name,
            service_version=settings.app_version,
        )
        logfire.info("Logfire initialized", environment=settings.environment)
    except Exception as e:
        # Don''t fail startup if Logfire initialization fails
        logfire.warning(f"Logfire initialization failed: {e}")


@contextmanager
def track_latency(
    metric_name: str,
    *,
    extra_attrs: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Context manager for tracking operation latency.

    Emits a logfire span with timing and automatically calculates duration.
    Correlation ID is attached for trace reconstruction.

    Args:
        metric_name: Name of the metric (e.g., "canvas_load", "intent_decipher").
        extra_attrs: Additional attributes to attach to the span.

    Yields:
        None

    Example:
        with track_latency("intent_decipher", extra_attrs={"model": "claude-opus"}):
            result = await gateway_client.call()
    """
    attrs = extra_attrs or {}
    attrs["correlation_id"] = get_correlation_id()

    with logfire.span(
        f"{PERF_NAMESPACE}.{metric_name}",
        **attrs,
    ) as span:
        start = time.monotonic()
        try:
            yield
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            # Set duration as an attribute for p50/p95 calculation
            span.set_attribute("duration_ms", duration_ms)


def record_metric(
    metric_name: str,
    value: float,
    unit: str = "ms",
    *,
    extra_attrs: dict[str, Any] | None = None,
) -> None:
    """Record a single metric value.

    Use for one-off metric recording where a context manager isn''t suitable.

    Args:
        metric_name: Name of the metric.
        value: Metric value (typically duration in milliseconds).
        unit: Unit of measurement (default: "ms").
        extra_attrs: Additional attributes to attach.

    Example:
        record_metric("ws_reconnect_time", 1200, extra_attrs={"success": True})
    """
    attrs = extra_attrs or {}
    attrs["correlation_id"] = get_correlation_id()
    attrs["unit"] = unit

    logfire.metric(
        f"{PERF_NAMESPACE}.{metric_name}",
        value,
        **attrs,
    )


def increment_counter(
    counter_name: str,
    *,
    amount: int = 1,
    extra_attrs: dict[str, Any] | None = None,
) -> None:
    """Increment a counter metric.

    Use for counting events (e.g., messages sent, errors occurred).

    Args:
        counter_name: Name of the counter.
        amount: Amount to increment by (default: 1).
        extra_attrs: Additional attributes to attach.

    Example:
        increment_counter("ws_messages_sent", extra_attrs={"direction": "outbound"})
    """
    attrs = extra_attrs or {}
    attrs["correlation_id"] = get_correlation_id()

    logfire.increment(
        f"{PERF_NAMESPACE}.{counter_name}",
        amount,
        **attrs,
    )


# NFR-PERF-001: Canvas initial load time
def track_canvas_load(user_id: str, node_count: int, edge_count: int):
    """Track canvas initial load performance.

    Measures time from canvas request to full render.
    Target: < 2000ms per NFR-PERF-001.

    Args:
        user_id: User ID loading the canvas.
        node_count: Number of nodes in the canvas.
        edge_count: Number of edges in the canvas.
    """
    return track_latency(
        "canvas_load",
        extra_attrs={
            "user_id": user_id,
            "node_count": node_count,
            "edge_count": edge_count,
        },
    )


# NFR-PERF-002: State update propagation
def track_state_update(
    update_type: str,
    entity_type: str,  # "node", "edge", "document", etc.
):
    """Track state update propagation time.

    Measures time from WebSocket message receipt to UI state commit.
    Target: < 100ms per NFR-PERF-002.

    Args:
        update_type: Type of update ("create", "update", "delete").
        entity_type: Type of entity being updated.
    """
    return track_latency(
        "state_update",
        extra_attrs={
            "update_type": update_type,
            "entity_type": entity_type,
        },
    )


# NFR-PERF-003: Intent deciphering latency
def track_intent_decipher(
    agent_name: str,
    model: str,
    command_length: int,
):
    """Track intent deciphering performance.

    Measures Gateway call duration for intent analysis.
    Target: < 5000ms per NFR-PERF-003.

    Args:
        agent_name: Name of the agent (e.g., "PlannerAgent").
        model: Model being used (e.g., "claude-opus-4-5-20251101").
        command_length: Length of user command in characters.
    """
    return track_latency(
        "intent_decipher",
        extra_attrs={
            "agent": agent_name,
            "model": model,
            "command_length": command_length,
        },
    )


# NFR-PERF-004: Command execution time
def track_command_execution(
    job_type: str,
    tool_count: int,
):
    """Track command execution performance.

    Measures end-to-end job duration from enqueue to completion.
    Target: < 30000ms per NFR-PERF-004.

    Args:
        job_type: Type of job being executed.
        tool_count: Number of tools/calls required.
    """
    return track_latency(
        "command_execution",
        extra_attrs={
            "job_type": job_type,
            "tool_count": tool_count,
        },
    )


# NFR-PERF-005: WebSocket reconnection time
def record_ws_reconnect(duration_ms: float, success: bool) -> None:
    """Record WebSocket reconnection performance.

    Measures time from connection drop to successful reconnect.
    Target: < 5000ms per NFR-PERF-005.

    Args:
        duration_ms: Time taken to reconnect in milliseconds.
        success: Whether reconnection was successful.
    """
    record_metric(
        "ws_reconnect_time",
        duration_ms,
        extra_attrs={"success": success},
    )


# NFR-PERF-006: Canvas render performance with many nodes
def track_canvas_render_fps(node_count: int, fps: float) -> None:
    """Record canvas rendering frame rate.

    Measures smoothness of pan/zoom operations under load.
    Target: 60fps with 100 nodes per NFR-PERF-006.

    Note: This is typically measured on the frontend. Backend receives
    aggregated metrics via telemetry API.

    Args:
        node_count: Number of nodes in canvas.
        fps: Measured frame rate.
    """
    record_metric(
        "canvas_render_fps",
        fps,
        unit="fps",
        extra_attrs={"node_count": node_count},
    )


# Job system metrics (NFR-OBS-003)
def track_job_lifecycle(
    job_id: str,
    job_type: str,
    lifecycle_event: str,  # "enqueued", "started", "completed", "failed", "cancelled"
):
    """Track job lifecycle events with timing.

    Emits metrics for job queue performance monitoring.

    Args:
        job_id: Unique job identifier.
        job_type: Type of job.
        lifecycle_event: Lifecycle stage being tracked.
    """
    return track_latency(
        "job_lifecycle",
        extra_attrs={
            "job_id": job_id,
            "job_type": job_type,
            "event": lifecycle_event,
        },
    )


# Gateway call metrics (NFR-OBS-002)
def track_gateway_call(
    model: str,
    operation: str,
):
    """Track Gateway API call performance.

    Measures latency and success/failure for LLM inference calls.

    Args:
        model: Model being called.
        operation: Type of operation (e.g., "chat", "stream").
    """
    return track_latency(
        "gateway_call",
        extra_attrs={
            "model": model,
            "operation": operation,
        },
    )


# =============================================================================
# Success Metrics Event Emission (JM-8, PRD §5.2)
# Reference: docs/telemetry_spec.md
# =============================================================================


def _emit_telemetry_event(
    event_name: str,
    event_data: dict[str, Any],
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    workspace_id: str | None = None,
    run_id: str | None = None,
    correlation_id: str | None = None,
    source_service: str = "intent-api",
) -> str:
    """Emit a telemetry event with canonical envelope.

    Args:
        event_name: Event name (e.g., "intent.executed", "assumption.created")
        event_data: Event-specific data (will be PII-redacted)
        user_id: User identifier (optional, redacted if present)
        session_id: Session identifier (optional)
        workspace_id: Workspace identifier (optional)
        run_id: Intent execution identifier (optional)
        correlation_id: Links related events (optional)
        source_service: Service emitting the event (default: "intent-api")

    Returns:
        The generated event_id for this telemetry event
    """
    event_id = str(uuid.uuid4())
    event_timestamp = datetime.now(UTC).isoformat()

    # Use provided correlation_id or get from context
    if correlation_id is None:
        correlation_id = get_correlation_id()

    # Redact PII from event_data
    redacted_data = _redact_pii_in_dict(event_data)

    # Build canonical event envelope
    envelope: dict[str, Any] = {
        "event_name": event_name,
        "event_timestamp": event_timestamp,
        "event_id": event_id,
        "correlation_id": correlation_id,
        "event_data": redacted_data,
        "source_service": source_service,
    }

    # Add optional context fields
    if user_id is not None:
        envelope["user_id"] = user_id
    if session_id is not None:
        envelope["session_id"] = session_id
    if workspace_id is not None:
        envelope["workspace_id"] = workspace_id
    if run_id is not None:
        envelope["run_id"] = run_id

    # Emit via logfire
    logfire.info(
        f"{EVENT_NAMESPACE}.{event_name}",
        **envelope,
    )

    return event_id


# Metric 1: Task Completion Rate (>80%)
# Events: intent.executed


def emit_intent_executed(
    *,
    status: str,  # "success" | "failed" | "cancelled"
    intent_type: str,  # e.g., "research", "plan", "execute"
    execution_duration_ms: int,
    failure_reason: str | None = None,
    is_simple_task: bool = False,
    user_id: str | None = None,
    session_id: str | None = None,
    workspace_id: str | None = None,
    run_id: str | None = None,
    correlation_id: str | None = None,
) -> str:
    """Emit intent.executed event for Task Completion Rate and Time-to-Value metrics.

    Reference: docs/telemetry_spec.md §1, §3

    Args:
        status: Execution status
        intent_type: Type of intent executed
        execution_duration_ms: Time from submission to completion (ms)
        failure_reason: Present if status = "failed"
        is_simple_task: True for one-shot operations (Time-to-Value)
        user_id: User identifier
        session_id: Session identifier
        workspace_id: Workspace identifier
        run_id: Intent execution identifier
        correlation_id: Links related events

    Returns:
        The generated event_id
    """
    event_data: dict[str, Any] = {
        "status": status,
        "intent_type": intent_type,
        "execution_duration_ms": execution_duration_ms,
        "is_simple_task": is_simple_task,
    }

    if failure_reason:
        event_data["failure_reason"] = failure_reason

    return _emit_telemetry_event(
        "intent.executed",
        event_data,
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace_id,
        run_id=run_id,
        correlation_id=correlation_id,
    )


# Metric 2: Assumption Accuracy (>70%)
# Events: assumption.created, assumption.resolved


def emit_assumption_created(
    *,
    assumption_id: str,
    assumption_type: str,  # e.g., "context_gap", "ambiguous_term"
    run_id: str,
    user_id: str | None = None,
    session_id: str | None = None,
    workspace_id: str | None = None,
    correlation_id: str | None = None,
) -> str:
    """Emit assumption.created event for Assumption Accuracy metric.

    Reference: docs/telemetry_spec.md §2

    Args:
        assumption_id: Unique assumption identifier
        assumption_type: Type of assumption
        run_id: Intent execution identifier
        user_id: User identifier
        session_id: Session identifier
        workspace_id: Workspace identifier
        correlation_id: Links related events

    Returns:
        The generated event_id
    """
    return _emit_telemetry_event(
        "assumption.created",
        {
            "assumption_id": assumption_id,
            "assumption_type": assumption_type,
            "run_id": run_id,
        },
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace_id,
        run_id=run_id,
        correlation_id=correlation_id,
    )


def emit_assumption_resolved(
    *,
    assumption_id: str,
    resolution: str,  # "accepted_as_is" | "modified" | "rejected"
    modifications_made: int | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    workspace_id: str | None = None,
    correlation_id: str | None = None,
) -> str:
    """Emit assumption.resolved event for Assumption Accuracy metric.

    Reference: docs/telemetry_spec.md §2

    Args:
        assumption_id: Unique assumption identifier
        resolution: How the user resolved the assumption
        modifications_made: Number of modifications if resolution = "modified"
        user_id: User identifier
        session_id: Session identifier
        workspace_id: Workspace identifier
        correlation_id: Links related events

    Returns:
        The generated event_id
    """
    event_data: dict[str, Any] = {
        "assumption_id": assumption_id,
        "resolution": resolution,
    }

    if modifications_made is not None:
        event_data["modifications_made"] = modifications_made

    return _emit_telemetry_event(
        "assumption.resolved",
        event_data,
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace_id,
        correlation_id=correlation_id,
    )


# Metric 4: Session Continuity (>60%)
# Events: session.started


def emit_session_started(
    *,
    workspace_id: str,
    workspace_is_new: bool,
    workspace_age_days: int | None = None,
    previous_session_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> str:
    """Emit session.started event for Session Continuity metric.

    Reference: docs/telemetry_spec.md §4

    Args:
        workspace_id: Canvas/workspace identifier
        workspace_is_new: True if workspace created this session
        workspace_age_days: Age of workspace if resuming
        previous_session_id: Previous session if resuming
        user_id: User identifier
        session_id: Current session identifier

    Returns:
        The generated event_id
    """
    event_data: dict[str, Any] = {
        "workspace_id": workspace_id,
        "workspace_is_new": workspace_is_new,
    }

    if workspace_age_days is not None:
        event_data["workspace_age_days"] = workspace_age_days
    if previous_session_id:
        event_data["previous_session_id"] = previous_session_id

    return _emit_telemetry_event(
        "session.started",
        event_data,
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace_id,
        source_service="intent-api",
    )


# Metric 5: Research Job Completion Rate (>75%)
# Events: job.enqueued, job.completed


def emit_job_enqueued(
    *,
    job_id: str,
    job_type: str,  # "deep_research" | "synthesis" | "export" | "transcription"
    job_params: dict[str, Any],
    user_id: str | None = None,
    session_id: str | None = None,
    correlation_id: str | None = None,
) -> str:
    """Emit job.enqueued event for Research Job Completion metric.

    Reference: docs/telemetry_spec.md §5

    Args:
        job_id: Unique job identifier
        job_type: Type of job
        job_params: Job parameters (will be redacted if sensitive)
        user_id: User identifier
        session_id: Session identifier
        correlation_id: Links related events

    Returns:
        The generated event_id
    """
    return _emit_telemetry_event(
        "job.enqueued",
        {
            "job_id": job_id,
            "job_type": job_type,
            "job_params": job_params,
        },
        user_id=user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        source_service="job-worker",
    )


def emit_job_completed(
    *,
    job_id: str,
    job_type: str,  # "deep_research" | "synthesis" | "export" | "transcription"
    status: str,  # "success" | "failed" | "cancelled"
    execution_duration_ms: int,
    failure_reason: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    correlation_id: str | None = None,
) -> str:
    """Emit job.completed event for Research Job Completion metric.

    Reference: docs/telemetry_spec.md §5

    Args:
        job_id: Unique job identifier
        job_type: Type of job
        status: Terminal status
        execution_duration_ms: Time from enqueue to completion (ms)
        failure_reason: Present if status = "failed"
        user_id: User identifier
        session_id: Session identifier
        correlation_id: Links related events (should match job.enqueued)

    Returns:
        The generated event_id
    """
    event_data: dict[str, Any] = {
        "job_id": job_id,
        "job_type": job_type,
        "status": status,
        "execution_duration_ms": execution_duration_ms,
    }

    if failure_reason:
        event_data["failure_reason"] = failure_reason

    return _emit_telemetry_event(
        "job.completed",
        event_data,
        user_id=user_id,
        session_id=session_id,
        correlation_id=correlation_id,
        source_service="job-worker",
    )


# Metric 6: Command vs Chat Ratio (>3:1)
# Events: intent.submitted


def emit_intent_submitted(
    *,
    intent_type: str,
    interaction_mode: str,  # "command" | "chat"
    input_length_chars: int,
    has_attachments: bool = False,
    user_id: str | None = None,
    session_id: str | None = None,
    workspace_id: str | None = None,
) -> str:
    """Emit intent.submitted event for Command vs Chat Ratio metric.

    Reference: docs/telemetry_spec.md §6

    Args:
        intent_type: Type of intent (e.g., "research", "plan", "execute")
        interaction_mode: "command" or "chat"
        input_length_chars: Length of user input in characters
        has_attachments: Whether input has attachments
        user_id: User identifier
        session_id: Session identifier
        workspace_id: Workspace identifier

    Returns:
        The generated event_id
    """
    return _emit_telemetry_event(
        "intent.submitted",
        {
            "intent_type": intent_type,
            "interaction_mode": interaction_mode,
            "input_length_chars": input_length_chars,
            "has_attachments": has_attachments,
        },
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace_id,
        source_service="intent-api",
    )


# Metric 7: MCP Adoption Rate (>30%)
# Events: mcp.configured


def emit_mcp_configured(
    *,
    mcp_id: str,
    mcp_type: str,  # e.g., "calendar", "filesystem", "database"
    mcp_name: str,  # User-provided name
    is_active: bool = True,
    user_id: str | None = None,
    session_id: str | None = None,
) -> str:
    """Emit mcp.configured event for MCP Adoption metric.

    Reference: docs/telemetry_spec.md §7

    Args:
        mcp_id: Unique MCP server identifier
        mcp_type: Type of MCP server
        mcp_name: User-provided name for the server
        is_active: Whether the server is active
        user_id: User identifier
        session_id: Session identifier

    Returns:
        The generated event_id
    """
    return _emit_telemetry_event(
        "mcp.configured",
        {
            "mcp_id": mcp_id,
            "mcp_type": mcp_type,
            "mcp_name": mcp_name,
            "is_active": is_active,
        },
        user_id=user_id,
        session_id=session_id,
        source_service="mcp-manager",
    )
