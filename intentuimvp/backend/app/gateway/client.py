"""Pydantic AI Gateway client for all LLM inference.

CRITICAL: All LLM calls MUST go through this module. No direct
provider SDK imports (OpenAI, Anthropic, etc.) allowed elsewhere.
"""

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class GatewayClientError(Exception):
    """Base exception for Gateway client errors."""

    pass


class GatewayClient:
    """Client for Pydantic AI Gateway.

    All LLM inference requests must go through this client to ensure
    Gateway-only enforcement and consistent error handling.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize the Gateway client.

        Args:
            api_key: Pydantic AI Gateway API key. Defaults to env var.
            base_url: Gateway base URL.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
        """
        self.api_key = api_key or settings.pydantic_gateway_api_key
        self.base_url = (base_url or settings.pydantic_gateway_base_url).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
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

        Args:
            model: Model identifier (e.g., "openai/gpt-4o").
            messages: Chat messages in OpenAI format.
            **kwargs: Additional request parameters (temperature, etc.).

        Returns:
            Response JSON from the Gateway.

        Raises:
            GatewayClientError: If all retries are exhausted.
        """
        payload = {
            "model": model,
            "messages": messages,
            **kwargs,
        }

        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self._make_request(payload)
                logger.info(
                    "Gateway request succeeded",
                    extra={
                        "model": model,
                        "attempt": attempt + 1,
                    },
                )
                return response

            except httpx.HTTPStatusError as e:
                last_error = e
                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    logger.error(
                        "Gateway request failed with client error",
                        extra={
                            "status_code": e.response.status_code,
                            "attempt": attempt + 1,
                        },
                    )
                    raise GatewayClientError(
                        f"Gateway request failed: {e.response.status_code}"
                    ) from e

            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(
                    "Gateway request failed with network error, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self.max_retries,
                    },
                )

            # Exponential backoff: 1s, 2s, 4s
            if attempt < self.max_retries - 1:
                backoff = 2**attempt
                logger.debug(f"Backing off for {backoff}s before retry")
                await _async_sleep(backoff)

        # All retries exhausted
        raise GatewayClientError(
            f"Gateway request failed after {self.max_retries} attempts"
        ) from last_error

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


async def _async_sleep(seconds: float) -> None:
    """Async sleep for backoff."""
    import asyncio

    await asyncio.sleep(seconds)


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
