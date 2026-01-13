"""Backend metrics collection and percentile calculation.

Implements NFR-PERF metrics collection with correlation IDs for querying p50/p95/p99.

This module provides in-memory metrics storage for development and testing.
In production, metrics are primarily exported to Logfire for analysis.
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MetricRecord:
    """A single metric record with correlation ID."""

    metric_type: str
    correlation_id: str
    value_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metric_type": self.metric_type,
            "correlation_id": self.correlation_id,
            "value_ms": self.value_ms,
            "timestamp": self.timestamp,
            **self.metadata,
        }


class MetricsStore:
    """Thread-safe in-memory metrics store.

    Stores metrics for local analysis and percentile calculation.
    In production, metrics are also sent to Logfire.
    """

    _instance: "MetricsStore | None" = None
    _lock: threading.Lock = threading.Lock()

    # Instance attributes (declared for mypy, initialized in __new__)
    _metrics: defaultdict[str, list[MetricRecord]]
    _max_metrics_per_type: int

    def __new__(cls) -> "MetricsStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    # Initialize instance attributes
                    cls._instance._metrics = defaultdict(list)  # type: ignore[assignment]
                    cls._instance._max_metrics_per_type = 1000  # type: ignore[assignment]
        return cls._instance

    def record(
        self,
        metric_type: str,
        correlation_id: str,
        value_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a metric.

        Args:
            metric_type: Type of metric (e.g., "intent_decipher", "job_execution")
            correlation_id: Correlation ID for trace reconstruction
            value_ms: Metric value in milliseconds
            metadata: Optional additional context
        """
        record = MetricRecord(
            metric_type=metric_type,
            correlation_id=correlation_id,
            value_ms=value_ms,
            metadata=metadata or {},
        )

        with self._lock:
            metrics = self._metrics[metric_type]
            metrics.append(record)

            # Keep only the most recent metrics
            if len(metrics) > self._max_metrics_per_type:
                self._metrics[metric_type] = metrics[-self._max_metrics_per_type :]

        # Log in development
        logger.info(
            f"Metric recorded: {metric_type}",
            extra={
                "metric_type": metric_type,
                "correlation_id": correlation_id,
                "value_ms": value_ms,
                **(metadata or {}),
            },
        )

    def get_metrics(self, metric_type: str) -> list[MetricRecord]:
        """Get all metrics for a specific type.

        Args:
            metric_type: Type of metric to retrieve

        Returns:
            List of metric records
        """
        with self._lock:
            return self._metrics.get(metric_type, []).copy()

    def get_percentiles(
        self, metric_type: str, percentiles: list[int] | None = None
    ) -> dict[str, float] | None:
        """Calculate percentile values for a metric type.

        Args:
            metric_type: Type of metric to analyze
            percentiles: List of percentiles to calculate (e.g., [50, 95, 99])

        Returns:
            Dictionary with percentile values, or None if no metrics available
        """
        if percentiles is None:
            percentiles = [50, 95, 99]

        metrics = self.get_metrics(metric_type)
        if not metrics:
            return None

        values = sorted(m.value_ms for m in metrics)
        result = {}

        for p in percentiles:
            index = min(int((p / 100) * len(values)), len(values) - 1)
            result[f"p{p}"] = values[index]

        return result

    def get_summary(
        self, metric_type: str
    ) -> dict[str, Any] | None:
        """Get summary statistics for a metric type.

        Args:
            metric_type: Type of metric to analyze

        Returns:
            Summary statistics including count, min, max, mean, p50, p95, p99
        """
        metrics = self.get_metrics(metric_type)
        if not metrics:
            return None

        values = sorted(m.value_ms for m in metrics)
        count = len(values)
        min_val = values[0]
        max_val = values[-1]
        mean_val = sum(values) / count

        p50 = values[int(0.50 * count)]
        p95 = values[min(int(0.95 * count), count - 1)]
        p99 = values[min(int(0.99 * count), count - 1)]

        return {
            "metric_type": metric_type,
            "count": count,
            "min_ms": min_val,
            "max_ms": max_val,
            "mean_ms": mean_val,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
        }

    def clear(self, metric_type: str | None = None) -> None:
        """Clear metrics.

        Args:
            metric_type: Specific type to clear, or None to clear all
        """
        with self._lock:
            if metric_type:
                self._metrics.pop(metric_type, None)
            else:
                self._metrics.clear()

    def export(self) -> dict[str, list[dict[str, Any]]]:
        """Export all metrics as a dictionary.

        Returns:
            Dictionary mapping metric types to lists of metric records
        """
        with self._lock:
            return {
                metric_type: [m.to_dict() for m in records]
                for metric_type, records in self._metrics.items()
            }


# Singleton instance
_metrics_store = MetricsStore()


def get_metrics_store() -> MetricsStore:
    """Get the singleton metrics store instance.

    Returns:
        MetricsStore instance
    """
    return _metrics_store


def record_metric(
    metric_type: str,
    correlation_id: str,
    value_ms: float,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a metric (convenience function).

    Args:
        metric_type: Type of metric (e.g., "intent_decipher", "job_execution")
        correlation_id: Correlation ID for trace reconstruction
        value_ms: Metric value in milliseconds
        metadata: Optional additional context
    """
    _metrics_store.record(metric_type, correlation_id, value_ms, metadata)


class MetricTimer:
    """Context manager for timing operations.

    Usage:
        ```python
        with MetricTimer("operation_name", correlation_id) as timer:
            # Do work
            timer.metadata["additional"] = "context"
        # Metric is automatically recorded on exit
        ```
    """

    def __init__(
        self, metric_type: str, correlation_id: str, metadata: dict[str, Any] | None = None
    ) -> None:
        self.metric_type = metric_type
        self.correlation_id = correlation_id
        self.metadata = metadata or {}
        self.start_time: float | None = None

    def __enter__(self) -> "MetricTimer":
        self.start_time = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is not None:
            duration_ms = (time.monotonic() - self.start_time) * 1000
            metadata = dict(self.metadata)
            if exc_type is not None:
                metadata["error"] = exc_type.__name__
            record_metric(self.metric_type, self.correlation_id, duration_ms, metadata)
