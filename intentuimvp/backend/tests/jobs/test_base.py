"""Tests for job base types and utilities."""

import pytest

from app.jobs.base import (
    JobContext,
    JobResult,
    JobStateMachine,
    JobStatus,
    JobTransitionError,
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


class TestJobStateMachine:
    """Tests for JobStateMachine state transition validation."""

    def test_valid_transition_from_pending_to_queued(self) -> None:
        """pending -> queued should be a valid transition."""
        JobStateMachine.validate_transition(JobStatus.PENDING, JobStatus.QUEUED)

    def test_valid_transition_from_queued_to_in_progress(self) -> None:
        """queued -> in_progress should be a valid transition."""
        JobStateMachine.validate_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS)

    def test_valid_transition_from_in_progress_to_complete(self) -> None:
        """in_progress -> complete should be a valid transition."""
        JobStateMachine.validate_transition(JobStatus.IN_PROGRESS, JobStatus.COMPLETE)

    def test_valid_transition_from_in_progress_to_failed(self) -> None:
        """in_progress -> failed should be a valid transition."""
        JobStateMachine.validate_transition(JobStatus.IN_PROGRESS, JobStatus.FAILED)

    def test_valid_transition_from_queued_to_cancelled(self) -> None:
        """queued -> cancelled should be a valid transition."""
        JobStateMachine.validate_transition(JobStatus.QUEUED, JobStatus.CANCELLED)

    def test_valid_transition_from_in_progress_to_cancelled(self) -> None:
        """in_progress -> cancelled should be a valid transition."""
        JobStateMachine.validate_transition(JobStatus.IN_PROGRESS, JobStatus.CANCELLED)

    def test_valid_transition_from_pending_to_cancelled(self) -> None:
        """pending -> cancelled should be a valid transition."""
        JobStateMachine.validate_transition(JobStatus.PENDING, JobStatus.CANCELLED)

    def test_idempotent_transition_is_valid(self) -> None:
        """Transitioning to the same state should always be valid."""
        for status in JobStatus:
            JobStateMachine.validate_transition(status, status)

    def test_invalid_transition_from_complete_to_in_progress(self) -> None:
        """complete -> in_progress should raise JobTransitionError (PRD JI-002)."""
        with pytest.raises(JobTransitionError) as exc_info:
            JobStateMachine.validate_transition(JobStatus.COMPLETE, JobStatus.IN_PROGRESS)

        assert "Cannot transition from terminal state" in str(exc_info.value)
        assert "complete" in str(exc_info.value).lower()

    def test_invalid_transition_from_failed_to_in_progress(self) -> None:
        """failed -> in_progress should raise JobTransitionError (PRD JI-002)."""
        with pytest.raises(JobTransitionError) as exc_info:
            JobStateMachine.validate_transition(JobStatus.FAILED, JobStatus.IN_PROGRESS)

        assert "Cannot transition from terminal state" in str(exc_info.value)
        assert "failed" in str(exc_info.value).lower()

    def test_invalid_transition_from_complete_to_queued(self) -> None:
        """complete -> queued should raise JobTransitionError."""
        with pytest.raises(JobTransitionError) as exc_info:
            JobStateMachine.validate_transition(JobStatus.COMPLETE, JobStatus.QUEUED)

        assert "Cannot transition from terminal state" in str(exc_info.value)

    def test_invalid_transition_from_cancelled_to_in_progress(self) -> None:
        """cancelled -> in_progress should raise JobTransitionError."""
        with pytest.raises(JobTransitionError) as exc_info:
            JobStateMachine.validate_transition(JobStatus.CANCELLED, JobStatus.IN_PROGRESS)

        assert "Cannot transition from terminal state" in str(exc_info.value)

    def test_invalid_transition_from_queued_to_complete(self) -> None:
        """queued -> complete should raise JobTransitionError."""
        with pytest.raises(JobTransitionError) as exc_info:
            JobStateMachine.validate_transition(JobStatus.QUEUED, JobStatus.COMPLETE)

        assert "Allowed transitions" in str(exc_info.value)

    def test_invalid_transition_from_pending_to_failed(self) -> None:
        """pending -> failed should raise JobTransitionError."""
        with pytest.raises(JobTransitionError) as exc_info:
            JobStateMachine.validate_transition(JobStatus.PENDING, JobStatus.FAILED)

        assert "Allowed transitions" in str(exc_info.value)

    def test_can_transition_returns_true_for_valid(self) -> None:
        """can_transition should return True for valid transitions."""
        assert JobStateMachine.can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS) is True

    def test_can_transition_returns_false_for_invalid(self) -> None:
        """can_transition should return False for invalid transitions."""
        assert JobStateMachine.can_transition(JobStatus.COMPLETE, JobStatus.IN_PROGRESS) is False

    def test_is_terminal_for_complete(self) -> None:
        """is_terminal should return True for complete status."""
        assert JobStateMachine.is_terminal(JobStatus.COMPLETE) is True

    def test_is_terminal_for_failed(self) -> None:
        """is_terminal should return True for failed status."""
        assert JobStateMachine.is_terminal(JobStatus.FAILED) is True

    def test_is_terminal_for_cancelled(self) -> None:
        """is_terminal should return True for cancelled status."""
        assert JobStateMachine.is_terminal(JobStatus.CANCELLED) is True

    def test_is_terminal_for_non_terminal_states(self) -> None:
        """is_terminal should return False for non-terminal states."""
        assert JobStateMachine.is_terminal(JobStatus.PENDING) is False
        assert JobStateMachine.is_terminal(JobStatus.QUEUED) is False
        assert JobStateMachine.is_terminal(JobStatus.IN_PROGRESS) is False

    def test_is_active_for_in_progress(self) -> None:
        """is_active should return True for in_progress status."""
        assert JobStateMachine.is_active(JobStatus.IN_PROGRESS) is True

    def test_is_active_for_non_active_states(self) -> None:
        """is_active should return False for non-active states."""
        assert JobStateMachine.is_active(JobStatus.PENDING) is False
        assert JobStateMachine.is_active(JobStatus.QUEUED) is False
        assert JobStateMachine.is_active(JobStatus.COMPLETE) is False

    def test_is_pending_for_pending(self) -> None:
        """is_pending should return True for pending status."""
        assert JobStateMachine.is_pending(JobStatus.PENDING) is True

    def test_is_pending_for_queued(self) -> None:
        """is_pending should return True for queued status."""
        assert JobStateMachine.is_pending(JobStatus.QUEUED) is True

    def test_is_pending_for_non_pending_states(self) -> None:
        """is_pending should return False for non-pending states."""
        assert JobStateMachine.is_pending(JobStatus.IN_PROGRESS) is False
        assert JobStateMachine.is_pending(JobStatus.COMPLETE) is False

    def test_get_valid_transitions_from_pending(self) -> None:
        """get_valid_transitions should return correct targets for pending."""
        transitions = JobStateMachine.get_valid_transitions(JobStatus.PENDING)
        assert transitions == {JobStatus.QUEUED, JobStatus.CANCELLED}

    def test_get_valid_transitions_from_queued(self) -> None:
        """get_valid_transitions should return correct targets for queued."""
        transitions = JobStateMachine.get_valid_transitions(JobStatus.QUEUED)
        assert transitions == {JobStatus.IN_PROGRESS, JobStatus.CANCELLED}

    def test_get_valid_transitions_from_in_progress(self) -> None:
        """get_valid_transitions should return correct targets for in_progress."""
        transitions = JobStateMachine.get_valid_transitions(JobStatus.IN_PROGRESS)
        assert transitions == {JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED}

    def test_get_valid_transitions_from_complete(self) -> None:
        """get_valid_transitions should return empty set for terminal states."""
        transitions = JobStateMachine.get_valid_transitions(JobStatus.COMPLETE)
        assert transitions == set()

    def test_get_valid_transitions_from_failed(self) -> None:
        """get_valid_transitions should return empty set for terminal states."""
        transitions = JobStateMachine.get_valid_transitions(JobStatus.FAILED)
        assert transitions == set()

    def test_validate_transition_with_string_inputs(self) -> None:
        """validate_transition should accept string status values."""
        # Should not raise
        JobStateMachine.validate_transition("queued", "in_progress")
        JobStateMachine.validate_transition("in_progress", "complete")

    def test_validate_transition_with_mixed_inputs(self) -> None:
        """validate_transition should accept mixed string/enum inputs."""
        # Should not raise
        JobStateMachine.validate_transition(JobStatus.QUEUED, "in_progress")
        JobStateMachine.validate_transition("queued", JobStatus.IN_PROGRESS)

    def test_transition_error_contains_from_and_to_status(self) -> None:
        """JobTransitionError should contain from and to status."""
        try:
            JobStateMachine.validate_transition(JobStatus.COMPLETE, JobStatus.IN_PROGRESS)
        except JobTransitionError as e:
            assert e.from_status == "complete"
            assert e.to_status == "in_progress"
            assert "complete" in str(e)
            assert "in_progress" in str(e)
