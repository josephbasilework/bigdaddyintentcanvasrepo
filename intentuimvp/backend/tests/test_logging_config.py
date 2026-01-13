"""Tests for structured logging configuration.

Tests the logging_config module which implements:
- FR-022: Observability + Auditability
- NFR-OBS-001: API endpoints request/response logging (no secrets)
- NFR-OBS-002: Agent invocations latency, success/failure metrics
- NFR-OBS-003: Job system lifecycle events, duration, outcomes
- NFR-OBS-004: WebSocket connection events, message counts
- NFR-OBS-005: Structured error logging with correlation IDs
"""

import json
import logging

from app.logging_config import (
    JsonFormatter,
    LogHelper,
    RedactingFormatter,
    clear_correlation_id,
    configure_logging,
    create_log_helper,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)


class TestCorrelationId:
    """Tests for correlation ID context management."""

    def test_get_correlation_id_generates_new_id(self):
        """get_correlation_id should generate a new UUID when none is set."""
        clear_correlation_id()
        cid = get_correlation_id()
        assert cid is not None
        assert len(cid) == 36  # UUID string length

    def test_get_correlation_id_returns_existing(self):
        """get_correlation_id should return the existing ID when set."""
        expected_cid = "test-correlation-id-123"
        set_correlation_id(expected_cid)
        actual_cid = get_correlation_id()
        assert actual_cid == expected_cid

    def test_clear_correlation_id(self):
        """clear_correlation_id should remove the correlation ID."""
        set_correlation_id("test-id")
        clear_correlation_id()
        # Getting a new ID after clearing should generate a new UUID
        new_cid = get_correlation_id()
        assert new_cid != "test-id"


