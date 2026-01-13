"""Tests for telemetry module.

Tests performance metrics instrumentation for NFR-PERF targets.
"""

from unittest.mock import Mock, patch

import pytest

from app.telemetry import (
    initialize_logfire,
    record_metric,
)


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
    with patch("app.telemetry.logfire") as m:
        m.configure = Mock()
        m.info = Mock()
        m.warning = Mock()
        m.span = Mock()
        m.metric = Mock()
        m.increment = Mock()
        yield m


@pytest.fixture
def mock_correlation_id():
    """Mock correlation ID."""
    with patch("app.telemetry.get_correlation_id", return_value="test-cid-123"):
        yield "test-cid-123"


class TestInitializeLogfire:
    """Tests for initialize_logfire function."""

    def test_initialize_logfire_success(self, mock_settings, mock_logfire):
        """Test successful Logfire initialization."""
        initialize_logfire(mock_settings)

        mock_logfire.configure.assert_called_once_with(
            send_to_logfire=False,
            service_name="test-app",
            service_version="0.1.0",
        )
        mock_logfire.info.assert_called_once()

    def test_initialize_logfire_failure(self, mock_settings, mock_logfire):
        """Test Logfire initialization failure doesn''t crash."""
        mock_logfire.configure.side_effect = Exception("Init failed")

        # Should not raise
        initialize_logfire(mock_settings)

        mock_logfire.warning.assert_called_once()


class TestRecordMetric:
    """Tests for record_metric function."""

    def test_record_metric_basic(self, mock_logfire, mock_correlation_id):
        """Test basic metric recording."""
        record_metric("test_metric", 123.4)

        mock_logfire.metric.assert_called_once_with(
            "intentui.perf.test_metric",
            123.4,
            correlation_id="test-cid-123",
            unit="ms",
        )
