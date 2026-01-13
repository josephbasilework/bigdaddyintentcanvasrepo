"""Tests for doc generation service and job function."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.base import JobResult
from app.jobs.doc_generation import (
    DocGenerationRequest,
    DocGenerationService,
    GeneratedDocument,
    get_doc_service,
)


class TestDocGenerationRequest:
    """Tests for DocGenerationRequest model."""

    def test_doc_generation_request_creation(self) -> None:
        """DocGenerationRequest should create with all fields."""
        request = DocGenerationRequest(
            job_id="job-123",
            node_id=None,
            workspace_id="workspace-456",
            doc_format="markdown",
            include_metadata=True,
        )

        assert request.job_id == "job-123"
        assert request.node_id is None
        assert request.workspace_id == "workspace-456"
        assert request.doc_format == "markdown"
        assert request.include_metadata is True

    def test_doc_generation_request_defaults(self) -> None:
        """DocGenerationRequest should have sensible defaults."""
        request = DocGenerationRequest()

        assert request.job_id is None
        assert request.node_id is None
        assert request.workspace_id is None
        assert request.doc_format == "markdown"
        assert request.include_metadata is True


class TestGeneratedDocument:
    """Tests for GeneratedDocument model."""

    def test_generated_document_creation(self) -> None:
        """GeneratedDocument should create with all fields."""
        doc = GeneratedDocument(
            content="# Test Document",
            format="markdown",
            artifact_id=1,
            source_job_id="job-123",
            source_node_id=None,
        )

        assert doc.content == "# Test Document"
        assert doc.format == "markdown"
        assert doc.artifact_id == 1
        assert doc.source_job_id == "job-123"
        assert doc.success is True

    def test_generated_document_defaults(self) -> None:
        """GeneratedDocument should have sensible defaults."""
        doc = GeneratedDocument(
            content="# Test",
            format="markdown",
        )

        assert doc.artifact_id is None
        assert doc.source_job_id is None
        assert doc.source_node_id is None
        assert doc.success is True  # Default
        assert doc.generated_at is not None  # Auto-generated


class TestDocGenerationService:
    """Tests for DocGenerationService."""

    def test_initialization(self) -> None:
        """DocGenerationService should initialize."""
        service = DocGenerationService()
        assert service.gateway is not None
        assert service.storage is not None

    @pytest.mark.asyncio
    async def test_generate_from_plan_result_markdown(self) -> None:
        """Service should generate markdown documentation from plan result."""
        service = DocGenerationService()

        plan_result = {
            "plan_metadata": {
                "goal": "Build a todo app",
                "approach": "Use React and FastAPI",
                "estimated_total_effort": "2 days",
                "assumptions": ["User has basic tech knowledge"],
                "risks": ["Scope creep"],
            },
            "task_dag": {
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Design UI",
                        "description": "Create wireframes",
                        "priority": "high",
                        "estimated_effort": "2 hours",
                        "dependencies": [],
                    },
                    {
                        "id": "task-2",
                        "title": "Build API",
                        "description": "Implement endpoints",
                        "priority": "high",
                        "estimated_effort": "4 hours",
                        "dependencies": ["task-1"],
                    },
                ],
                "dependencies": [
                    {
                        "task_id": "task-2",
                        "depends_on_task_id": "task-1",
                        "dependency_type": "hard",
                    }
                ],
            },
            "execution_order": [["task-1"], ["task-2"]],
            "job_id": "plan-job-123",
        }

        result = await service.generate_from_plan_result(
            plan_result, doc_format="markdown", include_metadata=True
        )

        assert isinstance(result, GeneratedDocument)
        assert result.format == "markdown"
        assert "# Plan: Build a todo app" in result.content
        assert "Design UI" in result.content
        assert "Build API" in result.content
        assert "React and FastAPI" in result.content
        assert result.success is True

    @pytest.mark.asyncio
    async def test_generate_from_plan_result_text(self) -> None:
        """Service should generate plain text documentation from plan result."""
        service = DocGenerationService()

        plan_result = {
            "plan_metadata": {
                "goal": "Test goal",
                "approach": "Test approach",
            },
            "task_dag": {"tasks": []},
            "execution_order": [],
            "job_id": "job-123",
        }

        result = await service.generate_from_plan_result(
            plan_result, doc_format="text", include_metadata=False
        )

        assert result.format == "text"
        assert "PLAN: Test goal" in result.content
        assert "Test approach" in result.content

    @pytest.mark.asyncio
    async def test_generate_from_research_result_markdown(self) -> None:
        """Service should generate markdown documentation from research result."""
        service = DocGenerationService()

        research_result = {
            "query": "What is AI?",
            "perspectives": [
                {
                    "name": "technical",
                    "display_name": "Technical",
                    "analysis": "AI is machine learning systems.",
                },
                {
                    "name": "business",
                    "display_name": "Business",
                    "analysis": "AI is a growing market.",
                },
            ],
            "judge_synthesis": {
                "overall_assessment": "AI has broad implications.",
                "recommendations": ["Invest in ML infrastructure", "Hire data scientists"],
            },
            "job_id": "research-job-123",
        }

        result = await service.generate_from_research_result(
            research_result, doc_format="markdown", include_metadata=True
        )

        assert isinstance(result, GeneratedDocument)
        assert result.format == "markdown"
        assert "# Research Report: What is AI?" in result.content
        assert "## Perspectives" in result.content
        assert "### Technical" in result.content
        assert "### Business" in result.content
        assert "## Synthesis" in result.content
        assert "AI has broad implications" in result.content

    @pytest.mark.asyncio
    async def test_format_plan_as_markdown_sections(self) -> None:
        """Service should format plan with proper markdown sections."""
        service = DocGenerationService()

        plan_result = {
            "plan_metadata": {
                "goal": "Test Plan",
                "approach": "Test approach",
                "estimated_total_effort": "1 day",
                "assumptions": ["Assumption 1", "Assumption 2"],
                "risks": ["Risk 1"],
            },
            "task_dag": {
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Task 1",
                        "description": "Description 1",
                        "priority": "high",
                        "estimated_effort": "1 hour",
                        "dependencies": [],
                    }
                ],
                "dependencies": [],
            },
            "execution_order": [["task-1"]],
            "job_id": "job-123",
        }

        result = await service.generate_from_plan_result(
            plan_result, doc_format="markdown", include_metadata=True
        )

        # Check sections are present
        assert "## Metadata" in result.content
        assert "## Approach" in result.content
        assert "### Assumptions" in result.content
        assert "### Risks" in result.content
        assert "## Tasks" in result.content
        assert "## Execution Order" in result.content

        # Check task details
        assert "### Task 1" in result.content
        assert "**Priority**: high" in result.content
        assert "**Estimated Effort**: 1 hour" in result.content

    @pytest.mark.asyncio
    async def test_generate_and_store(self) -> None:
        """Service should generate and store documentation as artifact."""
        service = DocGenerationService()

        source_artifact = MagicMock()
        source_artifact.id = 1
        source_artifact.job_id = "source-job-123"
        source_artifact.artifact_name = "Test Artifact"
        source_artifact.artifact_type = "synthesis_output"

        source_result_data = {
            "query": "Test query",
            "perspectives": [],
            "judge_synthesis": {"overall_assessment": "Test assessment"},
            "job_id": "source-job-123",
        }

        request = DocGenerationRequest(
            job_id="source-job-123",
            doc_format="markdown",
            include_metadata=True,
        )

        # Mock the storage
        mock_storage = MagicMock()
        mock_stored = MagicMock()
        mock_stored.id = 42
        mock_storage.store_artifact = AsyncMock(return_value=mock_stored)

        with patch.object(service, "storage", mock_storage):
            result = await service.generate_and_store(
                request, source_artifact, source_result_data, user_id="user-123"
            )

        assert result.artifact_id == 42
        assert result.success is True
        assert result.content is not None
        mock_storage.store_artifact.assert_called_once()


class TestGetDocService:
    """Tests for get_doc_service singleton."""

    def test_singleton_returns_same_instance(self) -> None:
        """get_doc_service should return singleton instance."""
        service1 = get_doc_service()
        service2 = get_doc_service()

        # Should be the same instance
        assert service1 is service2

    def test_singleton_initializes_once(self) -> None:
        """get_doc_service should initialize only once."""
        # Clear the singleton
        import app.jobs.doc_generation as doc_module
        doc_module._doc_service = None

        service1 = get_doc_service()
        service2 = get_doc_service()

        assert service1 is service2


class TestDocGenerationJobFunction:
    """Tests for doc_generation_job worker function."""

    @pytest.mark.asyncio
    async def test_doc_generation_job_with_plan_result(self) -> None:
        """doc_generation_job should process plan job and generate docs."""
        from app.jobs.worker import doc_generation_job

        # Mock the progress tracker and dependencies
        mock_job = MagicMock()
        mock_job.job_id = "source-job-123"
        mock_job.job_type = "planner"
        mock_job.result_data = '{"plan_metadata": {"goal": "Test"}, "task_dag": {"tasks": []}, "execution_order": []}'

        with patch("app.jobs.worker.progress_tracker") as mock_tracker:
            mock_tracker.create_job = AsyncMock()
            mock_tracker.get_job = AsyncMock(return_value=mock_job)
            mock_tracker.update_progress = AsyncMock()
            mock_tracker.complete_job = AsyncMock()

            # Mock database and storage
            mock_db = MagicMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock()
            mock_storage = MagicMock()
            mock_stored = MagicMock()
            mock_stored.id = 1
            mock_storage.store_artifact = AsyncMock(return_value=mock_stored)

            with patch("app.database.SessionLocal", return_value=mock_db):
                with patch("app.jobs.artifact_storage.get_artifact_storage", return_value=mock_storage):
                    ctx = {
                        "job_id": "doc-job-456",
                        "user_id": "user-123",
                        "workspace_id": "workspace-789",
                    }

                    result = await doc_generation_job(
                        ctx=ctx,
                        source_job_id="source-job-123",
                        doc_format="markdown",
                        include_metadata=True,
                    )

        assert isinstance(result, JobResult)
        assert result.success is True
        assert result.data is not None
        assert "artifact_id" in result.data

    @pytest.mark.asyncio
    async def test_doc_generation_job_source_not_found(self) -> None:
        """doc_generation_job should fail if source job not found."""
        from app.jobs.worker import doc_generation_job

        with patch("app.jobs.worker.progress_tracker") as mock_tracker:
            mock_tracker.create_job = AsyncMock()
            mock_tracker.get_job = AsyncMock(return_value=None)
            mock_tracker.update_progress = AsyncMock()
            mock_tracker.fail_job = AsyncMock()

            ctx = {
                "job_id": "doc-job-456",
                "user_id": "user-123",
                "workspace_id": "workspace-789",
            }

            result = await doc_generation_job(
                ctx=ctx,
                source_job_id="nonexistent-job",
                doc_format="markdown",
                include_metadata=True,
            )

        assert isinstance(result, JobResult)
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower()
