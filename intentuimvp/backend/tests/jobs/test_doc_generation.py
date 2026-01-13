"""Tests for doc generation service and job function."""

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.base import JobResult
from app.jobs.doc_generation import (
    DocGenerationRequest,
    DocGenerationService,
    DocUpdateSuggestion,
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


class TestDocUpdateSuggestion:
    """Tests for DocUpdateSuggestion model."""

    def test_doc_update_suggestion_creation(self) -> None:
        """DocUpdateSuggestion should create with all fields."""
        suggestion = DocUpdateSuggestion(
            existing_doc_artifact_id=1,
            source_artifact_id=2,
            new_content="# Updated Document\n\nNew content here.",
            diff="--- original.md\n+++ updated.md\n@@ -1,1 +1,1 @@\n-Old\n+New",
            has_changes=True,
            lines_added=5,
            lines_removed=3,
        )

        assert suggestion.existing_doc_artifact_id == 1
        assert suggestion.source_artifact_id == 2
        assert suggestion.new_content == "# Updated Document\n\nNew content here."
        assert suggestion.has_changes is True
        assert suggestion.lines_added == 5
        assert suggestion.lines_removed == 3
        assert suggestion.suggested_at is not None

    def test_doc_update_suggestion_defaults(self) -> None:
        """DocUpdateSuggestion should have sensible defaults."""
        suggestion = DocUpdateSuggestion(
            existing_doc_artifact_id=1,
            source_artifact_id=2,
            new_content="New content",
            diff="diff",
        )

        assert suggestion.has_changes is True  # Default
        assert suggestion.lines_added == 0  # Default
        assert suggestion.lines_removed == 0  # Default
        assert suggestion.suggested_at is not None  # Auto-generated


class TestDocDiffComputation:
    """Tests for diff computation functionality."""

    def test_compute_doc_diff_with_changes(self) -> None:
        """Service should compute diff between two documents with changes."""
        service = DocGenerationService()

        old_content = "# Original Document\n\nLine 1\nLine 2\nLine 3\n"
        new_content = "# Updated Document\n\nLine 1\nLine 2 modified\nLine 3\nLine 4\n"

        diff, added, removed = service.compute_doc_diff(old_content, new_content)

        assert "---" in diff
        assert "+++" in diff
        assert added > 0
        assert removed > 0

    def test_compute_doc_diff_identical(self) -> None:
        """Service should return empty diff for identical content."""
        service = DocGenerationService()

        content = "# Document\n\nSame content\n"
        diff, added, removed = service.compute_doc_diff(content, content)

        # No changes should result in minimal diff output
        assert added == 0
        assert removed == 0

    def test_compute_doc_diff_line_counts(self) -> None:
        """Service should correctly count added and removed lines."""
        service = DocGenerationService()

        old_content = "Line 1\nLine 2\nLine 3\n"
        new_content = "Line 1\nLine 2 modified\nLine 3\nLine 4\nLine 5\n"

        diff, added, removed = service.compute_doc_diff(old_content, new_content)

        # Line 2 removal counts as 1 removed, Line 2 modified + Line 4 + Line 5 = 3 added
        assert added == 3
        assert removed == 1

    def test_extract_source_artifact_id(self) -> None:
        """Service should extract source artifact ID from description."""
        service = DocGenerationService()

        doc_artifact = MagicMock()
        doc_artifact.description = "Generated documentation from artifact 42"

        source_id = service.extract_source_artifact_id(doc_artifact)

        assert source_id == 42

    def test_extract_source_artifact_id_no_match(self) -> None:
        """Service should return None when no artifact ID in description."""
        service = DocGenerationService()

        doc_artifact = MagicMock()
        doc_artifact.description = "Some other description"

        source_id = service.extract_source_artifact_id(doc_artifact)

        assert source_id is None

    def test_extract_source_artifact_id_no_description(self) -> None:
        """Service should return None when description is None."""
        service = DocGenerationService()

        doc_artifact = MagicMock()
        doc_artifact.description = None

        source_id = service.extract_source_artifact_id(doc_artifact)

        assert source_id is None

    @pytest.mark.asyncio
    async def test_suggest_doc_update_with_changes(self) -> None:
        """Service should generate update suggestion when content changes."""
        service = DocGenerationService()

        # Mock existing doc
        existing_doc = MagicMock()
        existing_doc.id = 1
        existing_doc.description = "Generated documentation from artifact 2"

        # Mock storage to return old content
        old_content = "# Old Document\n\nOld content\n"
        mock_storage = MagicMock()
        mock_storage.get_artifact_content = AsyncMock(return_value=(existing_doc, old_content))

        # Updated source artifact and data
        updated_source = MagicMock()
        updated_source.id = 2
        updated_source.artifact_type = "plan_output"

        updated_data = {
            "plan_metadata": {"goal": "Updated Goal", "approach": "New approach"},
            "task_dag": {"tasks": []},
            "execution_order": [],
            "job_id": "job-123",
        }

        mock_db = MagicMock()

        with patch.object(service, "storage", mock_storage):
            suggestion = await service.suggest_doc_update(
                db=mock_db,
                existing_doc=existing_doc,
                updated_source_artifact=updated_source,
                updated_result_data=updated_data,
            )

        assert suggestion is not None
        assert suggestion.has_changes is True
        assert suggestion.existing_doc_artifact_id == 1
        assert suggestion.source_artifact_id == 2
        assert "Updated Goal" in suggestion.new_content

    @pytest.mark.asyncio
    async def test_suggest_doc_update_no_changes(self) -> None:
        """Service should return None when content is identical."""
        service = DocGenerationService()

        # Mock existing doc
        existing_doc = MagicMock()
        existing_doc.id = 1
        existing_doc.description = "Generated documentation from artifact 2"

        # Mock storage to return content
        content = "# Document\n\nSame content\n"
        mock_storage = MagicMock()
        mock_storage.get_artifact_content = AsyncMock(return_value=(existing_doc, content))

        # Updated source with same result (will generate same content)
        updated_source = MagicMock()
        updated_source.id = 2
        updated_source.artifact_type = "plan_output"

        # Mock the generate method to return same content
        with patch.object(
            service,
            "generate_from_plan_result",
            return_value=MagicMock(content=content),
        ):
            updated_data = {
                "plan_metadata": {"goal": "Document"},
                "task_dag": {"tasks": []},
                "execution_order": [],
                "job_id": "job-123",
            }

            mock_db = MagicMock()

            with patch.object(service, "storage", mock_storage):
                suggestion = await service.suggest_doc_update(
                    db=mock_db,
                    existing_doc=existing_doc,
                    updated_source_artifact=updated_source,
                    updated_result_data=updated_data,
                )

        assert suggestion is None

    @pytest.mark.asyncio
    async def test_find_docs_for_source(self) -> None:
        """Service should find all docs generated from a source artifact."""
        service = DocGenerationService()

        mock_db = MagicMock()
        mock_query_result = MagicMock()
        mock_query_result.scalars.return_value.all.return_value = []

        with patch("sqlalchemy.select") as mock_select:
            mock_stmt = MagicMock()
            mock_select.return_value = mock_stmt
            mock_stmt.where.return_value.order_by.return_value = mock_stmt
            mock_db.execute = AsyncMock(return_value=mock_query_result)

            docs = await service.find_docs_for_source(mock_db, source_artifact_id=42)

        assert isinstance(docs, list)

    @pytest.mark.asyncio
    async def test_apply_doc_update(self) -> None:
        """Service should apply approved doc update."""
        service = DocGenerationService()

        suggestion = DocUpdateSuggestion(
            existing_doc_artifact_id=1,
            source_artifact_id=2,
            new_content="# Updated\n\nNew content",
            diff="diff",
        )

        # Mock database query with all required fields for StoredArtifact.from_model
        from datetime import datetime

        mock_artifact = MagicMock()
        mock_artifact.id = 1
        mock_artifact.job_id = "job-123"
        mock_artifact.user_id = "user-123"
        mock_artifact.workspace_id = "workspace-456"
        mock_artifact.artifact_type = "markdown_document"
        mock_artifact.artifact_name = "Test Doc"
        mock_artifact.description = "Test description"
        mock_artifact.filename = "doc_1.md"
        mock_artifact.mime_type = "text/markdown"
        mock_artifact.size_bytes = 100
        mock_artifact.storage_path = None
        mock_artifact.inline_data = "Old content"
        mock_artifact.is_archived = 0
        mock_artifact.created_at = datetime.now(UTC)
        mock_artifact.updated_at = datetime.now(UTC)
        mock_artifact.to_dict.return_value = {
            "id": 1,
            "job_id": "job-123",
            "user_id": "user-123",
            "workspace_id": "workspace-456",
            "artifact_type": "markdown_document",
            "artifact_name": "Test Doc",
            "description": "Test description",
            "filename": "doc_1.md",
            "mime_type": "text/markdown",
            "size_bytes": 100,
            "storage_path": None,
            "inline_data": "Old content",
            "is_archived": 0,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_artifact

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock file storage
        mock_file_storage = MagicMock()
        mock_file_storage.store = AsyncMock(return_value="/path/to/file")

        with patch("sqlalchemy.select", return_value=mock_result):
            with patch.object(service.storage, "_file_storage", mock_file_storage):
                result = await service.apply_doc_update(mock_db, suggestion, user_id="user-123")

        assert result is not None

    @pytest.mark.asyncio
    async def test_apply_doc_update_not_found(self) -> None:
        """Service should raise ValueError when artifact not found."""
        service = DocGenerationService()

        suggestion = DocUpdateSuggestion(
            existing_doc_artifact_id=999,
            source_artifact_id=2,
            new_content="New content",
            diff="diff",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("sqlalchemy.select", return_value=mock_result):
            with pytest.raises(ValueError, match="not found"):
                await service.apply_doc_update(mock_db, suggestion)
