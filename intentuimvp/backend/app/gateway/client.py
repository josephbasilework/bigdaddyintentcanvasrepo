"""Pydantic AI Gateway client for all LLM inference.

CRITICAL: All LLM calls MUST go through this module. No direct
provider SDK imports (OpenAI, Anthropic, etc.) allowed elsewhere.

Implements NFR-PERF-003: Gateway call latency tracking.
Implements NFR-REL-001: Retry with exponential backoff and degradation logging.
Implements NFR-PRIV-004: PII warning + log redaction rules.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UserError
from pydantic_ai.messages import (
    ImageUrl,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.gateway import gateway_provider

from app.config import get_settings
from app.pii_detector import get_pii_detector
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
        route: str | None = None,
        timeout: float = 60.0,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the Gateway client.

        Args:
            api_key: Pydantic AI Gateway API key. Defaults to env var.
            base_url: Gateway base URL (without /proxy).
            route: Gateway route slug configured in the Gateway dashboard.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts. Defaults to config.
        """
        self.api_key = api_key or settings.pydantic_gateway_api_key
        self.base_url = (base_url or settings.pydantic_gateway_base_url).rstrip("/")
        self.route = route or settings.gateway_route
        self.timeout = timeout
        # Use configured max_retries if not explicitly provided
        self.max_retries = max_retries if max_retries is not None else settings.gateway_retry_max_attempts
        self._http_client: httpx.AsyncClient | None = None
        self._providers: dict[str, Any] = {}
        self._models: dict[tuple[str, str], GoogleModel] = {}

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self._providers.clear()
        self._models.clear()

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    def _get_gateway_base_url(self) -> str:
        """Get the Gateway base URL with the proxy path appended."""
        base_url = self.base_url.rstrip("/")
        if not base_url.endswith("/proxy"):
            base_url = f"{base_url}/proxy"
        return base_url

    def _get_provider(self, route: str) -> Any:
        """Get or create a Gateway provider for the route."""
        if not route:
            raise GatewayClientError(
                "Gateway route is required. Set GATEWAY_ROUTE or use model format <route>/<model>."
            )
        provider = self._providers.get(route)
        if provider is None:
            provider = gateway_provider(
                "google-vertex",
                route=route,
                api_key=self.api_key,
                base_url=self._get_gateway_base_url(),
                http_client=self._get_http_client(),
            )
            self._providers[route] = provider
        return provider

    def _get_model(self, model_name: str, route: str) -> GoogleModel:
        """Get or create a Google model for the given route."""
        cache_key = (route, model_name)
        model = self._models.get(cache_key)
        if model is None:
            provider = self._get_provider(route)
            model = GoogleModel(model_name, provider=provider)
            self._models[cache_key] = model
        return model

    def _split_model(self, model: str) -> tuple[str, str]:
        """Split model into route and model name."""
        if "/" in model:
            route, model_name = model.split("/", 1)
            return route, model_name
        return self.route, model

    def _normalize_text_content(self, content: Any) -> str:
        """Normalize message content to plain text."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            return "\n".join(part for part in parts if part)
        return str(content)

    def _normalize_user_content(self, content: Any) -> str | list[Any]:
        """Normalize user content into Pydantic AI-compatible parts."""
        if isinstance(content, list):
            parts: list[Any] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    item_type = item.get("type")
                    if item_type == "text":
                        text = item.get("text")
                        if text:
                            parts.append(str(text))
                    elif item_type == "image_url":
                        image_url = (item.get("image_url") or {}).get("url")
                        if image_url:
                            parts.append(ImageUrl(image_url))
            return parts if parts else ""
        return self._normalize_text_content(content)

    def _build_model_messages(self, messages: list[dict[str, Any]]) -> list[ModelMessage]:
        """Convert OpenAI-style messages into Pydantic AI messages."""
        model_messages: list[ModelMessage] = []
        request_parts: list[Any] = []

        for message in messages:
            role = (message.get("role") or "").lower()
            content = message.get("content")

            if role == "assistant":
                if request_parts:
                    model_messages.append(ModelRequest(parts=request_parts))
                    request_parts = []

                response_parts: list[Any] = []
                text = self._normalize_text_content(content)
                if text:
                    response_parts.append(TextPart(content=text))

                for tool_call in message.get("tool_calls", []) or []:
                    function = tool_call.get("function") or {}
                    tool_call_id = tool_call.get("id")
                    if tool_call_id:
                        response_parts.append(
                            ToolCallPart(
                                tool_name=function.get("name", ""),
                                args=function.get("arguments"),
                                tool_call_id=tool_call_id,
                            )
                        )
                    else:
                        response_parts.append(
                            ToolCallPart(
                                tool_name=function.get("name", ""),
                                args=function.get("arguments"),
                            )
                        )

                if response_parts:
                    model_messages.append(ModelResponse(parts=response_parts))
                continue

            if role == "system":
                request_parts.append(SystemPromptPart(self._normalize_text_content(content)))
                continue

            if role == "user":
                request_parts.append(UserPromptPart(self._normalize_user_content(content)))
                continue

            if role == "tool":
                tool_name = message.get("name") or "tool"
                tool_call_id = message.get("tool_call_id")
                part_kwargs = {"tool_name": tool_name, "content": content}
                if tool_call_id:
                    part_kwargs["tool_call_id"] = tool_call_id
                request_parts.append(ToolReturnPart(**part_kwargs))
                continue

            request_parts.append(UserPromptPart(self._normalize_text_content(content)))

        if request_parts:
            model_messages.append(ModelRequest(parts=request_parts))

        return model_messages

    def _build_model_settings(self, request_kwargs: dict[str, Any]) -> dict[str, Any]:
        """Map OpenAI-style kwargs to Pydantic AI model settings."""
        settings_map = {
            "temperature": request_kwargs.get("temperature"),
            "top_p": request_kwargs.get("top_p"),
            "max_tokens": request_kwargs.get("max_tokens"),
            "stop_sequences": request_kwargs.get("stop_sequences"),
            "presence_penalty": request_kwargs.get("presence_penalty"),
            "frequency_penalty": request_kwargs.get("frequency_penalty"),
            "seed": request_kwargs.get("seed"),
            "timeout": request_kwargs.get("timeout", self.timeout),
        }

        if "stop" in request_kwargs and settings_map["stop_sequences"] is None:
            settings_map["stop_sequences"] = request_kwargs.get("stop")

        return {key: value for key, value in settings_map.items() if value is not None}

    async def _request_model(
        self,
        model_name: str,
        route: str,
        messages: list[ModelMessage],
        model_settings: dict[str, Any],
    ) -> ModelResponse:
        """Request a completion via the Pydantic AI Gateway provider."""
        model = self._get_model(model_name, route)
        request_params = ModelRequestParameters()
        return await model.request(messages, model_settings, request_params)

    def _build_openai_response(
        self,
        response: ModelResponse,
        model_name: str,
    ) -> dict[str, Any]:
        """Convert Pydantic AI response into OpenAI-compatible payload."""
        tool_calls = [
            {
                "id": call.tool_call_id,
                "type": "function",
                "function": {
                    "name": call.tool_name,
                    "arguments": call.args_as_json_str(),
                },
            }
            for call in response.tool_calls
        ]

        content = response.text or ""
        if tool_calls and not content:
            message_content: str | None = None
        else:
            message_content = content

        usage = response.usage
        return {
            "id": response.provider_response_id or "gateway",
            "object": "chat.completion",
            "created": int(response.timestamp.timestamp()),
            "model": response.model_name or model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": message_content,
                        **({"tool_calls": tool_calls} if tool_calls else {}),
                    },
                    "finish_reason": response.finish_reason or ("tool_calls" if tool_calls else "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": usage.input_tokens,
                "completion_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            },
        }

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
            model: Model name (e.g., "gemini-3-flash-preview").
            messages: Chat messages in OpenAI format.
            **kwargs: Additional request parameters (temperature, etc.).

        Returns:
            Response JSON from the Gateway.

        Raises:
            GatewayClientError: If all retries are exhausted.
            GatewayDegradedError: With degradation context on retry exhaustion.
        """
        last_error: Exception | None = None
        degraded_since = asyncio.get_event_loop().time()

        for attempt in range(self.max_retries):
            try:
                # Track Gateway call latency with telemetry
                with track_gateway_call(model=model, operation="chat"):
                    response = await self._make_request(model=model, messages=messages, **kwargs)

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

            except GatewayClientError:
                raise
            except ModelHTTPError as e:
                last_error = e
                # Don't retry client errors (4xx)
                if 400 <= e.status_code < 500:
                    logger.error(
                        "Gateway request failed with client error (not retryable)",
                        extra={
                            "event": "gateway_client_error",
                            "status_code": e.status_code,
                            "model": model,
                        },
                    )
                    raise GatewayClientError(
                        f"Gateway request failed: {e.status_code}"
                    ) from e

                # Log server errors (5xx) before retry
                logger.warning(
                    "Gateway request failed with server error, retrying",
                    extra={
                        "event": "gateway_server_error",
                        "status_code": e.status_code,
                        "attempt": attempt + 1,
                        "max_attempts": self.max_retries,
                        "model": model,
                    },
                )

            except (ModelAPIError, httpx.RequestError, httpx.TimeoutException) as e:
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

        # Add jitter before capping to ensure we never exceed max
        if settings.gateway_retry_jitter:
            jitter_range = exponential_delay * 0.25
            jitter = random.uniform(-jitter_range, jitter_range)
            delayed = exponential_delay + jitter
        else:
            delayed = exponential_delay

        # Cap at max delay (after jitter to ensure we never exceed)
        final_delay = min(int(delayed), settings.gateway_retry_max_delay_ms)

        return max(final_delay, base_delay)  # Ensure at least base delay

    async def _make_request(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a single request to the Gateway.

        Implements NFR-PRIV-004: PII warning before sending to external services.

        Args:
            model: Model name or legacy route/model format.
            messages: OpenAI-style message payloads.
            **kwargs: Additional request settings (temperature, max_tokens, etc.).

        Returns:
            OpenAI-compatible response JSON.

        Raises:
            ModelHTTPError: On HTTP errors.
            ModelAPIError: On API errors.
        """
        payload = {
            "model": model,
            "messages": messages,
            **kwargs,
        }

        # Scan for PII before sending to Gateway
        pii_detector = get_pii_detector()
        text_content = self._extract_text_from_payload(payload)

        if text_content:
            pii_result = pii_detector.scan(text_content, context="Gateway request")

            if pii_result.has_pii:
                logger.warning(
                    pii_result.warning_message or "PII detected in Gateway request",
                    extra={
                        "event": "pii_detected",
                        "pii_types": [d.type.value for d in pii_result.detections],
                        "severity": pii_result.severity.value,
                        "model": payload.get("model", "unknown"),
                    },
                )

                # Check if request should be blocked
                if pii_detector.is_blocked(pii_result):
                    raise GatewayClientError(
                        f"Request blocked: PII detected with severity {pii_result.severity.value}. "
                        f"Content must be reviewed before sending to external services."
                    )

        route, model_name = self._split_model(model)
        model_messages = self._build_model_messages(messages)
        model_settings = self._build_model_settings(kwargs)

        try:
            response = await self._request_model(
                model_name=model_name,
                route=route,
                messages=model_messages,
                model_settings=model_settings,
            )
        except UserError as e:
            raise GatewayClientError(str(e)) from e

        return self._build_openai_response(response, model_name)

    def _extract_text_from_payload(self, payload: dict[str, Any]) -> str:
        """Extract text content from payload for PII scanning.

        Args:
            payload: Gateway request payload.

        Returns:
            Concatenated text content from messages.
        """
        messages = payload.get("messages", [])
        if not messages:
            return ""

        # Extract content from each message
        text_parts: list[str] = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                # Handle multimodal content (text + images, etc.)
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))

        return "\n".join(text_parts)


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
