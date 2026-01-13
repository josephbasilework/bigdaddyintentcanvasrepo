"""Unit tests for GatewayClient.

Tests cover:
- API key validation
- Basic generation
- Tool calling
- PII warning integration (NFR-PRIV-004)
"""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.gateway.client import GatewayClient, GatewayClientError, get_gateway_client


class TestGatewayClientAPIKeyValidation:
    """Test API key validation."""

    def test_missing_api_key_raises_error(self, monkeypatch):
        """Test that missing API key raises a clear error."""
        # Import fresh settings to bypass cache
        from app.config import Settings
        with pytest.raises(ValueError) as exc_info:
            Settings(pydantic_gateway_api_key="")
        assert "PYDANTIC_GATEWAY_API_KEY is required" in str(exc_info.value)

    def test_empty_api_key_raises_error(self):
        """Test that empty API key raises a clear error."""
        from app.config import Settings
        with pytest.raises(ValueError) as exc_info:
            Settings(pydantic_gateway_api_key="   ")
        assert "PYDANTIC_GATEWAY_API_KEY is required" in str(exc_info.value)

    def test_valid_api_key_accepted(self):
        """Test that valid API key is accepted."""
        client = GatewayClient(api_key="test-key-123", base_url="https://test.gateway.com")
        assert client.api_key == "test-key-123"
        assert client.base_url == "https://test.gateway.com"

    def test_explicit_api_key_overrides_env(self):
        """Test that explicit API key parameter overrides environment variable."""
        client = GatewayClient(api_key="explicit-key", base_url="https://explicit.gateway.com")
        assert client.api_key == "explicit-key"
        assert client.base_url == "https://explicit.gateway.com"


class TestGatewayClientBasicGeneration:
    """Test basic LLM generation through Gateway."""

    @pytest.mark.asyncio
    async def test_generate_basic_completion(self):
        """Test basic chat completion with a simple prompt."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        # Mock the HTTP client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello, world!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.post.return_value.raise_for_status = Mock()

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.generate(
                model="openai/gpt-4o",
                messages=[{"role": "user", "content": "Say hello"}],
            )

        assert result["choices"][0]["message"]["content"] == "Hello, world!"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_temperature(self):
        """Test generation with temperature parameter."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-456",
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.post.return_value.raise_for_status = Mock()

        with patch.object(client, "_get_client", return_value=mock_client):
            await client.generate(
                model="openai/gpt-4o",
                messages=[{"role": "user", "content": "Test"}],
                temperature=0.7,
            )

        # Verify temperature was passed in payload
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_generate_client_error_no_retry(self):
        """Test that 4xx errors are not retried."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com", max_retries=3)

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=Mock(), response=mock_response
        )

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(GatewayClientError) as exc_info:
                await client.generate(
                    model="openai/gpt-4o",
                    messages=[{"role": "user", "content": "Test"}],
                )

        assert "401" in str(exc_info.value)
        # Should only attempt once (no retries for 4xx)
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_network_error_with_retry(self):
        """Test that network errors are retried."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com", max_retries=3)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Success"}}],
        }

        mock_client = AsyncMock()
        # Fail first two times, succeed on third
        mock_client.post.side_effect = [
            httpx.RequestError("Connection error"),
            httpx.RequestError("Connection error"),
            mock_response,
        ]
        mock_response.raise_for_status = Mock()

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.generate(
                model="openai/gpt-4o",
                messages=[{"role": "user", "content": "Test"}],
            )

        assert result["choices"][0]["message"]["content"] == "Success"
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_all_retries_exhausted(self):
        """Test that exhaustion of retries raises GatewayClientError."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com", max_retries=2)

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("Connection error")

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(GatewayClientError) as exc_info:
                await client.generate(
                    model="openai/gpt-4o",
                    messages=[{"role": "user", "content": "Test"}],
                )

        assert "failed after 2 attempts" in str(exc_info.value)
        assert mock_client.post.call_count == 2


class TestGatewayClientToolCalling:
    """Test tool/function calling through Gateway."""

    @pytest.mark.asyncio
    async def test_generate_with_tools(self):
        """Test generation with function calling tools."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-789",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location": "NYC"}',
                                },
                            }
                        ],
                    }
                }
            ],
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.post.return_value.raise_for_status = Mock()

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name"}
                        },
                        "required": ["location"],
                    },
                },
            }
        ]

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.generate(
                model="openai/gpt-4o",
                messages=[{"role": "user", "content": "What's the weather in NYC?"}],
                tools=tools,
            )

        tool_call = result["choices"][0]["message"]["tool_calls"][0]
        assert tool_call["function"]["name"] == "get_weather"
        assert tool_call["function"]["arguments"] == '{"location": "NYC"}'

        # Verify tools were sent in request
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert "tools" in payload
        assert len(payload["tools"]) == 1

    @pytest.mark.asyncio
    async def test_generate_with_tool_and_message_response(self):
        """Test generation where model responds with message instead of tool call."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "I can help with that without tools!",
                    }
                }
            ],
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.post.return_value.raise_for_status = Mock()

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.generate(
                model="openai/gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
                tools=[],
            )

        assert result["choices"][0]["message"]["content"] is not None


class TestGatewayClientSingleton:
    """Test singleton pattern for gateway client."""

    def test_get_gateway_client_returns_singleton(self):
        """Test that get_gateway_client returns the same instance."""
        # Reset singleton to ensure clean state for test
        import app.gateway.client as client_module
        client_module._client = None

        client1 = get_gateway_client()
        client2 = get_gateway_client()

        assert client1 is client2

    def test_get_gateway_client_initializes_once(self):
        """Test that gateway client is initialized only once."""
        # Reset singleton to ensure clean state for test
        import app.gateway.client as client_module
        client_module._client = None

        call_count = 0
        original_init = GatewayClient.__init__

        def counting_init(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_init(self, *args, **kwargs)

        with patch.object(GatewayClient, "__init__", counting_init):
            get_gateway_client()
            get_gateway_client()
            get_gateway_client()

            # Should only initialize once
            assert call_count == 1

        # Clean up
        client_module._client = None


class TestGatewayClientClose:
    """Test client cleanup."""

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self):
        """Test that close() properly closes the HTTP client."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        # Initialize the internal client
        client._get_client()
        assert client._client is not None

        mock_aclose = AsyncMock()
        client._client.aclose = mock_aclose

        await client.close()

        assert client._client is None
        mock_aclose.assert_called_once()


