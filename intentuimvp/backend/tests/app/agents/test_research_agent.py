"""Tests for ResearchAgent."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.research_agent import ResearchAgent
from app.gateway.client import GatewayClient, GatewayClientError


def build_gateway_response(payload: dict) -> dict:
    """Build a Gateway response payload for structured output."""
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


class TestResearchAgent:
    """Tests for ResearchAgent behavior."""

    @pytest.mark.asyncio
    async def test_research_success_uses_gateway(self):
        """Test research success via Gateway."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            side_effect=[
                build_gateway_response({"sub_queries": ["Test query"]}),
                build_gateway_response(
                    {
                        "summary": "Summary text",
                        "key_points": ["Point 1"],
                        "detailed_findings": "Detailed findings",
                        "confidence": 0.8,
                        "limitations": ["Limited data"],
                        "follow_up_questions": ["Next question?"],
                    }
                ),
            ]
        )

        agent = ResearchAgent(gateway=mock_gateway, model="test/model", temperature=0.2)
        report = await agent.research("Test query", max_steps=1)

        assert report.summary == "Summary text"
        assert report.key_points == ["Point 1"]
        assert report.confidence == 0.8
        assert report.limitations == ["Limited data"]
        assert report.follow_up_questions == ["Next question?"]

        assert mock_gateway.generate.call_count == 2
        for call in mock_gateway.generate.call_args_list:
            call_kwargs = call.kwargs
            assert call_kwargs["model"] == "test/model"
            assert call_kwargs["temperature"] == 0.2
            messages = call_kwargs["messages"]
            assert any(message["role"] == "system" for message in messages)
            assert any(message["role"] == "user" for message in messages)

    @pytest.mark.asyncio
    async def test_decompose_query_fallback_on_gateway_error(self):
        """Test gateway failure falls back to original query."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            side_effect=GatewayClientError("Gateway failed")
        )

        agent = ResearchAgent(gateway=mock_gateway)
        sub_queries = await agent._decompose_query("Fallback query")

        assert sub_queries == ["Fallback query"]

    @pytest.mark.asyncio
    async def test_synthesize_report_fallback_on_invalid_json(self):
        """Test synthesis fallback when Gateway returns invalid JSON."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            return_value={"choices": [{"message": {"content": "not json"}}]}
        )

        agent = ResearchAgent(gateway=mock_gateway)
        report = await agent._synthesize_report("Test topic", steps=[], sources=[])

        assert report.summary.startswith("Research conducted on Test topic.")
        assert report.limitations == ["Synthesis failed, using raw findings"]
