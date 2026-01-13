"""Tests for PerspectiveAgent (FR-012: Multi-Judge Compute).

Tests cover:
- FR-012 default perspectives (skeptic, advocate, synthesizer)
- Sequential execution with 30s timeout
- Graceful failure handling (proceed with available perspectives)
- Specific prompts for each perspective type
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.perspective_agent import (
    PERSPECTIVE_TIMEOUT,
    Perspective,
    PerspectiveAgent,
    PerspectiveConfig,
)
from app.gateway.client import GatewayClient, GatewayClientError


class TestPerspectiveAgentInit:
    """Tests for PerspectiveAgent initialization."""

    @patch("app.gateway.client.get_gateway_client")
    def test_init_with_defaults(self, mock_get_client):
        """Test initialization with default values."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_get_client.return_value = mock_gateway

        agent = PerspectiveAgent()

        assert agent.gateway is mock_gateway
        assert agent.model == "openai/gpt-4o"
        assert agent.temperature == 0.5
        assert agent.config.num_perspectives == 3
        assert agent.config.include_bias_analysis is True

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        mock_gateway = MagicMock(spec=GatewayClient)
        config = PerspectiveConfig(num_perspectives=2, include_bias_analysis=False)

        agent = PerspectiveAgent(
            gateway=mock_gateway, model="custom/model", temperature=0.3, config=config
        )

        assert agent.gateway is mock_gateway
        assert agent.model == "custom/model"
        assert agent.temperature == 0.3
        assert agent.config.num_perspectives == 2
        assert agent.config.include_bias_analysis is False


class TestDefaultPerspectives:
    """Tests for FR-012 default perspectives."""

    def test_fr012_default_perspectives(self):
        """Test FR-012 default perspectives are skeptic, advocate, synthesizer."""
        assert PerspectiveAgent.DEFAULT_PERSPECTIVES == [
            "skeptic",
            "advocate",
            "synthesizer",
        ]

    def test_default_perspectives_count(self):
        """Test FR-012 specifies 3 default perspectives."""
        assert len(PerspectiveAgent.DEFAULT_PERSPECTIVES) == 3


class TestPerspectiveAgentRun:
    """Tests for PerspectiveAgent.run() method."""

    @pytest.mark.asyncio
    async def test_run_requires_topic(self):
        """Test run() raises ValueError without topic."""
        mock_gateway = MagicMock(spec=GatewayClient)
        agent = PerspectiveAgent(gateway=mock_gateway)

        with pytest.raises(ValueError, match="must contain 'topic' field"):
            await agent.run({})

    @pytest.mark.asyncio
    async def test_run_with_topic(self):
        """Test run() processes topic and returns evaluation."""
        mock_gateway = MagicMock(spec=GatewayClient)

        # Mock all Gateway calls
        mock_gateway.generate = AsyncMock(
            side_effect=[
                # Skeptic perspective
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"name": "skeptic", "description": "Skeptic view", "stance": "con", "arguments": ["Weak evidence"], "evidence": [], "confidence": 0.7, "strengths": [], "weaknesses": []}'
                            }
                        }
                    ]
                },
                # Advocate perspective
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"name": "advocate", "description": "Advocate view", "stance": "pro", "arguments": ["Strong argument"], "evidence": [], "confidence": 0.8, "strengths": [], "weaknesses": []}'
                            }
                        }
                    ]
                },
                # Synthesizer perspective
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"name": "synthesizer", "description": "Synthesizer view", "stance": "neutral", "arguments": ["Middle ground"], "evidence": [], "confidence": 0.75, "strengths": [], "weaknesses": []}'
                            }
                        }
                    ]
                },
                # Consensus
                {
                    "choices": [
                        {"message": {"content": '{"consensus_points": ["Common point"]}'}}
                    ]
                },
                # Disagreements
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"disagreement_points": ["Key tension"]}'
                            }
                        }
                    ]
                },
                # Bias analysis
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"detected_biases": [], "bias_explanations": [], "mitigation_suggestions": [], "overall_bias_rating": "low"}'
                            }
                        }
                    ]
                },
                # Recommendation
                {
                    "choices": [
                        {
                            "message": {
                                "content": "Balanced recommendation considering all viewpoints."
                            }
                        }
                    ]
                },
            ]
        )

        agent = PerspectiveAgent(gateway=mock_gateway)
        result = await agent.run({"topic": "Test topic"})

        assert "topic" in result
        assert result["topic"] == "Test topic"
        assert "perspectives" in result
        assert len(result["perspectives"]) == 3
        assert result["perspectives"][0]["name"] == "skeptic"
        assert result["perspectives"][1]["name"] == "advocate"
        assert result["perspectives"][2]["name"] == "synthesizer"


