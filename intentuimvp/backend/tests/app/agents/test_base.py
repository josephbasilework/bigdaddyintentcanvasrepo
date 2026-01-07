"""Tests for BaseAgent class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError
from pydantic_core import InitErrorDetails

from app.agents.base import AgentError, BaseAgent
from app.gateway.client import GatewayClient, GatewayClientError


class DummyAgent(BaseAgent):
    """Minimal test agent implementation."""

    async def run(self, input_data: dict):
        """Echo the input."""
        return {"echo": input_data.get("prompt", "")}


class EchoResponseModel:
    """Test Pydantic model for structured output."""

    REQUIRED_FIELDS = {"original", "echo", "timestamp"}

    def __init__(self, original: str, echo: str, timestamp: str):
        self.original = original
        self.echo = echo
        self.timestamp = timestamp

    @classmethod
    def model_validate(cls, data: dict):
        """Validate model from dict."""
        missing = cls.REQUIRED_FIELDS - data.keys()
        if missing:
            errors = [
                InitErrorDetails(
                    type="missing",
                    loc=tuple(missing),
                    input=data,
                )
            ]
            raise ValidationError.from_exception_data(cls.__name__, errors)
        return cls(**data)


class TestBaseAgent:
    """Tests for BaseAgent base class."""

    def test_init_with_gateway(self):
        """Test initialization with explicit Gateway client."""
        mock_gateway = MagicMock(spec=GatewayClient)
        agent = DummyAgent(gateway=mock_gateway, model="custom/model", temperature=0.5)

        assert agent.gateway is mock_gateway
        assert agent.model == "custom/model"
        assert agent.temperature == 0.5

    @patch("app.gateway.client.get_gateway_client")
    def test_init_without_gateway(self, mock_get_client):
        """Test initialization uses singleton Gateway client."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_get_client.return_value = mock_gateway

        agent = DummyAgent()

        assert agent.gateway is mock_gateway
        mock_get_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_abstractmethod(self):
        """Test that run() must be implemented by subclasses."""
        # Can't instantiate BaseAgent directly
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore

    @pytest.mark.asyncio
    async def test_subclass_can_implement_run(self):
        """Test that subclass can override run() method."""
        agent = DummyAgent()
        result = await agent.run({"prompt": "hello"})

        assert result == {"echo": "hello"}

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful generation via Gateway."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={"choices": [{"message": {"content": "test response"}}]}
        )

        agent = DummyAgent(gateway=mock_gateway)
        messages = [{"role": "user", "content": "test"}]
        response = await agent.generate(messages)

        assert response == {"choices": [{"message": {"content": "test response"}}]}
        mock_gateway.generate.assert_called_once_with(
            model="openai/gpt-4o",
            messages=messages,
            temperature=0.7,
        )

    @pytest.mark.asyncio
    async def test_generate_with_overrides(self):
        """Test generation with model and temperature overrides."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(return_value={})

        agent = DummyAgent(gateway=mock_gateway)
        await agent.generate(
            [],
            model="custom/model",
            temperature=0.3,
            max_tokens=100,
        )

        mock_gateway.generate.assert_called_once_with(
            model="custom/model",
            temperature=0.3,
            max_tokens=100,
            messages=[],
        )

    @pytest.mark.asyncio
    async def test_generate_gateway_error_raises_agent_error(self):
        """Test that Gateway errors are wrapped in AgentError."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            side_effect=GatewayClientError("Gateway failed")
        )

        agent = DummyAgent(gateway=mock_gateway)

        with pytest.raises(AgentError) as exc_info:
            await agent.generate([])

        assert "Agent execution failed" in str(exc_info.value)
        assert "Gateway failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_structured_success(self):
        """Test successful structured generation."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={
                "choices": [
                    {"message": {"content": '{"original": "hi", "echo": "hi", "timestamp": "2024-01-01T00:00:00"}'}}
                ]
            }
        )

        agent = DummyAgent(gateway=mock_gateway)
        result = await agent.generate_structured(
            [{"role": "user", "content": "hi"}],
            response_model=EchoResponseModel,
        )

        assert result.original == "hi"
        assert result.echo == "hi"
        assert result.timestamp == "2024-01-01T00:00:00"

    @pytest.mark.asyncio
    async def test_generate_structured_invalid_response_format(self):
        """Test structured generation with invalid response format."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(return_value={"invalid": "format"})

        agent = DummyAgent(gateway=mock_gateway)

        with pytest.raises(AgentError) as exc_info:
            await agent.generate_structured([], response_model=EchoResponseModel)

        assert "Invalid Gateway response format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_structured_invalid_json(self):
        """Test structured generation with invalid JSON in response."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={"choices": [{"message": {"content": "not json"}}]}
        )

        agent = DummyAgent(gateway=mock_gateway)

        with pytest.raises(AgentError) as exc_info:
            await agent.generate_structured([], response_model=EchoResponseModel)

        assert "Structured response validation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_structured_validation_error(self):
        """Test structured generation with Pydantic validation error."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={
                "choices": [{"message": {"content": '{"wrong": "fields"}'}}]
            }
        )

        agent = DummyAgent(gateway=mock_gateway)

        with pytest.raises(AgentError) as exc_info:
            await agent.generate_structured([], response_model=EchoResponseModel)

        assert "Structured response validation failed" in str(exc_info.value)


class TestGatewayOnlyEnforcement:
    """Tests to verify Gateway-only enforcement."""

    def test_no_direct_provider_imports_in_base(self):
        """Verify BaseAgent does not import provider SDKs directly."""
        import inspect

        import app.agents.base as base_module

        source = inspect.getsource(base_module)

        # Ensure no direct imports of OpenAI, Anthropic, etc.
        assert "import openai" not in source.lower()
        assert "import anthropic" not in source.lower()
        assert "from openai" not in source.lower()
        assert "from anthropic" not in source.lower()

    def test_gateway_only_pattern_documented(self):
        """Verify Gateway-only pattern is documented in BaseAgent."""
        assert BaseAgent.__doc__ is not None
        assert "Gateway" in BaseAgent.__doc__ or "gateway" in BaseAgent.__doc__
