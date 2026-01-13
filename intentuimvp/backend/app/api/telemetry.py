"""Telemetry and metrics API endpoints.

Provides:
1. Ingestion endpoint for client-side performance metrics (NFR-PERF compliance)
2. Query endpoints for PRD §5.2 success metrics (JM-8)

Metrics endpoints support:
- Rolling windows (24h, 7d)
- Per-user workspace views
- All 7 success metrics from PRD §5.2
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.metrics_service import get_metrics_service

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


class TelemetryEvent(BaseModel):
    """A telemetry event from the frontend.

    Attributes:
        metric_name: Name of the metric (e.g., 'canvas_load', 'canvas_fps')
        value: Numeric value of the metric
        unit: Unit of measurement (e.g., 'ms', 'fps')
        extra_attrs: Additional contextual attributes
    """

    metric_name: str = Field(..., description="Name of the metric being reported")
    value: float = Field(..., description="Numeric value of the metric")
    unit: str | None = Field(None, description="Unit of measurement (e.g., 'ms', 'fps')")
    extra_attrs: dict[str, Any] | None = Field(
        None, description="Additional contextual attributes"
    )


@router.post("/api/v1/telemetry")
async def ingest_telemetry(event: TelemetryEvent) -> dict[str, str]:
    """Accept a telemetry event from the frontend.

    This endpoint receives client-side performance metrics for NFR-PERF compliance.
    Events are logged at INFO level for observability.

    In production, this would typically:
    - Send to a time-series database (e.g., Prometheus, InfluxDB)
    - Batch and forward to an observability platform (e.g., Logfire, Datadog)
    - Aggregate for dashboards and alerting

    Args:
        event: The telemetry event to ingest

    Returns:
        Confirmation message

    Raises:
        HTTPException: If the event is invalid
    """
    try:
        # Log the telemetry event
        log_data = {
            "metric": event.metric_name,
            "value": event.value,
            "unit": event.unit,
            **(event.extra_attrs or {}),
        }
        logger.info("Telemetry received", extra=log_data)

        # In production: send to metrics backend, time-series DB, etc.
        # For MVP: logging is sufficient for compliance verification

        return {"status": "recorded", "metric": event.metric_name}
    except Exception as e:
        logger.error(f"Failed to process telemetry: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record telemetry",
        ) from e


# =============================================================================
# PRD §5.2 Success Metrics Query Endpoints (JM-8)
# =============================================================================


class MetricsResponse(BaseModel):
    """Response model for success metrics query.

    Attributes:
        metrics: Dictionary of all 7 success metrics
        window: Rolling window used ("24h" or "7d")
        generated_at: ISO timestamp of when metrics were computed
    """

    metrics: dict[str, Any] = Field(
        ..., description="All 7 success metrics keyed by metric name"
    )
    window: str = Field(..., description="Rolling window (e.g., '24h', '7d')")
    generated_at: str = Field(..., description="ISO timestamp of computation")


@router.get("/api/v1/metrics/success", response_model=MetricsResponse)
async def get_success_metrics(
    window: str = Query(
        "24h",
        description="Rolling window: '24h' or '7d'",
        pattern="^(24h|7d)$",
    ),
    user_id: str | None = Query(
        None, description="Optional user ID for per-user workspace views"
    ),
    workspace_id: str | None = Query(
        None, description="Optional workspace ID for filtering"
    ),
) -> MetricsResponse:
    """Get all 7 PRD §5.2 success metrics for the given rolling window.

    Returns computed values for all success metrics:
    1. Task Completion Rate (>80%): % of user intents successfully executed
    2. Assumption Accuracy (>70%): % of assumptions accepted without modification
    3. Time-to-Value (<30s): Average time from command to useful output
    4. Session Continuity (>60%): % of users resuming previous workspace
    5. Research Job Completion (>75%): % of deep research jobs completed
    6. Command vs. Chat Ratio (>3:1): Ratio of command to chat interactions
    7. MCP Adoption (>30%): % of users with at least one MCP configured

    Each metric includes:
    - value: Computed value
    - target: Target value from PRD
    - meets_target: Whether the target is met
    - sample_size: Number of data points included
    - Additional metadata specific to each metric

    Args:
        window: Rolling window ("24h" or "7d")
        user_id: Optional user filter for per-user views
        workspace_id: Optional workspace filter

    Returns:
        MetricsResponse with all 7 metrics

    Raises:
        HTTPException: If the query fails
    """
    try:
        from datetime import UTC, datetime

        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            metrics_service = get_metrics_service()

            metrics = await metrics_service.get_all_metrics(
                db, window=window, user_id=user_id, workspace_id=workspace_id
            )

            return MetricsResponse(
                metrics=metrics,
                window=window,
                generated_at=datetime.now(UTC).isoformat(),
            )
    except Exception as e:
        logger.error(f"Failed to fetch success metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch metrics",
        ) from e


@router.get("/api/v1/metrics/success/{metric_name}")
async def get_single_metric(
    metric_name: str,
    window: str = Query(
        "24h",
        description="Rolling window: '24h' or '7d'",
        pattern="^(24h|7d)$",
    ),
    user_id: str | None = Query(None, description="Optional user ID filter"),
    workspace_id: str | None = Query(None, description="Optional workspace ID filter"),
) -> dict[str, Any]:
    """Get a single success metric by name.

    Valid metric names:
    - task_completion_rate
    - assumption_accuracy
    - time_to_value
    - session_continuity
    - research_job_completion
    - command_vs_chat_ratio
    - mcp_adoption

    Args:
        metric_name: Name of the metric to fetch
        window: Rolling window ("24h" or "7d")
        user_id: Optional user filter
        workspace_id: Optional workspace filter

    Returns:
        Single metric result

    Raises:
        HTTPException: If metric name is invalid or query fails
    """
    valid_metrics = {
        "task_completion_rate",
        "assumption_accuracy",
        "time_to_value",
        "session_continuity",
        "research_job_completion",
        "command_vs_chat_ratio",
        "mcp_adoption",
    }

    if metric_name not in valid_metrics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric name: {metric_name}. Valid names: {', '.join(sorted(valid_metrics))}",
        )

    try:
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            metrics_service = get_metrics_service()

            all_metrics = await metrics_service.get_all_metrics(
                db, window=window, user_id=user_id, workspace_id=workspace_id
            )

            if metric_name not in all_metrics:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Metric {metric_name} not found",
                )

            return all_metrics[metric_name]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch metric {metric_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch metric: {metric_name}",
        ) from e
