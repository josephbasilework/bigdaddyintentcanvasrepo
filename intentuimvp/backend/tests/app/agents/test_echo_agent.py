"""Tests for EchoAgent class."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.echo_agent import EchoAgent, EchoResponse
from app.gateway.client import GatewayClient, GatewayClientError


class TestEchoAgent:
    """Tests for EchoAgent."""

    @pytest.mark.asyncio
    async def test_run_success_with_gateway(self):
        """Test successful echo via Gateway."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": '{"original": "hello", "echo": "hello", "timestamp": "2024-01-01T00:00:00"}'
                        }
                    }
                ]
            }
        )

        agent = EchoAgent(gateway=mock_gateway)
        result = await agent.run({"prompt": "hello"})

        assert result["original"] == "hello"
        assert result["echo"] == "hello"
        assert result["timestamp"] == "2024-01-01T00:00:00"

    @pytest.mark.asyncio
    async def test_run_gateway_failure_fallback(self):
        """Test that Gateway failure triggers fallback response."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(side_effect=GatewayClientError("Gateway failed"))

        agent = EchoAgent(gateway=mock_gateway)
        result = await agent.run({"prompt": "test input"})

        # Fallback should return original input with [fallback] prefix
        assert result["original"] == "test input"
        assert result["echo"] == "[fallback] test input"
        assert "timestamp" in result
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(result["timestamp"])

    @pytest.mark.asyncio
    async def test_run_with_empty_prompt(self):
        """Test agent handles empty prompt gracefully."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": '{"original": "", "echo": "", "timestamp": "2024-01-01T00:00:00"}'
                        }
                    }
                ]
            }
        )

        agent = EchoAgent(gateway=mock_gateway)
        result = await agent.run({"prompt": ""})

        assert result["original"] == ""
        assert result["echo"] == ""

    @pytest.mark.asyncio
    async def test_run_with_non_string_prompt_converts_to_string(self):
        """Test agent converts non-string prompts to strings."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": '{"original": "42", "echo": "42", "timestamp": "2024-01-01T00:00:00"}'
                        }
                    }
                ]
            }
        )

        agent = EchoAgent(gateway=mock_gateway)
        result = await agent.run({"prompt": 42})

        assert result["original"] == "42"
        assert result["echo"] == "42"

    @pytest.mark.asyncio
    async def test_run_with_missing_prompt_uses_empty_string(self):
        """Test agent handles missing prompt key gracefully."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": '{"original": "", "echo": "", "timestamp": "2024-01-01T00:00:00"}'
                        }
                    }
                ]
            }
        )

        agent = EchoAgent(gateway=mock_gateway)
        result = await agent.run({})

        assert result["original"] == ""
        assert result["echo"] == ""

    @pytest.mark.asyncio
    async def test_run_gateway_invalid_response_format_fallback(self):
        """Test that invalid Gateway response format triggers fallback."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(return_value={"invalid": "format"})

        agent = EchoAgent(gateway=mock_gateway)
        result = await agent.run({"prompt": "test"})

        assert result["original"] == "test"
        assert result["echo"] == "[fallback] test"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_run_gateway_invalid_json_fallback(self):
        """Test that invalid JSON in Gateway response triggers fallback."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={"choices": [{"message": {"content": "not json"}}]}
        )

        agent = EchoAgent(gateway=mock_gateway)
        result = await agent.run({"prompt": "test"})

        assert result["original"] == "test"
        assert result["echo"] == "[fallback] test"

    @pytest.mark.asyncio
    async def test_run_gateway_validation_error_fallback(self):
        """Test that Pydantic validation error triggers fallback."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={"choices": [{"message": {"content": '{"wrong": "fields"}'}}]}
        )

        agent = EchoAgent(gateway=mock_gateway)
        result = await agent.run({"prompt": "test"})

        assert result["original"] == "test"
        assert result["echo"] == "[fallback] test"

    @pytest.mark.asyncio
    async def test_uses_generate_structured_method(self):
        """Test that agent uses generate_structured for structured output."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": '{"original": "hi", "echo": "hi", "timestamp": "2024-01-01T00:00:00"}'
                        }
                    }
                ]
            }
        )

        agent = EchoAgent(gateway=mock_gateway)
        await agent.run({"prompt": "hi"})

        # Verify Gateway was called
        mock_gateway.generate.assert_called_once()
        call_args = mock_gateway.generate.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]

        # Verify system prompt includes echo instructions
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "echo agent" in system_msg["content"].lower()
        assert "json" in system_msg["content"].lower()


class TestEchoResponse:
    """Tests for EchoResponse Pydantic model."""

    def test_valid_echo_response(self):
        """Test creating a valid EchoResponse."""
        response = EchoResponse(
            original="test", echo="test", timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        assert response.original == "test"
        assert response.echo == "test"
        assert response.timestamp == datetime(2024, 1, 1, 12, 0, 0)

    def test_echo_response_serialization(self):
        """Test EchoResponse model serialization."""
        response = EchoResponse(
            original="hello", echo="hello", timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )

        data = response.model_dump()

        assert data["original"] == "hello"
        assert data["echo"] == "hello"
        assert data["timestamp"] == datetime(2024, 1, 1, 12, 0, 0)

    def test_echo_response_from_dict(self):
        """Test creating EchoResponse from dict."""
        data = {
            "original": "world",
            "echo": "world",
            "timestamp": "2024-01-01T12:00:00",
        }

        response = EchoResponse.model_validate(data)

        assert response.original == "world"
        assert response.echo == "world"

    def test_echo_response_missing_required_field_raises_error(self):
        """Test that missing required fields raise validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EchoResponse.model_validate({"original": "test", "echo": "test"})


class TestGatewayOnlyEnforcement:
    """Tests to verify EchoAgent follows Gateway-only pattern."""

    def test_no_direct_provider_imports_in_echo_agent(self):
        """Verify EchoAgent does not import provider SDKs directly."""
        import inspect

        import app.agents.echo_agent as echo_module

        source = inspect.getsource(echo_module)

        # Ensure no direct imports of OpenAI, Anthropic, etc.
        assert "import openai" not in source.lower()
        assert "import anthropic" not in source.lower()
        assert "from openai" not in source.lower()
        assert "from anthropic" not in source.lower()

    def test_echo_agent_extends_base_agent(self):
        """Verify EchoAgent extends BaseAgent."""
        from app.agents.base import BaseAgent

        assert issubclass(EchoAgent, BaseAgent)
