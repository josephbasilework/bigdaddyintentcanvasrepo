"""Tests for job worker functions.

Tests the actual job implementations that process background tasks.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import select

from app.database import AsyncSessionLocal, async_engine
from app.jobs.base import JobType
from app.jobs.worker import (
    DEFAULT_PERSPECTIVES,
    PerspectiveAgent,
    deep_research_job,
    export_job,
    perspective_gather_job,
    planner_job,
    synthesis_job,
    transcription_job,
)
from app.models.artifact import ArtifactType, JobArtifact
from app.models.edge import RelationType
from app.models.node import NodeType
from app.repositories.canvas_repo import CanvasRepository
from app.repositories.edge_repo import EdgeRepository
from app.repositories.node_repo import NodeRepository


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
class TestStreamPeriodicProgress:
    """Tests for _stream_periodic_progress helper function."""

    @patch("app.jobs.worker.progress_tracker")
    @patch("app.jobs.worker.check_job_cancelled")
    async def test_stream_periodic_progress_sends_updates(self, mock_check_cancel, mock_progress_tracker):
        """Should send progress updates at the specified interval."""
        mock_check_cancel.return_value = None
        mock_progress_tracker.update_progress = AsyncMock()

        # Use a short interval for testing
        task = await asyncio.create_task(
            self._run_periodic_progress(
                job_id="test-job-123",
                current_step="Testing",
                step_number=1,
                steps_total=5,
                progress_percent=20.0,
                interval_seconds=0.1,  # 100ms for fast test
            )
        )

        # Wait for multiple updates
        await asyncio.sleep(0.35)

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have called update_progress multiple times
        # At least 3 times in 350ms with 100ms interval
        assert mock_progress_tracker.update_progress.call_count >= 3

    @patch("app.jobs.worker.progress_tracker")
    @patch("app.jobs.worker.check_job_cancelled")
    async def test_stream_periodic_progress_handles_cancellation(self, mock_check_cancel, mock_progress_tracker):
        """Should handle task cancellation gracefully."""
        mock_check_cancel.return_value = None
        mock_progress_tracker.update_progress = AsyncMock()

        task = await self._run_periodic_progress(
            job_id="test-job-456",
            current_step="Testing",
            step_number=1,
            steps_total=5,
            progress_percent=20.0,
            interval_seconds=0.1,
        )

        # Cancel immediately
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should not raise any errors
        assert True

    @patch("app.jobs.worker.progress_tracker")
    @patch("app.jobs.worker.check_job_cancelled")
    async def test_stream_periodic_progress_propagates_job_cancelled(self, mock_check_cancel, mock_progress_tracker):
        """Should propagate JobCancelledError from check_job_cancelled."""
        from app.jobs.worker import JobCancelledError

        mock_progress_tracker.update_progress = AsyncMock()

        # Make check_job_cancelled raise JobCancelledError
        call_count = 0
        async def side_effect(job_id):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise JobCancelledError("Job was cancelled")

        mock_check_cancel.side_effect = side_effect

        task = await self._run_periodic_progress(
            job_id="test-job-cancelled",
            current_step="Testing",
            step_number=1,
            steps_total=5,
            progress_percent=20.0,
            interval_seconds=0.05,
        )

        # Should raise JobCancelledError
        with pytest.raises(JobCancelledError, match="Job was cancelled"):
            await task

    async def _run_periodic_progress(
        self, job_id: str, current_step: str, step_number: int, steps_total: int, progress_percent: float, interval_seconds: float
    ):
        """Helper to import and run _stream_periodic_progress (which is private)."""
        from app.jobs.worker import _stream_periodic_progress
        return await _stream_periodic_progress(
            job_id=job_id,
            current_step=current_step,
            step_number=step_number,
            steps_total=steps_total,
            progress_percent=progress_percent,
            interval_seconds=interval_seconds,
        )


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

    async def test_deep_research_job_stores_report_node(self) -> None:
        """Should store report artifact and link a report node to inputs."""
        async with AsyncSessionLocal() as session:
            canvas_repo = CanvasRepository(session)
            canvas = await canvas_repo.create_canvas(user_id="report-user", name="default")
            canvas_id = canvas.id

            node_repo = NodeRepository(session)
            node_a = await node_repo.create_node(
                canvas_id=canvas.id,
                label="Source A",
                type=NodeType.TEXT,
                position={"x": 10, "y": 20, "z": 0},
                node_metadata=None,
            )
            node_b = await node_repo.create_node(
                canvas_id=canvas.id,
                label="Source B",
                type=NodeType.TEXT,
                position={"x": 40, "y": 60, "z": 0},
                node_metadata=None,
            )
            input_ids = [node_a.id, node_b.id]

        ctx = {
            "job_id": "test-job-report-store",
            "user_id": "report-user",
            "workspace_id": str(canvas_id),
        }

        with patch("app.jobs.worker.get_gateway_client") as mock_gateway, patch(
            "app.jobs.worker.get_research_agent"
        ) as mock_research_agent:

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

            result = await deep_research_job(
                ctx,
                query="Test query",
                depth=2,
                input_refs=[str(input_ids[0]), input_ids[1]],
            )

            assert result.success is True
            assert result.data is not None

            report_artifact_id = result.data["report_artifact_id"]
            report_node_id = result.data["report_node_id"]
            report_edge_ids = result.data["report_edge_ids"]

        async with AsyncSessionLocal() as session:
            node_repo = NodeRepository(session)
            report_node = await node_repo.get_by_id(report_node_id)
            assert report_node is not None
            assert report_node.type == NodeType.DOCUMENT

            metadata = report_node.get_metadata()
            assert metadata["artifactId"] == report_artifact_id
            assert metadata["jobId"] == ctx["job_id"]
            assert metadata["jobType"] == JobType.DEEP_RESEARCH.value

            edge_repo = EdgeRepository(session)
            edges = await edge_repo.get_by_node(report_node_id)
            assert {edge.to_node_id for edge in edges} == set(input_ids)
            assert all(edge.relation_type == RelationType.DERIVED_FROM for edge in edges)
            assert {edge.id for edge in edges} == set(report_edge_ids)

            artifact_result = await session.execute(
                select(JobArtifact).where(JobArtifact.id == report_artifact_id)
            )
            artifact = artifact_result.scalar_one_or_none()
            assert artifact is not None
            assert artifact.artifact_type == ArtifactType.RESEARCH_REPORT.value
            assert artifact.workspace_id == str(canvas_id)

    async def test_deep_research_job_creates_report_node_and_artifact(self) -> None:
        """Should store report artifact and link a report node to inputs."""
        async with AsyncSessionLocal() as session:
            canvas_repo = CanvasRepository(session)
            canvas = await canvas_repo.create_canvas(user_id="report-user", name="default")
            canvas_id = canvas.id

            node_repo = NodeRepository(session)
            node_a = await node_repo.create_node(
                canvas_id=canvas.id,
                label="Source A",
                type=NodeType.TEXT,
                position={"x": 10, "y": 20, "z": 0},
                node_metadata=None,
            )
            node_b = await node_repo.create_node(
                canvas_id=canvas.id,
                label="Source B",
                type=NodeType.TEXT,
                position={"x": 40, "y": 60, "z": 0},
                node_metadata=None,
            )
            input_ids = [node_a.id, node_b.id]

        ctx = {
            "job_id": "test-job-report-create",
            "user_id": "report-user",
            "workspace_id": str(canvas_id),
        }

        with patch("app.jobs.worker.get_gateway_client") as mock_gateway, patch(
            "app.jobs.worker.get_research_agent"
        ) as mock_research_agent:

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

            result = await deep_research_job(
                ctx,
                query="Test query",
                depth=2,
                input_refs=[str(input_ids[0]), input_ids[1]],
            )

            assert result.success is True
            assert result.data is not None

            report_artifact_id = result.data["report_artifact_id"]
            report_node_id = result.data["report_node_id"]
            report_edge_ids = result.data["report_edge_ids"]

        async with AsyncSessionLocal() as session:
            node_repo = NodeRepository(session)
            report_node = await node_repo.get_by_id(report_node_id)
            assert report_node is not None
            assert report_node.type == NodeType.DOCUMENT

            metadata = report_node.get_metadata()
            assert metadata["artifactId"] == report_artifact_id
            assert metadata["jobId"] == ctx["job_id"]
            assert metadata["jobType"] == JobType.DEEP_RESEARCH.value

            edge_repo = EdgeRepository(session)
            edges = await edge_repo.get_by_node(report_node_id)
            assert {edge.to_node_id for edge in edges} == set(input_ids)
            assert all(edge.relation_type == RelationType.DERIVED_FROM for edge in edges)
            assert {edge.id for edge in edges} == set(report_edge_ids)

            artifact_result = await session.execute(
                select(JobArtifact).where(JobArtifact.id == report_artifact_id)
            )
            artifact = artifact_result.scalar_one_or_none()
            assert artifact is not None
            assert artifact.artifact_type == ArtifactType.RESEARCH_REPORT.value
            assert artifact.workspace_id == str(canvas_id)


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


@pytest.mark.asyncio
class TestTranscriptionJob:
    """Tests for transcription_job function."""

    async def test_transcription_job_basic(self) -> None:
        """Should transcribe audio block successfully."""
        from app.models.audio_block import AudioBlock, AudioBlockStatus

        ctx = {"job_id": "test-transcription-123"}

        # Mock the audio block repository and database
        mock_audio_block = MagicMock(spec=AudioBlock)
        mock_audio_block.id = 123
        mock_audio_block.audio_uri = "audio_blocks/test.webm"
        mock_audio_block.duration = 30.5
        mock_audio_block.status = AudioBlockStatus.READY

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_audio_block)
        mock_repo.set_status = AsyncMock(return_value=mock_audio_block)
        mock_repo.update_transcription = AsyncMock(return_value=mock_audio_block)

        with patch("app.repositories.audio_block_repo.AudioBlockRepository", return_value=mock_repo):
            result = await transcription_job(ctx, audio_block_id=123)

        assert result.success is True
        assert result.data is not None
        assert result.data["audio_block_id"] == 123
        assert result.data["status"] == "transcribed"
        assert "transcription" in result.data
        assert "job_id" in result.data

    async def test_transcription_job_audio_block_not_found(self) -> None:
        """Should return error when audio block not found."""
        ctx = {"job_id": "test-transcription-404"}

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with patch("app.repositories.audio_block_repo.AudioBlockRepository", return_value=mock_repo):
            result = await transcription_job(ctx, audio_block_id=999)

        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower()

    async def test_transcription_job_handles_cancellation(self) -> None:
        """Should handle job cancellation gracefully."""
        from app.jobs.worker import JobCancelledError

        ctx = {"job_id": "test-transcription-cancel"}

        mock_audio_block = MagicMock()
        mock_audio_block.id = 123
        mock_audio_block.audio_uri = "audio_blocks/test.webm"
        mock_audio_block.duration = 30.0

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_audio_block)
        mock_repo.set_status = AsyncMock(return_value=mock_audio_block)

        with patch(
            "app.jobs.worker.check_job_cancelled",
            side_effect=JobCancelledError("Job was cancelled"),
        ), patch("app.repositories.audio_block_repo.AudioBlockRepository", return_value=mock_repo):
            result = await transcription_job(ctx, audio_block_id=123)

        assert result.success is False
        assert result.error == "Job was cancelled"
        assert result.metadata.get("cancelled") is True

    async def test_transcription_job_updates_status(self) -> None:
        """Should update audio block status through transcription process."""
        from app.models.audio_block import AudioBlock, AudioBlockStatus

        ctx = {"job_id": "test-transcription-status"}
        status_updates = []

        mock_audio_block = MagicMock(spec=AudioBlock)
        mock_audio_block.id = 123
        mock_audio_block.audio_uri = "audio_blocks/test.webm"
        mock_audio_block.duration = 30.5
        mock_audio_block.status = AudioBlockStatus.READY

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_audio_block)

        async def mock_set_status(block_id: int, status: AudioBlockStatus, **kwargs):
            status_updates.append(status)
            return mock_audio_block

        mock_repo.set_status = mock_set_status
        mock_repo.update_transcription = AsyncMock(return_value=mock_audio_block)

        with patch("app.repositories.audio_block_repo.AudioBlockRepository", return_value=mock_repo):
            result = await transcription_job(ctx, audio_block_id=123)

        assert result.success is True
        # Should have set status to TRANSCRIBING at least once
        assert AudioBlockStatus.TRANSCRIBING in status_updates


@pytest.mark.asyncio
class TestPlannerJob:
    """Tests for planner_job function."""

    async def test_planner_job_basic(self) -> None:
        """Should generate a plan successfully with valid goal."""
        from app.agents.planner_agent import PlanMetadata, PlannerResult, PlanTask, TaskDAG

        ctx = {"job_id": "test-planner-123"}

        mock_planner_result = PlannerResult(
            plan_metadata=PlanMetadata(
                goal="Test goal",
                approach="Test approach",
                assumptions=["Assumption 1"],
                risks=["Risk 1"],
            ),
            task_dag=TaskDAG(
                tasks=[
                    PlanTask(
                        id="task-1",
                        title="Task 1",
                        description="First task",
                        priority="high",
                    ),
                    PlanTask(
                        id="task-2",
                        title="Task 2",
                        description="Second task",
                        priority="medium",
                        dependencies=["task-1"],
                    ),
                ],
                dependencies=[],
            ),
            reasoning="Test reasoning",
            success=True,
        )

        mock_planner = MagicMock()
        mock_planner.plan = AsyncMock(return_value=mock_planner_result)

        with patch("app.agents.planner_agent.get_planner", return_value=mock_planner):
            result = await planner_job(ctx, goal="Test goal")

        assert result.success is True
        assert result.data is not None
        assert result.data["success"] is True
        assert "plan_metadata" in result.data
        assert result.data["plan_metadata"]["goal"] == "Test goal"
        assert "task_dag" in result.data
        assert len(result.data["task_dag"]["tasks"]) == 2
        assert "execution_order" in result.data
        assert "reasoning" in result.data

    async def test_planner_job_with_context(self) -> None:
        """Should pass context to the planner."""
        from app.agents.planner_agent import PlanMetadata, PlannerResult, PlanTask, TaskDAG

        ctx = {"job_id": "test-planner-ctx", "user_id": "user-123", "workspace_id": "ws-456"}

        mock_planner_result = PlannerResult(
            plan_metadata=PlanMetadata(
                goal="Goal with context",
                approach="Contextual approach",
            ),
            task_dag=TaskDAG(
                tasks=[
                    PlanTask(id="task-1", title="Task 1", description="Task desc"),
                ],
                dependencies=[],
            ),
            reasoning="Used context",
            success=True,
        )

        mock_planner = MagicMock()
        mock_planner.plan = AsyncMock(return_value=mock_planner_result)

        with patch("app.agents.planner_agent.get_planner", return_value=mock_planner):
            result = await planner_job(
                ctx, goal="Goal with context", context="User is working on project X"
            )

        assert result.success is True
        mock_planner.plan.assert_called_once_with("Goal with context", "User is working on project X")

    async def test_planner_job_handles_cancellation(self) -> None:
        """Should handle job cancellation gracefully."""
        from app.jobs.worker import JobCancelledError

        ctx = {"job_id": "test-planner-cancel"}

        with patch(
            "app.jobs.worker.check_job_cancelled",
            side_effect=JobCancelledError("Job was cancelled"),
        ):
            result = await planner_job(ctx, goal="Test goal")

        assert result.success is False
        assert result.error == "Job was cancelled"
        assert result.metadata.get("cancelled") is True

    async def test_planner_job_handles_error(self) -> None:
        """Should return JobResult with error on exception."""
        ctx = {"job_id": "test-planner-error"}

        mock_planner = MagicMock()
        mock_planner.plan = AsyncMock(side_effect=Exception("Planner error"))

        with patch("app.agents.planner_agent.get_planner", return_value=mock_planner):
            result = await planner_job(ctx, goal="Test goal")

        assert result.success is False
        assert result.error is not None
        assert "Planner error" in result.error

    async def test_planner_job_includes_execution_order(self) -> None:
        """Should include execution order from task DAG."""
        from app.agents.planner_agent import (
            PlanMetadata,
            PlannerResult,
            PlanTask,
            TaskDAG,
            TaskDependency,
        )

        ctx = {"job_id": "test-planner-order"}

        mock_planner_result = PlannerResult(
            plan_metadata=PlanMetadata(
                goal="Multi-step goal",
                approach="Sequential approach",
            ),
            task_dag=TaskDAG(
                tasks=[
                    PlanTask(id="task-1", title="Task 1", description="First"),
                    PlanTask(id="task-2", title="Task 2", description="Second"),
                    PlanTask(id="task-3", title="Task 3", description="Third"),
                ],
                dependencies=[
                    TaskDependency(task_id="task-2", depends_on_task_id="task-1"),
                    TaskDependency(task_id="task-3", depends_on_task_id="task-2"),
                ],
            ),
            reasoning="Sequential",
            success=True,
        )

        mock_planner = MagicMock()
        mock_planner.plan = AsyncMock(return_value=mock_planner_result)

        with patch("app.agents.planner_agent.get_planner", return_value=mock_planner):
            result = await planner_job(ctx, goal="Multi-step goal")

        assert result.success is True
        assert result.data is not None
        assert "execution_order" in result.data
        execution_order = result.data["execution_order"]
        assert len(execution_order) == 3
        assert execution_order[0] == ["task-1"]
        assert execution_order[1] == ["task-2"]
        assert execution_order[2] == ["task-3"]

    async def test_planner_job_returns_failed_plan(self) -> None:
        """Should return success=False when planner returns failed plan."""
        from app.agents.planner_agent import PlanMetadata, PlannerResult, PlanTask, TaskDAG

        ctx = {"job_id": "test-planner-failed"}

        mock_planner_result = PlannerResult(
            plan_metadata=PlanMetadata(
                goal="Failed goal",
                approach="Fallback approach",
                risks=["Planning error: Something went wrong"],
            ),
            task_dag=TaskDAG(
                tasks=[
                    PlanTask(id="task-1", title="Fallback task", description="Manual work"),
                ],
                dependencies=[],
            ),
            reasoning="Planning encountered an error",
            success=False,
        )

        mock_planner = MagicMock()
        mock_planner.plan = AsyncMock(return_value=mock_planner_result)

        with patch("app.agents.planner_agent.get_planner", return_value=mock_planner):
            result = await planner_job(ctx, goal="Failed goal")

        assert result.success is False
        assert result.data is not None
        assert result.data["success"] is False


@pytest_asyncio.fixture(autouse=True)
async def _dispose_async_engine():
    """Dispose the async engine to avoid lingering background threads."""
    yield
    await async_engine.dispose()
