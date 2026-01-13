"""Middleware for request/response logging with correlation IDs.

Implements NFR-OBS-001: API endpoints request/response logging (no secrets)

Logs all HTTP requests and responses with:
- Correlation ID for trace reconstruction
- Request method, path, headers (sanitized)
- Response status, duration
- Client IP and user agent
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import (
    clear_correlation_id,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)

logger = get_logger(__name__)


# Headers that may contain sensitive data - exclude from logs
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "secret",
    "password",
    "token",
}


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Sanitize request headers by removing sensitive values.

    Args:
        headers: Original headers dictionary.

    Returns:
        Headers with sensitive values redacted.
    """
    return {
        k: "[REDACTED]" if any(s in k.lower() for s in SENSITIVE_HEADERS) else v
        for k, v in headers.items()
    }


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured HTTP request/response logging.

    Implements NFR-OBS-001 by logging all API requests and responses with:
    - Correlation ID for distributed tracing
    - Request method, path, query parameters
    - Response status code and duration
    - Sanitized headers (no secrets)

    Each request gets a unique correlation ID that propagates through
    the entire request lifecycle, enabling trace reconstruction.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request and log request/response details.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler in the chain.

        Returns:
            The HTTP response from the downstream handler.
        """
        # Generate or retrieve correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = get_correlation_id()
        set_correlation_id(correlation_id)

        # Start timer for request duration
        start_time = time.time()

        # Extract request details
        method = request.method
        path = request.url.path
        query_params = str(request.query_params) if request.query_params else None
        client_host = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Sanitize headers for logging
        sanitized_headers = _sanitize_headers(dict(request.headers))

        # Log incoming request (NFR-OBS-001)
        logger.info(
            "Incoming request",
            extra={
                "event": "http_request",
                "method": method,
                "path": path,
                "query_params": query_params,
                "client_host": client_host,
                "user_agent": user_agent,
                "headers": sanitized_headers,
                "correlation_id": correlation_id,
            },
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log response (NFR-OBS-001)
            log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
            logger.log(
                log_level,
                "Outgoing response",
                extra={
                    "event": "http_response",
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "correlation_id": correlation_id,
                },
            )

            # Add correlation ID to response headers for client-side tracing
            response.headers["X-Correlation-ID"] = correlation_id

            return response

        except Exception as e:
            # Calculate duration for failed requests
            duration_ms = (time.time() - start_time) * 1000

            # Log error (NFR-OBS-005: Structured error logging)
            logger.error(
                "Request failed with exception",
                extra={
                    "event": "http_error",
                    "method": method,
                    "path": path,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "correlation_id": correlation_id,
                },
                exc_info=True,
            )
            raise

        finally:
            # Clear correlation ID from context
            clear_correlation_id()
