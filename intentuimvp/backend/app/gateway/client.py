"""Pydantic AI Gateway client for all LLM inference.

CRITICAL: All LLM calls MUST go through this module. No direct
provider SDK imports (OpenAI, Anthropic, etc.) allowed elsewhere.

Implements NFR-PERF-003: Gateway call latency tracking.
Implements NFR-REL-001: Retry with exponential backoff and degradation logging.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings
from app.telemetry import track_gateway_call

logger = logging.getLogger(__name__)
settings = get_settings()


class GatewayClientError(Exception):
    """Base exception for Gateway client errors."""

    pass


@dataclass
class GatewayDegradationInfo:
    """Information about Gateway degradation event.

    Attributes:
        model: The model being requested.
        attempts: Number of retry attempts made.
        last_error: The last error encountered.
        error_type: Type of the last error.
        degraded_since: Approximate time when degradation started.
    """

    model: str
    attempts: int
    last_error: str
    error_type: str
    degraded_since: float


class GatewayDegradedError(GatewayClientError):
    """Raised when Gateway requests fail after all retry attempts.

    Indicates service degradation - the Gateway is temporarily unavailable
    or experiencing errors. The application should handle this gracefully
    with user-facing messaging and fallback behavior.
    """

    def __init__(self, message: str, degradation_info: GatewayDegradationInfo) -> None:
        """Initialize the degraded error.

        Args:
            message: Error message.
            degradation_info: Detailed degradation information.
        """
        super().__init__(message)
        self.degradation_info = degradation_info


class GatewayClient:
    """Client for Pydantic AI Gateway.

    All LLM inference requests must go through this client to ensure
    Gateway-only enforcement and consistent error handling.

    Implements NFR-REL-001: Retry with exponential backoff and degradation logging.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the Gateway client.

        Args:
            api_key: Pydantic AI Gateway API key. Defaults to env var.
            base_url: Gateway base URL.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts. Defaults to config.
        """
        self.api_key = api_key or settings.pydantic_gateway_api_key
        self.base_url = (base_url or settings.pydantic_gateway_base_url).rstrip("/")
        self.timeout = timeout
        # Use configured max_retries if not explicitly provided
        self.max_retries = max_retries if max_retries is not None else settings.gateway_retry_max_attempts
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def generate(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a completion via the Gateway.

        Implements NFR-PERF-003: Tracks Gateway call latency.
        Implements NFR-REL-001: Retry with exponential backoff and degradation logging.

        Args:
            model: Model identifier (e.g., "openai/gpt-4o").
            messages: Chat messages in OpenAI format.
            **kwargs: Additional request parameters (temperature, etc.).

        Returns:
            Response JSON from the Gateway.

        Raises:
            GatewayClientError: If all retries are exhausted.
            GatewayDegradedError: With degradation context on retry exhaustion.
        """
        payload = {
            "model": model,
            "messages": messages,
            **kwargs,
        }

        last_error: Exception | None = None
        degraded_since = asyncio.get_event_loop().time()

        for attempt in range(self.max_retries):
            try:
                # Track Gateway call latency with telemetry
                with track_gateway_call(model=model, operation="chat"):
                    response = await self._make_request(payload)

                logger.info(
                    "Gateway request succeeded",
                    extra={
                        "event": "gateway_success",
                        "model": model,
                        "attempt": attempt + 1,
                        "max_attempts": self.max_retries,
                    },
                )
                return response

            except httpx.HTTPStatusError as e:
                last_error = e
                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    logger.error(
                        "Gateway request failed with client error (not retryable)",
                        extra={
                            "event": "gateway_client_error",
                            "status_code": e.response.status_code,
                            "model": model,
                        },
                    )
                    raise GatewayClientError(
                        f"Gateway request failed: {e.response.status_code}"
                    ) from e

                # Log server errors (5xx) before retry
                logger.warning(
                    "Gateway request failed with server error, retrying",
                    extra={
                        "event": "gateway_server_error",
                        "status_code": e.response.status_code,
                        "attempt": attempt + 1,
                        "max_attempts": self.max_retries,
                        "model": model,
                    },
                )

            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(
                    "Gateway request failed with network error, retrying",
                    extra={
                        "event": "gateway_network_error",
                        "error_type": type(e).__name__,
                        "attempt": attempt + 1,
                        "max_attempts": self.max_retries,
                        "model": model,
                    },
                )

            # Calculate backoff delay with exponential backoff and jitter
            if attempt < self.max_retries - 1:
                delay_ms = self._calculate_backoff_delay(attempt)
                logger.debug(
                    f"Backing off for {delay_ms}ms before retry attempt {attempt + 2}"
                )
                await asyncio.sleep(delay_ms / 1000)

        # All retries exhausted - create degradation error with context
        degradation_info = GatewayDegradationInfo(
            model=model,
            attempts=self.max_retries,
            last_error=str(last_error) if last_error else "Unknown error",
            error_type=type(last_error).__name__ if last_error else "Unknown",
            degraded_since=degraded_since,
        )

        # Log degradation event (NFR-REL-001)
        logger.error(
            "Gateway degradation: all retry attempts exhausted",
            extra={
                "event": "gateway_degradation",
                "model": model,
                "attempts": self.max_retries,
                "error_type": degradation_info.error_type,
                "degraded_duration_s": asyncio.get_event_loop().time() - degraded_since,
            },
        )

        raise GatewayDegradedError(
            f"Gateway request failed after {self.max_retries} attempts",
            degradation_info=degradation_info,
        ) from last_error

    def _calculate_backoff_delay(self, attempt: int) -> int:
        """Calculate backoff delay with exponential backoff and jitter.

        Implements NFR-REL-001: Exponential backoff with jitter to prevent
        thundering herd problem.

        Args:
            attempt: Current attempt number (0-indexed).

        Returns:
            Delay in milliseconds.
        """
        # Exponential backoff: base * 2^attempt
        base_delay = settings.gateway_retry_base_delay_ms
        exponential_delay = base_delay * (2**attempt)

        # Cap at max delay
        capped_delay = min(exponential_delay, settings.gateway_retry_max_delay_ms)

        # Add jitter if configured (±25% of delay)
        if settings.gateway_retry_jitter:
            jitter_range = capped_delay * 0.25
            jitter = random.uniform(-jitter_range, jitter_range)
            final_delay = int(capped_delay + jitter)
        else:
            final_delay = int(capped_delay)

        return max(final_delay, base_delay)  # Ensure at least base delay

    async def _make_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Make a single request to the Gateway.

        Args:
            payload: Request payload.

        Returns:
            Response JSON.

        Raises:
            httpx.HTTPStatusError: On HTTP errors.
            httpx.RequestError: On network errors.
        """
        client = self._get_client()
        response = await client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()


# Singleton instance
_client: GatewayClient | None = None


def get_gateway_client() -> GatewayClient:
    """Get the singleton Gateway client instance.

    Returns:
        Gateway client instance.
    """
    global _client
    if _client is None:
        _client = GatewayClient()
    return _client
