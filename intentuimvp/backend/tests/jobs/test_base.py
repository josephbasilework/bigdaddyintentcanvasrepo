"""Tests for job base types and utilities."""


from app.jobs.base import (
    JobContext,
    JobResult,
    JobStatus,
    JobType,
    get_redis_settings,
)


class TestJobTypes:
    """Tests for JobType enum."""

    def test_job_type_values(self) -> None:
        """JobType should have expected values."""
        assert JobType.DEEP_RESEARCH == "deep_research"
        assert JobType.PERSPECTIVE_GATHER == "perspective_gather"
        assert JobType.SYNTHESIS == "synthesis"
        assert JobType.EXPORT == "export"


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_job_status_values(self) -> None:
        """JobStatus should have expected values."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.QUEUED == "queued"
        assert JobStatus.IN_PROGRESS == "in_progress"
        assert JobStatus.COMPLETE == "complete"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.CANCELLED == "cancelled"


class TestJobResult:
    """Tests for JobResult dataclass."""

    def test_successful_result(self) -> None:
        """JobResult should represent a successful job."""
        result = JobResult(
            success=True,
            data={"key": "value"},
            metadata={"job_id": "test-123"},
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.metadata == {"job_id": "test-123"}

    def test_failed_result(self) -> None:
        """JobResult should represent a failed job."""
        result = JobResult(
            success=False,
            error="Something went wrong",
            metadata={"job_id": "test-456"},
        )

        assert result.success is False
        assert result.data is None
        assert result.error == "Something went wrong"
        assert result.metadata == {"job_id": "test-456"}

    def test_metadata_defaults_to_empty_dict(self) -> None:
        """JobResult metadata should default to empty dict."""
        result = JobResult(success=True)
        assert result.metadata == {}


class TestJobContext:
    """Tests for JobContext dataclass."""

    def test_job_context_with_all_fields(self) -> None:
        """JobContext should store all provided fields."""
        context = JobContext(
            job_id="job-123",
            job_type=JobType.DEEP_RESEARCH,
            user_id="user-456",
            workspace_id="workspace-789",
        )

        assert context.job_id == "job-123"
        assert context.job_type == JobType.DEEP_RESEARCH
        assert context.user_id == "user-456"
        assert context.workspace_id == "workspace-789"

    def test_job_context_with_optional_fields(self) -> None:
        """JobContext should work with only required fields."""
        context = JobContext(
            job_id="job-123",
            job_type=JobType.EXPORT,
        )

        assert context.job_id == "job-123"
        assert context.job_type == JobType.EXPORT
        assert context.user_id is None
        assert context.workspace_id is None


class TestRedisSettings:
    """Tests for Redis settings configuration."""

    def test_redis_settings_returns_valid_config(self) -> None:
        """get_redis_settings should return valid RedisSettings."""
        settings = get_redis_settings()

        assert settings.host is not None
        assert isinstance(settings.port, int)
        assert settings.port > 0
        assert settings.database >= 0