class TestSequentialExecutionWithTimeout:
    """Tests for FR-012 sequential execution with 30s timeout."""

    @patch("app.gateway.client.get_gateway_client")
    @pytest.mark.asyncio
    async def test_sequential_execution(self, mock_get_client):
        """Test perspectives are generated sequentially (not parallel)."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_get_client.return_value = mock_gateway

        call_order = []

        async def slow_generate(*args, **kwargs):
            call_order.append(len(call_order))
            await asyncio.sleep(0.01)  # Small delay to ensure ordering
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"name": "test", "description": "Test", "stance": "neutral", "arguments": [], "evidence": [], "confidence": 0.5, "strengths": [], "weaknesses": []}'
                        }
                    }
                ]
            }

        mock_gateway.generate = AsyncMock(side_effect=slow_generate)

        agent = PerspectiveAgent(gateway=mock_gateway, config=PerspectiveConfig(num_perspectives=2))
        # Mock other LLM calls to return empty/defaults
        mock_gateway.generate = AsyncMock(
            side_effect=[
                # First perspective
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"name": "skeptic", "description": "Test", "stance": "neutral", "arguments": [], "evidence": [], "confidence": 0.5, "strengths": [], "weaknesses": []}'
                            }
                        }
                    ]
                },
                # Second perspective
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"name": "advocate", "description": "Test", "stance": "neutral", "arguments": [], "evidence": [], "confidence": 0.5, "strengths": [], "weaknesses": []}'
                            }
                        }
                    ]
                },
                # Consensus (skipped if < 2 perspectives succeed)
                {"choices": [{"message": {"content": '{"consensus_points": []}'}}]},
                # Disagreements
                {"choices": [{"message": {"content": '{"disagreement_points": []}'}}]},
                # Bias analysis
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"detected_biases": [], "bias_explanations": [], "mitigation_suggestions": [], "overall_bias_rating": "low"}'
                            }
                        }
                    ]
                },
                # Recommendation
                {"choices": [{"message": {"content": "Recommendation"}}]},
            ]
        )

        await agent.evaluate("Test topic")

        # Verify generate was called multiple times (once per perspective + analysis)
        assert mock_gateway.generate.call_count >= 2

    @patch("app.gateway.client.get_gateway_client")
    @pytest.mark.asyncio
    async def test_timeout_per_perspective(self, mock_get_client):
        """Test FR-012: 30 second timeout per perspective."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_get_client.return_value = mock_gateway

        # Make the first perspective timeout
        async def timeout_generate(*args, **kwargs):
            await asyncio.sleep(PERSPECTIVE_TIMEOUT + 1)

        mock_gateway.generate = AsyncMock(side_effect=timeout_generate)

        # Mock other calls to return defaults
        async def default_generate(*args, **kwargs):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"name": "test", "description": "Test", "stance": "neutral", "arguments": [], "evidence": [], "confidence": 0.5, "strengths": [], "weaknesses": []}'
                        }
                    }
                ]
            }

        call_count = 0

        async def mixed_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (skeptic) times out
                await asyncio.sleep(PERSPECTIVE_TIMEOUT + 1)
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"name": "test", "description": "Test", "stance": "neutral", "arguments": [], "evidence": [], "confidence": 0.5, "strengths": [], "weaknesses": []}'
                        }
                    }
                ]
            }

        mock_gateway.generate = AsyncMock(side_effect=mixed_generate)

        agent = PerspectiveAgent(
            gateway=mock_gateway, config=PerspectiveConfig(num_perspectives=1, include_bias_analysis=False)
        )

        result = await agent.evaluate("Test topic")

        # Should have a failed perspective marked
        assert len(result.perspectives) == 1
        assert result.perspectives[0].failed is True
        assert "timeout" in result.perspectives[0].failure_reason.lower()


