"""Tests for metrics collection and percentile calculation.

Tests NFR-PERF metrics instrumentation with correlation IDs and percentile queries.
"""

import time

import pytest

from app.jobs.metrics_collection import (
    MetricsStore,
    MetricTimer,
    get_metrics_store,
    record_metric,
)


@pytest.fixture
def metrics_store() -> MetricsStore:
    """Get a fresh metrics store for each test."""
    store = MetricsStore()
    store.clear()  # Clear any existing metrics
    return store


class TestMetricsStore:
    """Tests for MetricsStore functionality."""

    def test_record_metric(self, metrics_store: MetricsStore) -> None:
        """Test recording a single metric."""
        metrics_store.record(
            metric_type="test_metric",
            correlation_id="test-cid-1",
            value_ms=100.0,
            metadata={"key": "value"},
        )

        metrics = metrics_store.get_metrics("test_metric")
        assert len(metrics) == 1
        assert metrics[0].correlation_id == "test-cid-1"
        assert metrics[0].value_ms == 100.0
        assert metrics[0].metadata["key"] == "value"

    def test_record_multiple_metrics(self, metrics_store: MetricsStore) -> None:
        """Test recording multiple metrics."""
        for i in range(10):
            metrics_store.record(
                metric_type="test_metric",
                correlation_id=f"test-cid-{i}",
                value_ms=float(i * 10),
            )

        metrics = metrics_store.get_metrics("test_metric")
        assert len(metrics) == 10

        # Check values are in order
        values = [m.value_ms for m in metrics]
        assert values == [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0]

    def test_get_metrics_for_nonexistent_type(self, metrics_store: MetricsStore) -> None:
        """Test getting metrics for a type that doesn't exist."""
        metrics = metrics_store.get_metrics("nonexistent")
        assert metrics == []

    def test_get_percentiles(self, metrics_store: MetricsStore) -> None:
        """Test percentile calculation."""
        # Record 100 metrics with values 0-99
        for i in range(100):
            metrics_store.record(
                metric_type="percentile_test",
                correlation_id=f"cid-{i}",
                value_ms=float(i),
            )

        percentiles = metrics_store.get_percentiles("percentile_test", [50, 95, 99])
        assert percentiles is not None
        assert percentiles["p50"] == 50.0
        assert percentiles["p95"] == 95.0
        assert percentiles["p99"] == 99.0

    def test_get_percentiles_no_metrics(self, metrics_store: MetricsStore) -> None:
        """Test percentile calculation with no metrics."""
        percentiles = metrics_store.get_percentiles("nonexistent")
        assert percentiles is None

    def test_get_percentiles_default(self, metrics_store: MetricsStore) -> None:
        """Test default percentiles (50, 95, 99)."""
        for i in range(100):
            metrics_store.record(
                metric_type="default_test",
                correlation_id=f"cid-{i}",
                value_ms=float(i),
            )

        percentiles = metrics_store.get_percentiles("default_test")
        assert percentiles is not None
        assert "p50" in percentiles
        assert "p95" in percentiles
        assert "p99" in percentiles

    def test_get_summary(self, metrics_store: MetricsStore) -> None:
        """Test summary statistics."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for i, val in enumerate(values):
            metrics_store.record(
                metric_type="summary_test",
                correlation_id=f"cid-{i}",
                value_ms=val,
            )

        summary = metrics_store.get_summary("summary_test")
        assert summary is not None
        assert summary["count"] == 5
        assert summary["min_ms"] == 10.0
        assert summary["max_ms"] == 50.0
        assert summary["mean_ms"] == 30.0
        assert summary["p50_ms"] == 30.0
        assert summary["p95_ms"] == 50.0
        assert summary["p99_ms"] == 50.0

    def test_clear_specific_type(self, metrics_store: MetricsStore) -> None:
        """Test clearing a specific metric type."""
        metrics_store.record("type1", "cid-1", 10.0)
        metrics_store.record("type2", "cid-2", 20.0)

        assert len(metrics_store.get_metrics("type1")) == 1
        assert len(metrics_store.get_metrics("type2")) == 1

        metrics_store.clear("type1")

        assert len(metrics_store.get_metrics("type1")) == 0
        assert len(metrics_store.get_metrics("type2")) == 1

    def test_clear_all(self, metrics_store: MetricsStore) -> None:
        """Test clearing all metrics."""
        metrics_store.record("type1", "cid-1", 10.0)
        metrics_store.record("type2", "cid-2", 20.0)

        metrics_store.clear()

        assert len(metrics_store.get_metrics("type1")) == 0
        assert len(metrics_store.get_metrics("type2")) == 0

    def test_max_metrics_limit(self, metrics_store: MetricsStore) -> None:
        """Test that metrics store respects the max limit."""
        # Record more than the default limit of 1000
        for i in range(1100):
            metrics_store.record(
                metric_type="limit_test",
                correlation_id=f"cid-{i}",
                value_ms=float(i),
            )

        metrics = metrics_store.get_metrics("limit_test")
        assert len(metrics) <= 1000

        # Check that we kept the most recent metrics
        assert metrics[0].correlation_id == "cid-100"  # First kept metric
        assert metrics[-1].correlation_id == "cid-1099"  # Last metric

    def test_export(self, metrics_store: MetricsStore) -> None:
        """Test exporting all metrics."""
        metrics_store.record("type1", "cid-1", 10.0, {"key": "value1"})
        metrics_store.record("type2", "cid-2", 20.0, {"key": "value2"})

        exported = metrics_store.export()
        assert "type1" in exported
        assert "type2" in exported
        assert len(exported["type1"]) == 1
        assert len(exported["type2"]) == 1
        assert exported["type1"][0]["correlation_id"] == "cid-1"
        assert exported["type2"][0]["correlation_id"] == "cid-2"


class TestMetricTimer:
    """Tests for MetricTimer context manager."""

    def test_timer_records_metric(self) -> None:
        """Test that timer records a metric on exit."""
        store = get_metrics_store()
        store.clear()

        with MetricTimer("test_operation", "test-cid"):
            time.sleep(0.01)  # Small delay

        metrics = store.get_metrics("test_operation")
        assert len(metrics) == 1
        assert metrics[0].correlation_id == "test-cid"
        assert metrics[0].value_ms >= 10  # At least 10ms

    def test_timer_with_metadata(self) -> None:
        """Test timer with custom metadata."""
        store = get_metrics_store()
        store.clear()

        timer = MetricTimer("test_operation", "test-cid", metadata={"key": "value"})
        with timer:
            timer.metadata["extra"] = "data"

        metrics = store.get_metrics("test_operation")
        assert len(metrics) == 1
        assert metrics[0].metadata["key"] == "value"
        assert metrics[0].metadata["extra"] == "data"

    def test_timer_with_exception(self) -> None:
        """Test that timer records error on exception."""
        store = get_metrics_store()
        store.clear()

        with pytest.raises(ValueError):
            with MetricTimer("test_operation", "test-cid"):
                raise ValueError("test error")

        metrics = store.get_metrics("test_operation")
        assert len(metrics) == 1
        assert metrics[0].metadata["error"] == "ValueError"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_record_metric_convenience(self) -> None:
        """Test the record_metric convenience function."""
        store = get_metrics_store()
        store.clear()

        record_metric("convenience_test", "test-cid", 42.0, {"key": "value"})

        metrics = store.get_metrics("convenience_test")
        assert len(metrics) == 1
        assert metrics[0].value_ms == 42.0
        assert metrics[0].metadata["key"] == "value"

    def test_get_metrics_store_singleton(self) -> None:
        """Test that get_metrics_store returns the same instance."""
        store1 = get_metrics_store()
        store2 = get_metrics_store()
        assert store1 is store2
