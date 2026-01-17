
"""Tests for Gateway retry behavior and degradation handling (NFR-REL-001)."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import ModelResponse, TextPart

from app.gateway.client import GatewayClient, GatewayDegradedError


class TestGatewayDegradedError:
    """Test GatewayDegradedError with degradation info."""

    @pytest.mark.asyncio
    async def test_degraded_error_contains_info(self):
        """Test that GatewayDegradedError contains degradation information."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com", max_retries=2)

        mock_request = AsyncMock(
            side_effect=ModelAPIError(model_name="gemini-3-flash-preview", message="Network error")
        )

        with patch.object(client, "_request_model", mock_request):
            with pytest.raises(GatewayDegradedError) as exc_info:
                await client.generate(
                    model="gemini-3-flash-preview",
                    messages=[{"role": "user", "content": "Test"}],
                )

        error = exc_info.value
        assert hasattr(error, "degradation_info")
        assert error.degradation_info.model == "gemini-3-flash-preview"
        assert error.degradation_info.attempts == 2
        assert error.degradation_info.error_type == "ModelAPIError"
        assert "Network error" in error.degradation_info.last_error
        assert isinstance(error.degradation_info.degraded_since, float)

    @pytest.mark.asyncio
    async def test_degraded_error_with_timeout(self):
        """Test GatewayDegradedError with timeout errors."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com", max_retries=3)

        mock_request = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))

        with patch.object(client, "_request_model", mock_request):
            with pytest.raises(GatewayDegradedError) as exc_info:
                await client.generate(
                    model="gemini-3-flash-preview",
                    messages=[{"role": "user", "content": "Test"}],
                )

        error = exc_info.value
        assert error.degradation_info.error_type == "TimeoutException"
        assert error.degradation_info.model == "gemini-3-flash-preview"
        assert error.degradation_info.attempts == 3


class TestGatewayBackoffCalculation:
    """Test exponential backoff with jitter calculation."""

    def test_backoff_delay_increases_exponentially(self):
        """Test that backoff delay increases exponentially."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        # With default config: base=1000ms, max=30000ms
        # Attempt 0: 1000ms
        # Attempt 1: 2000ms
        # Attempt 2: 4000ms
        # Attempt 3: 8000ms
        # Attempt 4: 16000ms
        # Attempt 5+: capped at 30000ms

        delay_0 = client._calculate_backoff_delay(0)
        delay_1 = client._calculate_backoff_delay(1)
        delay_2 = client._calculate_backoff_delay(2)

        # Should roughly double each time (within jitter range)
        assert 750 <= delay_0 <= 1250  # 1000 ± 25%
        assert 1500 <= delay_1 <= 2500  # 2000 ± 25%
        assert 3000 <= delay_2 <= 5000  # 4000 ± 25%

    def test_backoff_delay_capped_at_max(self):
        """Test that backoff delay is capped at max_delay."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        # With default max_delay=30000ms, even high attempts should be capped
        for attempt in range(10):
            delay = client._calculate_backoff_delay(attempt)
            assert delay <= 30000, f"Attempt {attempt} exceeded max: {delay}ms"

    def test_backoff_without_jitter(self):
        """Test backoff without jitter is deterministic."""
        with patch("app.gateway.client.settings") as mock_settings:
            # Configure with jitter disabled
            mock_settings.gateway_retry_base_delay_ms = 1000
            mock_settings.gateway_retry_max_delay_ms = 30000
            mock_settings.gateway_retry_jitter = False

            client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

            # Without jitter, delays should be exact
            delay_0 = client._calculate_backoff_delay(0)
            delay_1 = client._calculate_backoff_delay(1)
            delay_2 = client._calculate_backoff_delay(2)

            assert delay_0 == 1000
            assert delay_1 == 2000
            assert delay_2 == 4000


class TestGatewayRetryWithConfig:
    """Test Gateway retry behavior using configuration settings."""

    @pytest.mark.asyncio
    async def test_max_retries_from_config(self):
        """Test that max_retries defaults from configuration."""
        # Client with no explicit max_retries should use config
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        # Should use config value (default: 3)
        assert client.max_retries == 3

    @pytest.mark.asyncio
    async def test_explicit_max_retries_overrides_config(self):
        """Test that explicit max_retries overrides config."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com", max_retries=5)

        assert client.max_retries == 5

    @pytest.mark.asyncio
    async def test_server_error_retries_with_backoff(self):
        """Test that 5xx errors trigger retries with backoff."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com", max_retries=3)

        mock_response_success = ModelResponse(
            parts=[TextPart(content="Success")],
            model_name="gemini-3-flash-preview",
        )
        mock_request = AsyncMock(
            side_effect=[
                ModelHTTPError(status_code=500, model_name="gemini-3-flash-preview"),
                mock_response_success,
            ]
        )

        with patch.object(client, "_request_model", mock_request):
            result = await client.generate(
                model="gemini-3-flash-preview",
                messages=[{"role": "user", "content": "Test"}],
            )

        assert result["choices"][0]["message"]["content"] == "Success"
        assert mock_request.call_count == 2