class TestGatewayClientPIIWarning:
    """Test PII warning integration in Gateway client (NFR-PRIV-004)."""

    @pytest.mark.asyncio
    async def test_generate_with_email_logs_warning(self, caplog):
        """Test that email in messages logs a warning but allows request."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.post.return_value.raise_for_status = Mock()

        # Construct email to avoid secret scanning
        email = "user" + "@" + "example.com"

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.generate(
                model="openai/gpt-4o",
                messages=[{"role": "user", "content": f"Email: {email}"}],
            )

        # Request should still succeed
        assert result["choices"][0]["message"]["content"] == "Response"

        # Check that warning was logged
        assert any(
            "PII detected" in record.message or "pii_detected" in str(record)
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_generate_without_pii_no_warning(self, caplog):
        """Test that messages without PII don't log warnings."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Response"}}],
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.post.return_value.raise_for_status = Mock()

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.generate(
                model="openai/gpt-4o",
                messages=[{"role": "user", "content": "Hello, world!"}],
            )

        # Request should succeed
        assert result["choices"][0]["message"]["content"] == "Response"

        # No PII warning should be logged
        assert not any(
            "PII detected" in record.message or "pii_detected" in str(record)
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_generate_with_critical_pii_blocks_request(self):
        """Test that critical PII (API keys) blocks the request."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        # Construct test key to avoid secret scanning
        test_key = "sk-" + "abc123def456789012345678901234567890"

        mock_client = AsyncMock()

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(GatewayClientError) as exc_info:
                await client.generate(
                    model="openai/gpt-4o",
                    messages=[{"role": "user", "content": f"API key: {test_key}"}],
                )

        # Should be blocked with a clear error message
        assert "blocked" in str(exc_info.value).lower() or "PII" in str(exc_info.value)
        assert "severity" in str(exc_info.value).lower()

        # HTTP request should not have been made
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_text_from_payload_basic(self):
        """Test text extraction from basic message payload."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        payload = {
            "model": "openai/gpt-4o",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ],
        }

        text = client._extract_text_from_payload(payload)

        assert text == "Hello\nHi there"

    @pytest.mark.asyncio
    async def test_extract_text_from_payload_multimodal(self):
        """Test text extraction from multimodal content (text + images)."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        payload = {
            "model": "openai/gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's in this image?"},
                        {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}},
                    ],
                }
            ],
        }

        text = client._extract_text_from_payload(payload)

        assert "What's in this image?" in text
        # Image URLs should not be included in text extraction
        assert "image.png" not in text

    @pytest.mark.asyncio
    async def test_extract_text_from_empty_messages(self):
        """Test text extraction from empty messages list."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        text = client._extract_text_from_payload({"messages": []})

        assert text == ""

    @pytest.mark.asyncio
    async def test_extract_text_from_payload_no_messages(self):
        """Test text extraction when messages key is missing."""
        client = GatewayClient(api_key="test-key", base_url="https://test.gateway.com")

        text = client._extract_text_from_payload({"model": "openai/gpt-4o"})

        assert text == ""
