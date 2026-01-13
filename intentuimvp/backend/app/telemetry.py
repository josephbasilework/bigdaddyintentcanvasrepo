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

Reference: intentuimvp/docs/PERFORMANCE_BUDGET.md
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import logfire

from app.logging_config import get_correlation_id

# Metric namespace for all performance metrics
METRIC_NAMESPACE = "intentui.perf"


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
        f"{METRIC_NAMESPACE}.{metric_name}",
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
        f"{METRIC_NAMESPACE}.{metric_name}",
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
        f"{METRIC_NAMESPACE}.{counter_name}",
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
