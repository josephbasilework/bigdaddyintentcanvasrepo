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

    @pytest.mark.asyncio
    async def test_progress_callback_called_during_research(self):
        """Test that progress callback is called during research."""
        mock_gateway = MagicMock(spec=GatewayClient)
        mock_gateway.generate = AsyncMock(
            side_effect=[
                build_gateway_response({"sub_queries": ["Query 1", "Query 2"]}),
                build_gateway_response(
                    {
                        "summary": "Summary text",
                        "key_points": ["Point 1"],
                        "detailed_findings": "Detailed findings",
                        "confidence": 0.8,
                        "limitations": [],
                        "follow_up_questions": [],
                    }
                ),
            ]
        )

        # Mock the tool manager to return web search results
        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool = AsyncMock(
            return_value=MagicMock(
                success=True,
                output={
                    "results": [
                        {
                            "url": "https://example.com/1",
                            "title": "Source 1",
                            "snippet": "Snippet 1",
                        },
                        {
                            "url": "https://example.com/2",
                            "title": "Source 2",
                            "snippet": "Snippet 2",
                        },
                    ]
                },
            )
        )

        agent = ResearchAgent(gateway=mock_gateway)
        agent.tool_manager = mock_tool_manager

        # Track callback invocations
        progress_calls: list[dict] = []

        async def mock_callback(
            step_number: int,
            steps_total: int,
            current_step: str,
            data: dict | None = None,
        ) -> None:
            progress_calls.append(
                {
                    "step_number": step_number,
                    "steps_total": steps_total,
                    "current_step": current_step,
                    "data": data,
                }
            )

        # Run research with progress callback
        report = await agent.research(
            "Test query", max_steps=2, progress_callback=mock_callback
        )

        # Verify callback was called multiple times
        assert len(progress_calls) > 0
        assert report.summary == "Summary text"

        # Verify decomposition callback
        decompose_call = next(
            (c for c in progress_calls if "Decomposed query" in c["current_step"]), None
        )
        assert decompose_call is not None
        assert decompose_call["data"] is not None
        assert "sub_queries" in decompose_call["data"]

        # Verify search step callbacks
        search_calls = [c for c in progress_calls if "Searching:" in c["current_step"]]
        assert len(search_calls) == 2  # One for each sub-query

        # Verify sources found callbacks
        source_calls = [
            c for c in progress_calls if "sources" in (c.get("data") or {})
        ]
        assert len(source_calls) == 2  # One for each sub-query with results

        # Verify synthesis callback
        synthesis_call = next(
            (c for c in progress_calls if "Synthesizing" in c["current_step"]), None
        )
        assert synthesis_call is not None

    @pytest.mark.asyncio
    async def test_research_without_progress_callback(self):
        """Test that research works without progress callback (backward compatibility)."""
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
                        "limitations": [],
                        "follow_up_questions": [],
                    }
                ),
            ]
        )

        # Mock the tool manager
        mock_tool_manager = MagicMock()
        mock_tool_manager.execute_tool = AsyncMock(
            return_value=MagicMock(
                success=True,
                output={
                    "results": [
                        {
                            "url": "https://example.com/1",
                            "title": "Source 1",
                            "snippet": "Snippet 1",
                        }
                    ]
                },
            )
        )

        agent = ResearchAgent(gateway=mock_gateway)
        agent.tool_manager = mock_tool_manager

        # Run research without progress callback (should not crash)
        report = await agent.research("Test query", max_steps=1)

        assert report.summary == "Summary text"
        assert report.key_points == ["Point 1"]