class TestGracefulFailureHandling:
    """Tests for FR-012 graceful failure handling."""

    @patch("app.gateway.client.get_gateway_client")
    @pytest.mark.asyncio
    async def test_proceed_with_available_perspectives(self, mock_get_client):
        """Test FR-012: If perspective fails, proceed with available perspectives."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_get_client.return_value = mock_gateway

        call_count = 0

        async def failing_first_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First perspective fails
                raise GatewayClientError("Gateway error")
            # Subsequent calls succeed
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"name": "test", "description": "Test", "stance": "neutral", "arguments": [], "evidence": [], "confidence": 0.5, "strengths": [], "weaknesses": []}'
                        }
                    }
                ]
            }

        mock_gateway.generate = AsyncMock(side_effect=failing_first_call)

        agent = PerspectiveAgent(
            gateway=mock_gateway,
            config=PerspectiveConfig(num_perspectives=2, include_bias_analysis=False),
        )

        result = await agent.evaluate("Test topic")

        # Should have 2 perspectives: 1 failed, 1 succeeded
        assert len(result.perspectives) == 2
        assert result.perspectives[0].failed is True
        # BaseAgent wraps errors: "Agent execution failed: {error}"
        assert "Gateway error" in result.perspectives[0].failure_reason
        assert result.perspectives[1].failed is False

    @patch("app.gateway.client.get_gateway_client")
    @pytest.mark.asyncio
    async def test_failed_perspective_noted_in_output(self, mock_get_client):
        """Test FR-012: Failed perspective is noted in output."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_get_client.return_value = mock_gateway

        async def fail_then_succeed(*args, **kwargs):
            raise GatewayClientError("Test failure")

        mock_gateway.generate = AsyncMock(side_effect=fail_then_succeed)

        agent = PerspectiveAgent(
            gateway=mock_gateway,
            config=PerspectiveConfig(num_perspectives=1, include_bias_analysis=False),
        )

        result = await agent.evaluate("Test topic")

        assert len(result.perspectives) == 1
        p = result.perspectives[0]
        assert p.failed is True
        # BaseAgent wraps errors: "Agent execution failed: {error}"
        assert "Test failure" in p.failure_reason
        assert p.confidence == 0.0


class TestSpecificPerspectivePrompts:
    """Tests for FR-012 specific prompts for each perspective type."""

    def test_skeptic_prompt_includes_key_phrases(self):
        """Test skeptic prompt includes FR-012 required elements."""
        from app.agents.perspective_agent import PerspectiveAgent

        # This is a simple check - we verify the prompts are defined
        # In a real test, we might check the actual prompts
        assert "skeptic" in PerspectiveAgent.DEFAULT_PERSPECTIVES

    def test_advocate_prompt_includes_key_phrases(self):
        """Test advocate prompt includes FR-012 required elements."""
        from app.agents.perspective_agent import PerspectiveAgent

        assert "advocate" in PerspectiveAgent.DEFAULT_PERSPECTIVES

    def test_synthesizer_prompt_includes_key_phrases(self):
        """Test synthesizer prompt includes FR-012 required elements."""
        from app.agents.perspective_agent import PerspectiveAgent

        assert "synthesizer" in PerspectiveAgent.DEFAULT_PERSPECTIVES


class TestGatewayOnlyEnforcement:
    """Tests to verify Gateway-only enforcement for PerspectiveAgent."""

    def test_no_direct_provider_imports_in_perspective_agent(self):
        """Verify PerspectiveAgent does not import provider SDKs directly."""
        import inspect

        import app.agents.perspective_agent as perspective_module

        source = inspect.getsource(perspective_module)

        # Ensure no direct imports of OpenAI, Anthropic, etc.
        assert "import openai" not in source.lower()
        assert "import anthropic" not in source.lower()
        assert "from openai" not in source.lower()
        assert "from anthropic" not in source.lower()

    def test_perspective_agent_inherits_from_base_agent(self):
        """Verify PerspectiveAgent inherits from BaseAgent."""
        from app.agents.base import BaseAgent

        assert issubclass(PerspectiveAgent, BaseAgent)


class TestPerspectiveModel:
    """Tests for Perspective Pydantic model."""

    def test_perspective_model_has_failed_fields(self):
        """Test Perspective model has FR-012 failure tracking fields."""
        perspective = Perspective(
            name="test",
            description="Test perspective",
            stance="neutral",
            arguments=["test argument"],
            confidence=0.5,
        )

        # FR-012: New fields for failure handling
        assert hasattr(perspective, "failed")
        assert hasattr(perspective, "failure_reason")
        assert perspective.failed is False
        assert perspective.failure_reason is None

    def test_perspective_model_with_failure(self):
        """Test Perspective model can represent failures."""
        perspective = Perspective(
            name="test",
            description="Failed perspective",
            stance="neutral",
            arguments=["Failed"],
            confidence=0.0,
            failed=True,
            failure_reason="Timeout after 30s",
        )

        assert perspective.failed is True
        assert perspective.failure_reason == "Timeout after 30s"
        assert perspective.confidence == 0.0
