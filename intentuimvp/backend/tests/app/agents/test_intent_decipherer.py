"""Tests for IntentDeciphererAgent."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.base import BaseAgent
from app.agents.intent_decipherer import IntentDeciphererAgent
from app.context.models import AssumptionCategory
from app.gateway.client import GatewayClient, GatewayClientError


def build_gateway_response(payload: dict) -> dict:
    """Build a Gateway response payload for structured output."""
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


class TestIntentDeciphererAgent:
    """Tests for IntentDeciphererAgent behavior."""

    @pytest.mark.asyncio
    async def test_decipher_success_uses_gateway(self):
        """Test deciphering success via Gateway."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value=build_gateway_response(
                {
                    "primary_intent": {
                        "name": "research",
                        "confidence": 0.92,
                        "description": "Find sources and summarize",
                    },
                    "should_auto_execute": True,
                    "reasoning": "High confidence and no risky assumptions.",
                }
            )
        )

        agent = IntentDeciphererAgent(
            gateway=mock_gateway,
            model="test/model",
            temperature=0.2,
        )
        result = await agent.decipher("Research the impact of AI on education.")

        assert result.primary_intent.name == "research"
        assert result.primary_intent.confidence == 0.92
        assert result.should_auto_execute is True

        mock_gateway.generate.assert_called_once()
        call_kwargs = mock_gateway.generate.call_args.kwargs
        assert call_kwargs["model"] == "test/model"
        assert call_kwargs["temperature"] == 0.2
        messages = call_kwargs["messages"]
        assert any(m["role"] == "system" for m in messages)
        assert any(m["role"] == "user" for m in messages)

    @pytest.mark.asyncio
    async def test_decipher_gateway_failure_returns_fallback(self):
        """Test Gateway failure yields fallback result."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(side_effect=GatewayClientError("Gateway failed"))

        agent = IntentDeciphererAgent(gateway=mock_gateway)
        result = await agent.decipher("Analyze quarterly revenue.")

        assert result.primary_intent.name == "chat"
        assert result.primary_intent.confidence == 0.5
        assert result.should_auto_execute is False
        assert "Gateway failed" in result.reasoning

    @pytest.mark.asyncio
    async def test_decipher_invalid_gateway_format_returns_fallback(self):
        """Test invalid Gateway response format triggers fallback."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(return_value={"invalid": "format"})

        agent = IntentDeciphererAgent(gateway=mock_gateway)
        result = await agent.decipher("Summarize the meeting notes.")

        assert result.primary_intent.name == "chat"
        assert result.should_auto_execute is False

    @pytest.mark.asyncio
    async def test_run_requires_text(self):
        """Test run validates required text input."""
        agent = IntentDeciphererAgent(gateway=MagicMock(spec=GatewayClient))

        with pytest.raises(ValueError, match="text"):
            await agent.run({})

    @pytest.mark.asyncio
    async def test_run_returns_dict(self):
        """Test run returns serialized result dict."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value=build_gateway_response(
                {
                    "primary_intent": {
                        "name": "create",
                        "confidence": 0.88,
                        "description": "Build a new dashboard",
                    },
                    "should_auto_execute": True,
                    "reasoning": "Clear intent with sufficient parameters.",
                }
            )
        )

        agent = IntentDeciphererAgent(gateway=mock_gateway)
        result = await agent.run({"text": "Create a dashboard for sales KPIs."})

        assert isinstance(result, dict)
        assert result["primary_intent"]["name"] == "create"
        assert result["should_auto_execute"] is True

    def test_create_assumption_from_string_category(self):
        """Test creating assumptions from string categories."""
        agent = IntentDeciphererAgent(gateway=MagicMock(spec=GatewayClient))
        assumption = agent.create_assumption(
            text="User wants the latest dataset.",
            confidence=0.72,
            category="context",
            explanation="User referenced latest metrics.",
        )

        assert assumption.category == AssumptionCategory.CONTEXT.value
        assert assumption.text == "User wants the latest dataset."


class TestGatewayOnlyEnforcement:
    """Tests to verify Gateway-only enforcement for the decipherer."""

    def test_intent_decipherer_extends_base_agent(self):
        """Verify IntentDeciphererAgent extends BaseAgent."""
        assert issubclass(IntentDeciphererAgent, BaseAgent)

    def test_no_direct_provider_imports_in_intent_decipherer(self):
        """Verify IntentDeciphererAgent does not import provider SDKs directly."""
        import inspect

        import app.agents.intent_decipherer as decipher_module

        source = inspect.getsource(decipher_module)

        assert "import openai" not in source.lower()
        assert "import anthropic" not in source.lower()
        assert "from openai" not in source.lower()
        assert "from anthropic" not in source.lower()