class TestJsonFormatter:
    """Tests for JsonFormatter."""

    def test_add_fields_includes_timestamp(self):
        """JsonFormatter should add timestamp in ISO 8601 format."""
        formatter = JsonFormatter()
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = {}
        formatter.add_fields(result, log_record, {})

        assert "timestamp" in result
        assert "T" in result["timestamp"] or result["timestamp"].count("-") == 2

    def test_add_fields_includes_correlation_id(self):
        """JsonFormatter should include correlation ID when set."""
        formatter = JsonFormatter()
        set_correlation_id("test-cid-123")

        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = {}
        formatter.add_fields(result, log_record, {})

        assert result.get("correlation_id") == "test-cid-123"
        clear_correlation_id()

    def test_add_fields_includes_standard_fields(self):
        """JsonFormatter should include standard logging fields."""
        formatter = JsonFormatter()

        log_record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        log_record.funcName = "test_function"
        log_record.module = "test_module"

        result = {}
        formatter.add_fields(result, log_record, {})

        assert result.get("level") == "INFO"
        assert result.get("logger") == "test.logger"
        assert result.get("module") == "test_module"
        assert result.get("function") == "test_function"
        assert result.get("line") == 42


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_logging_sets_root_level(self, caplog):
        """configure_logging should set the root logger level."""
        configure_logging(level=logging.DEBUG)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_configure_logging_json_format(self):
        """configure_logging with json_format=True should use JsonFormatter."""
        configure_logging(level=logging.INFO, json_format=True)

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, JsonFormatter)

    def test_configure_logging_text_format(self):
        """configure_logging with json_format=False should use text formatter."""
        configure_logging(level=logging.INFO, json_format=False)

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

        handler = root_logger.handlers[0]
        assert not isinstance(handler.formatter, JsonFormatter)

    def test_configure_logging_custom_handler(self):
        """configure_logging should accept a custom handler."""
        custom_handler = logging.StreamHandler()
        configure_logging(level=logging.INFO, handler=custom_handler)

        root_logger = logging.getLogger()
        assert custom_handler in root_logger.handlers


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """get_logger should return a logging.Logger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_same_name_returns_same_instance(self):
        """get_logger should return the same logger for the same name."""
        logger1 = get_logger("test.module.same")
        logger2 = get_logger("test.module.same")
        assert logger1 is logger2


class TestLogHelper:
    """Tests for LogHelper class."""

    def test_log_helper_info(self, caplog):
        """LogHelper.info should log info messages with component field."""
        caplog.set_level(logging.INFO)
        logger = get_logger("test.helper")
        helper = LogHelper(logger, "test_component")

        helper.info("Test message", extra_field="extra_value")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.message == "Test message"
        assert record.levelno == logging.INFO
        assert record.component == "test_component"

    def test_log_helper_warning(self, caplog):
        """LogHelper.warning should log warning messages."""
        caplog.set_level(logging.WARNING)
        logger = get_logger("test.helper")
        helper = LogHelper(logger, "test_component")

        helper.warning("Warning message")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING

    def test_log_helper_error(self, caplog):
        """LogHelper.error should log error messages."""
        caplog.set_level(logging.ERROR)
        logger = get_logger("test.helper")
        helper = LogHelper(logger, "test_component")

        helper.error("Error message")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.ERROR

    def test_log_helper_debug(self, caplog):
        """LogHelper.debug should log debug messages."""
        caplog.set_level(logging.DEBUG)
        logger = get_logger("test.helper")
        helper = LogHelper(logger, "test_component")

        helper.debug("Debug message")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG


class TestCreateLogHelper:
    """Tests for create_log_helper function."""

    def test_create_log_helper_returns_log_helper(self):
        """create_log_helper should return a LogHelper instance."""
        logger = get_logger("test.create")
        helper = create_log_helper(logger, "test_component")

        assert isinstance(helper, LogHelper)


class TestSecretRedaction:
    """Tests for secret redaction in log formatters.

    Implements FR-022 AC: "Given log inspected, When secrets searched, Then no secrets present"

    NOTE: Test strings are constructed programmatically to avoid triggering GitHub
    secret scanning on the test data itself.
    """

    def test_json_formatter_redacts_openai_api_key(self):
        """JsonFormatter should redact OpenAI API keys (sk-*)."""
        formatter = JsonFormatter()
        # Construct test key to avoid secret scanning
        test_key = "sk-" + "abc123def456789012345678901234567890"
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=f"API key: {test_key}",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        assert result["message"] == "API key: [REDACTED]"
        assert test_key not in json_str

    def test_json_formatter_redacts_anthropic_api_key(self):
        """JsonFormatter should redact Anthropic API keys (sk-ant-*)."""
        formatter = JsonFormatter()
        # Construct test key to avoid secret scanning
        test_key = "sk-ant-" + "api123" + "-" + "4567890123456789012345678901234567890"
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=f"Using key: {test_key}",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        assert result["message"] == "Using key: [REDACTED]"

    def test_json_formatter_redacts_email_addresses(self):
        """JsonFormatter should redact email addresses."""
        formatter = JsonFormatter()
        # Construct email to avoid secret scanning
        email = "user" + "@" + "example.com"
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=f"User email: {email}",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        assert result["message"] == "User email: [REDACTED]"

    def test_json_formatter_redacts_phone_numbers(self):
        """JsonFormatter should redact phone numbers."""
        formatter = JsonFormatter()
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Call us at 555-123-4567",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        assert result["message"] == "Call us at [REDACTED]"

    def test_json_formatter_redacts_credit_cards(self):
        """JsonFormatter should redact credit card numbers."""
        formatter = JsonFormatter()
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Card: 4111-1111-1111-1111",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        assert result["message"] == "Card: [REDACTED]"

    def test_json_formatter_redacts_aws_access_keys(self):
        """JsonFormatter should redact AWS Access Keys."""
        formatter = JsonFormatter()
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="AWS key: AKIAIOSFODNN7EXAMPLE",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        assert result["message"] == "AWS key: [REDACTED]"

    def test_json_formatter_redacts_github_tokens(self):
        """JsonFormatter should redact GitHub personal access tokens."""
        formatter = JsonFormatter()
        # Construct test token to avoid secret scanning
        test_token = "ghp_" + "1234567890" + "abcdefghijklmnopqrstuvwxyz" + "123456"
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=f"GH token: {test_token}",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        # Note: The "token: <value>" pattern is matched as a whole
        assert result["message"] == "GH [REDACTED]"

    def test_json_formatter_redacts_slack_tokens(self):
        """JsonFormatter should redact Slack tokens."""
        formatter = JsonFormatter()
        # Construct test token to avoid secret scanning
        prefix = "xoxb-"
        mid = "1234567890"
        suffix = "-" + "1234567890123" + "-" + "AbCdEfGhIjKlMnOpQrStUv"
        test_token = prefix + mid + suffix
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=f"Slack bot token: {test_token}",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        # Note: The "token: <value>" pattern is matched as a whole
        assert result["message"] == "Slack bot [REDACTED]"

    def test_json_formatter_redacts_generic_secrets(self):
        """JsonFormatter should redact generic secret patterns."""
        formatter = JsonFormatter()
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Secret: secret=abc123def456789012345",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        assert result["message"] == "Secret: [REDACTED]"

    def test_json_formatter_redacts_uuids(self):
        """JsonFormatter should redact UUID patterns."""
        formatter = JsonFormatter()
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="UUID: 550e8400-e29b-41d4-a716-446655440000",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        assert result["message"] == "UUID: [REDACTED]"

    def test_json_formatter_preserves_safe_content(self):
        """JsonFormatter should preserve content without secrets."""
        formatter = JsonFormatter()
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Processing request for user john_doe",
            args=(),
            exc_info=None,
        )
        json_str = formatter.format(log_record)
        result = json.loads(json_str)

        assert result["message"] == "Processing request for user john_doe"

    def test_redacting_formatter_redacts_secrets(self):
        """RedactingFormatter should redact secrets in text format."""
        formatter = RedactingFormatter(
            fmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # Construct test values to avoid secret scanning
        test_key = "sk-" + "abc123def456789012345678901234567890"
        email = "user" + "@" + "example.com"
        log_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=f"API key: {test_key}, email: {email}",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(log_record)

        assert "[REDACTED]" in formatted
        assert test_key not in formatted
        assert email not in formatted
