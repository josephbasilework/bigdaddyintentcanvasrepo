"""Tests for job worker functions.

Tests the actual job implementations that process background tasks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.jobs.worker import (
    DEFAULT_PERSPECTIVES,
    PerspectiveAgent,
    deep_research_job,
    export_job,
    perspective_gather_job,
    synthesis_job,
)


class TestPerspectiveAgent:
    """Tests for PerspectiveAgent model."""

    def test_valid_perspective_agent(self) -> None:
        """PerspectiveAgent should validate with correct fields."""
        agent = PerspectiveAgent(
            name="technical",
            system_prompt="You are a technical analyst.",
            temperature=0.5,
        )
        assert agent.name == "technical"
        assert agent.system_prompt == "You are a technical analyst."
        assert agent.temperature == 0.5

    def test_default_temperature(self) -> None:
        """PerspectiveAgent should default temperature to 0.7."""
        agent = PerspectiveAgent(
            name="business",
            system_prompt="You are a business analyst.",
        )
        assert agent.temperature == 0.7

    def test_invalid_temperature_raises_error(self) -> None:
        """PerspectiveAgent should reject temperatures outside 0-1 range."""
        with pytest.raises(ValidationError):
            PerspectiveAgent(
                name="test",
                system_prompt="Test",
                temperature=1.5,
            )


class TestDefaultPerspectives:
    """Tests for DEFAULT_PERSPECTIVES."""

    def test_has_expected_perspectives(self) -> None:
        """DEFAULT_PERSPECTIVES should have expected keys."""
        assert "technical" in DEFAULT_PERSPECTIVES
        assert "business" in DEFAULT_PERSPECTIVES
        assert "ethical" in DEFAULT_PERSPECTIVES
        assert "user" in DEFAULT_PERSPECTIVES

    def test_all_perspectives_valid(self) -> None:
        """All perspectives in DEFAULT_PERSPECTIVES should be valid PerspectiveAgent instances."""
        for name, agent in DEFAULT_PERSPECTIVES.items():
            assert isinstance(agent, PerspectiveAgent)
            assert agent.name == name
            assert 0.0 <= agent.temperature <= 1.0
            assert len(agent.system_prompt) > 0


@pytest.mark.asyncio
class TestDeepResearchJob:
    """Tests for deep_research_job function."""

    async def test_deep_research_job_basic(self) -> None:
        """Should execute deep research with valid query."""
        ctx = {"job_id": "test-job-123"}

        # Mock the Gateway client
        with patch("app.jobs.worker.get_gateway_client") as mock_gateway, patch(
            "app.jobs.worker.get_research_agent"
        ) as mock_research_agent:

            # Setup mock gateway
            mock_gateway_instance = MagicMock()
            mock_gateway_instance.generate = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": '{"executive_summary": "Test", "key_insights": [], "recommendations": [], "confidence": 0.8, "confidence_rationale": "Test", "risks": [], "open_questions": []}'
                            }
                        }
                    ]
                }
            )
            mock_gateway.return_value = mock_gateway_instance
            mock_research_agent.return_value = MagicMock()

            # Mock research report
            mock_report = MagicMock()
            mock_report.summary = "Test summary"
            mock_report.key_points = ["Point 1", "Point 2"]
            mock_report.detailed_findings = "Detailed findings"
            mock_report.model_dump.return_value = {
                "summary": "Test summary",
                "key_points": ["Point 1", "Point 2"],
                "detailed_findings": "Detailed findings",
            }
            mock_research_agent.return_value.research = AsyncMock(return_value=mock_report)

            result = await deep_research_job(ctx, query="Test query", depth=2)

            assert result.success is True
            assert result.data is not None
            assert result.data["query"] == "Test query"
            assert result.data["depth"] == 2
            assert "perspectives" in result.data
            assert "synthesis" in result.data

    async def test_deep_research_job_with_depth_1(self) -> None:
        """Should use only 1 perspective when depth is 1."""
        ctx = {"job_id": "test-job-456"}

        with patch("app.jobs.worker.get_gateway_client") as mock_gateway, patch(
            "app.jobs.worker.get_research_agent"
        ) as mock_research_agent:

            mock_gateway_instance = MagicMock()
            mock_gateway_instance.generate = AsyncMock(
                return_value={
                    "choices": [{"message": {"content": '{"executive_summary": "Test", "key_insights": [], "recommendations": [], "confidence": 0.8, "confidence_rationale": "Test", "risks": [], "open_questions": []}'}}]
                }
            )
            mock_gateway.return_value = mock_gateway_instance
            mock_research_agent.return_value = MagicMock()

            mock_report = MagicMock()
            mock_report.summary = "Test"
            mock_report.key_points = []
            mock_report.detailed_findings = "Test"
            mock_report.model_dump.return_value = {"summary": "Test"}
            mock_research_agent.return_value.research = AsyncMock(return_value=mock_report)

            result = await deep_research_job(ctx, query="Test", depth=1)

            assert result.success is True
            # Should only have 1 perspective when depth is 1
            assert result.data is not None
            assert len(result.data["perspectives"]) == 1

    async def test_deep_research_job_handles_error(self) -> None:
        """Should return JobResult with error on exception."""
        ctx = {"job_id": "test-job-error"}

        with patch("app.jobs.worker.get_gateway_client") as mock_gateway:
            mock_gateway.side_effect = Exception("Gateway error")

            result = await deep_research_job(ctx, query="Test", depth=2)

            assert result.success is False
            assert result.error is not None
            assert "Gateway error" in result.error


@pytest.mark.asyncio
class TestPerspectiveGatherJob:
    """Tests for perspective_gather_job function."""

    async def test_perspective_gather_job_basic(self) -> None:
        """Should gather perspectives successfully."""
        ctx = {"job_id": "test-persp-123"}

        with patch("app.jobs.worker.get_gateway_client") as mock_gateway:

            mock_gateway_instance = MagicMock()
            mock_gateway_instance.generate = AsyncMock(
                return_value={
                    "choices": [{"message": {"content": "Analysis from technical perspective"}}]
                }
            )
            mock_gateway.return_value = mock_gateway_instance

            result = await perspective_gather_job(
                ctx, query="Test query", perspectives=["technical", "business"]
            )

            assert result.success is True
            assert result.data is not None
            assert result.data["query"] == "Test query"
            assert len(result.data["perspectives"]) == 2
            assert result.data["perspectives"][0]["name"] == "technical"
            assert result.data["perspectives"][1]["name"] == "business"

    async def test_perspective_gather_unknown_perspective(self) -> None:
        """Should skip unknown perspectives."""
        ctx = {"job_id": "test-persp-456"}

        with patch("app.jobs.worker.get_gateway_client") as mock_gateway:

            mock_gateway_instance = MagicMock()
            mock_gateway_instance.generate = AsyncMock(
                return_value={"choices": [{"message": {"content": "Analysis"}}]}
            )
            mock_gateway.return_value = mock_gateway_instance

            result = await perspective_gather_job(
                ctx, query="Test", perspectives=["technical", "unknown_perspective"]
            )

            assert result.success is True
            # Should skip unknown perspective
            assert result.data is not None
            assert len(result.data["perspectives"]) == 1
            assert result.data["perspectives"][0]["name"] == "technical"


@pytest.mark.asyncio
class TestSynthesisJob:
    """Tests for synthesis_job function."""

    async def test_synthesis_job_basic(self) -> None:
        """Should synthesize perspective results."""
        ctx = {"job_id": "test-synthesis-123"}

        with patch("app.jobs.worker.get_gateway_client") as mock_gateway:

            mock_gateway_instance = MagicMock()
            mock_gateway_instance.generate = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": '{"executive_summary": "Synthesis", "key_insights": ["Insight 1"], "recommendations": ["Recommendation 1"], "confidence": 0.85, "confidence_rationale": "High confidence", "risks": [], "open_questions": []}'
                            }
                        }
                    ]
                }
            )
            mock_gateway.return_value = mock_gateway_instance

            perspective_results = [
                {"name": "technical", "display_name": "Technical", "analysis": "Technical analysis"}
            ]

            result = await synthesis_job(ctx, query="Test query", perspective_results=perspective_results)

            assert result.success is True
            assert result.data is not None
            assert result.data["query"] == "Test query"
            assert result.data["perspective_count"] == 1
            assert "synthesis" in result.data
            assert result.data["synthesis"]["executive_summary"] == "Synthesis"

    async def test_synthesis_job_empty_results_raises_error(self) -> None:
        """Should raise ValueError for empty perspective results."""
        ctx = {"job_id": "test-synthesis-error"}

        with pytest.raises(ValueError, match="No perspective results to synthesize"):
            await synthesis_job(ctx, query="Test", perspective_results=[])


@pytest.mark.asyncio
class TestExportJob:
    """Tests for export_job function."""

    async def test_export_job_basic(self) -> None:
        """Should export workspace successfully."""
        ctx = {"job_id": "test-export-123"}

        result = await export_job(ctx, workspace_id="workspace-123", export_format="json")

        assert result.success is True
        assert result.data is not None
        assert result.data["workspace_id"] == "workspace-123"
        assert result.data["format"] == "json"
        assert "file_path" in result.data
