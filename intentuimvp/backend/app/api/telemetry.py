"""Telemetry endpoint for client-side performance metrics.

Accepts performance measurements from the frontend for NFR-PERF compliance tracking.
Metrics are logged and can be extended to persistent storage for production monitoring.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings

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
