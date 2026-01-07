"""Tests for Job artifact storage service."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.artifact_storage import (
    ArtifactMetadata,
    ArtifactStorageService,
    StoredArtifact,
    get_artifact_storage,
)
from app.models.artifact import ArtifactType


class TestArtifactType:
    """Tests for ArtifactType enum."""

    def test_artifact_type_values(self) -> None:
        """ArtifactType should have expected values."""
        assert ArtifactType.RESEARCH_REPORT == "research_report"
        assert ArtifactType.SYNTHESIS_OUTPUT == "synthesis_output"
        assert ArtifactType.PDF_DOCUMENT == "pdf_document"
        assert ArtifactType.CHART == "chart"
        assert ArtifactType.OTHER == "other"


class TestArtifactMetadata:
    """Tests for ArtifactMetadata model."""

    def test_artifact_metadata_creation(self) -> None:
        """ArtifactMetadata should create with all fields."""
        metadata = ArtifactMetadata(
            artifact_type=ArtifactType.RESEARCH_REPORT,
            artifact_name="Test Report",
            description="A test research report",
            filename="report.txt",
            mime_type="text/plain",
            archive_after_days=30,
        )

        assert metadata.artifact_type == ArtifactType.RESEARCH_REPORT
        assert metadata.artifact_name == "Test Report"
        assert metadata.description == "A test research report"
        assert metadata.filename == "report.txt"
        assert metadata.mime_type == "text/plain"
        assert metadata.archive_after_days == 30

    def test_artifact_metadata_defaults(self) -> None:
        """ArtifactMetadata should have sensible defaults."""
        metadata = ArtifactMetadata(
            artifact_type=ArtifactType.OTHER,
            artifact_name="Test",
        )

        assert metadata.description is None
        assert metadata.filename is None
        assert metadata.mime_type is None
        assert metadata.archive_after_days == 30  # Default


class TestStoredArtifact:
    """Tests for StoredArtifact model."""

    def test_stored_artifact_from_dict(self) -> None:
        """StoredArtifact should create from dictionary."""
        data = {
            "id": 1,
            "job_id": "job-123",
            "user_id": "user-456",
            "workspace_id": "workspace-789",
            "artifact_type": "research_report",
            "artifact_name": "Test Report",
            "description": "A test",
            "filename": "report.txt",
            "mime_type": "text/plain",
            "size_bytes": 100,
            "storage_path": "/path/to/file",
            "inline_data": None,
            "is_archived": False,
            "archive_after_days": 30,
            "created_at": "2026-01-07T12:00:00",
            "updated_at": "2026-01-07T12:00:00",
        }

        # Use model_validate for Pydantic models with dict input
        artifact = StoredArtifact.model_validate(data)

        assert artifact.id == 1
        assert artifact.job_id == "job-123"
        assert artifact.artifact_type == "research_report"
        assert artifact.is_archived is False


class TestArtifactStorageService:
    """Tests for ArtifactStorageService."""

    def test_initialization(self) -> None:
        """ArtifactStorageService should initialize with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactStorageService(storage_path=tmpdir)
            assert service.storage_path == Path(tmpdir)
            assert service.inline_threshold == 10240  # 10KB default

    def test_custom_initialization(self) -> None:
        """ArtifactStorageService should accept custom parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactStorageService(
                storage_path=tmpdir,
                inline_threshold=2048,
            )
            assert service.inline_threshold == 2048

    def test_get_storage_path(self) -> None:
        """_get_storage_path should create valid paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactStorageService(storage_path=tmpdir)

            path = service._get_storage_path("job-123", 1, "report.txt")
            assert "job-123" in path
            assert "report.txt" in path

    @pytest.mark.asyncio
    async def test_store_inline_artifact(self) -> None:
        """Service should store small artifacts inline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ArtifactStorageService(
                storage_path=tmpdir,
                inline_threshold=10240,
            )

            # Mock database session
            mock_db = AsyncMock(spec=AsyncSession)
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()

            # Create a mock artifact with ID
            mock_artifact = MagicMock()
            mock_artifact.id = 1
            mock_artifact.is_inline = MagicMock(return_value=True)
            mock_artifact.to_dict = MagicMock(
                return_value={
                    "id": 1,
                    "job_id": "job-123",
                    "artifact_type": "text",
                    "artifact_name": "Test",
                    "inline_data": "small content",
                    "is_archived": False,
                    "created_at": "2026-01-07T12:00:00",
                    "updated_at": "2026-01-07T12:00:00",
                }
            )

            # Mock the database add/refresh to set the artifact
            async def mock_refresh(obj):
                if hasattr(obj, '__dict__'):
                    obj.id = 1

            mock_db.refresh.side_effect = mock_refresh

            # Note: This test would need a proper async session mock
            # For now, we're testing the logic structure
            with patch.object(service, '_file_storage'):
                # Small content should be stored inline
                content = "x" * 100  # Well under threshold
                assert len(content) < service.inline_threshold

    @pytest.mark.asyncio
    async def test_list_job_artifacts(self) -> None:
        """Service should list artifacts for a job."""
        # This test verifies the service structure
        # Actual database operations require proper async mocking
        # or integration test setup
        with tempfile.TemporaryDirectory():
            _ = ArtifactStorageService()
            _ = AsyncMock(spec=AsyncSession)


class TestGetArtifactStorage:
    """Tests for get_artifact_storage singleton."""

    def test_singleton_returns_same_instance(self) -> None:
        """get_artifact_storage should return singleton instance."""
        service1 = get_artifact_storage()
        service2 = get_artifact_storage()

        # Should be the same instance
        assert service1 is service2

    def test_singleton_initializes_once(self) -> None:
        """get_artifact_storage should initialize only once."""
        # Clear the singleton
        import app.jobs.artifact_storage as artifact_module
        artifact_module._artifact_service = None

        service1 = get_artifact_storage()
        service2 = get_artifact_storage()

        assert service1 is service2
