"""Structured logging configuration for IntentUI backend.

Implements FR-022: Observability + Auditability
- Structured JSON logging for all significant events
- Correlation IDs for trace reconstruction
- Request/response logging without secrets
- Agent invocation metrics
- Job lifecycle events
- WebSocket connection events

Logging standards (NFR-OBS):
- NFR-OBS-001: API endpoints request/response logging (no secrets)
- NFR-OBS-002: Agent invocations latency, success/failure metrics
- NFR-OBS-003: Job system lifecycle events, duration, outcomes
- NFR-OBS-004: WebSocket connection events, message counts
- NFR-OBS-005: Structured error logging with correlation IDs
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from logging import Formatter
from typing import Any

from pythonjsonlogger import jsonlogger

# Context variable for correlation ID - tracks request lifecycle across async boundaries
correlation_id_var: ContextVar[str | None] = ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> str:
    """Get the current correlation ID from context.

    Returns:
        The correlation ID for the current request context, or a new UUID if none exists.
    """
    cid = correlation_id_var.get()
    if cid is None:
        cid = str(uuid.uuid4())
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID for the current context.

    Args:
        cid: The correlation ID to set.
    """
    correlation_id_var.set(cid)


def clear_correlation_id() -> None:
    """Clear the correlation ID from the current context."""
    correlation_id_var.set(None)


class JsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context fields.

    Formats log records as JSON with structured fields including:
    - timestamp: ISO 8601 format with UTC timezone
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - logger: Logger name
    - message: Log message
    - correlation_id: Request correlation ID for trace reconstruction
    - module: Python module where log was emitted
    - function: Function name where log was emitted
    - line: Line number where log was emitted
    """

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add timestamp in ISO 8601 format with UTC
        log_record["timestamp"] = datetime.now(UTC).isoformat()

        # Add correlation ID if available
        if cid := correlation_id_var.get():
            log_record["correlation_id"] = cid

        # Add standard logging fields
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


class RedactingFormatter(Formatter):
    """Formatter that redacts sensitive values from log messages.

    Currently placeholder - full secret redaction will be implemented in T4-F7.3.
    This formatter exists to establish the pattern for secret redaction.
    """

    # Patterns that will be redacted in T4-F7.3:
    # - API keys, tokens, passwords
    # - PII (email addresses, phone numbers)
    # - Gateway credentials
    REDACT_PATTERNS: list[str] = []  # Populated in T4-F7.3

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with secret redaction.

        Args:
            record: The log record to format.

        Returns:
            Formatted log message with sensitive values redacted.
        """
        msg = super().format(record)
        # Secret redaction will be implemented in T4-F7.3
        # for pattern in self.REDACT_PATTERNS:
        #     msg = re.sub(pattern, "[REDACTED]", msg)
        return msg


def configure_logging(
    level: str | int = logging.INFO,
    *,
    json_format: bool = True,
    handler: logging.Handler | None = None,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Logging level (default: INFO). Can be string or int constant.
        json_format: If True, use JSON formatting. If False, use text format.
        handler: Optional custom handler. If None, uses StreamHandler to stdout.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create handler if not provided
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

    # Set formatter based on format preference
    formatter: logging.Formatter | JsonFormatter
    if json_format:
        formatter = JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        formatter = RedactingFormatter(
            fmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Configure uvicorn loggers to use our configuration
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)

    # Quiet down noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A logger instance configured for structured logging.
    """
    return logging.getLogger(name)


class LogHelper:
    """Helper class for structured logging with common fields.

    Provides convenience methods for logging structured events with
    consistent field naming.
    """

    def __init__(self, logger: logging.Logger, component: str) -> None:
        """Initialize the LogHelper.

        Args:
            logger: The underlying logger instance.
            component: Component name for all log entries (e.g., "agent", "job", "api").
        """
        self._logger = logger
        self._component = component

    def _log(
        self,
        level: int,
        msg: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Internal logging method with component field.

        Args:
            level: Log level (logging.INFO, etc.)
            msg: Log message.
            extra: Additional structured fields to include.
        """
        log_extra = {"component": self._component}
        if extra:
            log_extra.update(extra)
        self._logger.log(level, msg, extra=log_extra)

    def info(self, msg: str, **extra: Any) -> None:
        """Log an info message with optional extra fields."""
        self._log(logging.INFO, msg, extra=extra or None)

    def warning(self, msg: str, **extra: Any) -> None:
        """Log a warning message with optional extra fields."""
        self._log(logging.WARNING, msg, extra=extra or None)

    def error(self, msg: str, **extra: Any) -> None:
        """Log an error message with optional extra fields."""
        self._log(logging.ERROR, msg, extra=extra or None)

    def debug(self, msg: str, **extra: Any) -> None:
        """Log a debug message with optional extra fields."""
        self._log(logging.DEBUG, msg, extra=extra or None)


def create_log_helper(logger: logging.Logger, component: str) -> LogHelper:
    """Create a LogHelper for a specific component.

    Args:
        logger: The underlying logger instance.
        component: Component name for log entries.

    Returns:
        A LogHelper instance for structured logging.
    """
    return LogHelper(logger, component)
