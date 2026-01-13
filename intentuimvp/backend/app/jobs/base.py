"""Base job definitions and task registry for ARQ worker."""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class JobStatus(StrEnum):
    """Status of a job in the queue.

    The job lifecycle follows a state machine with enforced transitions.
    See JobStateMachine for valid transitions.
    """

    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobTransitionError(Exception):
    """Raised when an invalid job state transition is attempted."""

    def __init__(self, from_status: str, to_status: str, reason: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason
        message = f"Invalid job state transition: {from_status} -> {to_status}"
        if reason:
            message += f" ({reason})"
        super().__init__(message)


class JobStateMachine:
    """State machine for job status transitions.

    Enforces valid state transitions per PRD JI-002:
    "Job cannot transition from completed/failed to running"

    Valid transitions:
        pending     -> queued, cancelled
        queued      -> in_progress, cancelled
        in_progress -> complete, failed, cancelled
        complete    -> (terminal, no outgoing transitions)
        failed      -> (terminal, no outgoing transitions)
        cancelled   -> (terminal, no outgoing transitions)

    Example:
        >>> machine = JobStateMachine()
        >>> machine.transition("pending", "queued")  # Valid
        >>> machine.transition("queued", "in_progress")  # Valid
        >>> machine.transition("complete", "in_progress")  # Raises JobTransitionError
    """

    # Define valid state transitions: from_state -> set of valid to_states
    _VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
        JobStatus.PENDING: {JobStatus.QUEUED, JobStatus.CANCELLED},
        JobStatus.QUEUED: {JobStatus.IN_PROGRESS, JobStatus.CANCELLED},
        JobStatus.IN_PROGRESS: {JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED},
        # Terminal states have no outgoing transitions
        JobStatus.COMPLETE: set(),
        JobStatus.FAILED: set(),
        JobStatus.CANCELLED: set(),
    }

    # Terminal states (jobs cannot transition out of these)
    _TERMINAL_STATES: set[JobStatus] = {JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED}

    # Active states (jobs are currently being processed)
    _ACTIVE_STATES: set[JobStatus] = {JobStatus.IN_PROGRESS}

    # Pending states (jobs waiting to be processed)
    _PENDING_STATES: set[JobStatus] = {JobStatus.PENDING, JobStatus.QUEUED}

    @classmethod
    def validate_transition(cls, from_status: str | JobStatus, to_status: str | JobStatus) -> None:
        """Validate a job state transition.

        Args:
            from_status: Current job status
            to_status: Target job status

        Raises:
            JobTransitionError: If the transition is invalid

        Example:
            >>> JobStateMachine.validate_transition("queued", "in_progress")  # OK
            >>> JobStateMachine.validate_transition("complete", "in_progress")  # Raises
        """
        from_state = JobStatus(from_status) if isinstance(from_status, str) else from_status
        to_state = JobStatus(to_status) if isinstance(to_status, str) else to_status

        # Same state is always valid (idempotent transition)
        if from_state == to_state:
            return

        # Check if from_state is a known state
        if from_state not in cls._VALID_TRANSITIONS:
            raise JobTransitionError(
                from_status, to_status, f"Unknown from_state: {from_state}"
            )

        # Check if transition is allowed
        valid_targets = cls._VALID_TRANSITIONS[from_state]
        if to_state not in valid_targets:
            if from_state in cls._TERMINAL_STATES:
                reason = f"Cannot transition from terminal state {from_state}"
            else:
                reason = f"Allowed transitions from {from_state}: {valid_targets}"
            raise JobTransitionError(from_status, to_status, reason)

    @classmethod
    def can_transition(cls, from_status: str | JobStatus, to_status: str | JobStatus) -> bool:
        """Check if a transition is valid without raising an exception.

        Args:
            from_status: Current job status
            to_status: Target job status

        Returns:
            True if transition is valid, False otherwise
        """
        try:
            cls.validate_transition(from_status, to_status)
            return True
        except JobTransitionError:
            return False

    @classmethod
    def is_terminal(cls, status: str | JobStatus) -> bool:
        """Check if a status is a terminal state.

        Args:
            status: Job status to check

        Returns:
            True if status is terminal (no outgoing transitions)
        """
        state = JobStatus(status) if isinstance(status, str) else status
        return state in cls._TERMINAL_STATES

    @classmethod
    def is_active(cls, status: str | JobStatus) -> bool:
        """Check if a status is an active (running) state.

        Args:
            status: Job status to check

        Returns:
            True if status is active (job is currently running)
        """
        state = JobStatus(status) if isinstance(status, str) else status
        return state in cls._ACTIVE_STATES

    @classmethod
    def is_pending(cls, status: str | JobStatus) -> bool:
        """Check if a status is a pending (waiting) state.

        Args:
            status: Job status to check

        Returns:
            True if status is pending (job is waiting to be processed)
        """
        state = JobStatus(status) if isinstance(status, str) else status
        return state in cls._PENDING_STATES

    @classmethod
    def get_valid_transitions(cls, from_status: str | JobStatus) -> set[JobStatus]:
        """Get all valid target states from a given status.

        Args:
            from_status: Current job status

        Returns:
            Set of valid target statuses
        """
        state = JobStatus(from_status) if isinstance(from_status, str) else from_status
        return cls._VALID_TRANSITIONS.get(state, set()).copy()


class JobType(StrEnum):
    """Types of jobs supported by the system."""

    # Research jobs (Phase 1.5)
    DEEP_RESEARCH = "deep_research"
    PERSPECTIVE_GATHER = "perspective_gather"
    SYNTHESIS = "synthesis"

    # General async jobs
    EXPORT = "export"
    IMPORT = "import"
    TRANSCRIPTION = "transcription"

    # Planning jobs (Phase 5)
    PLANNER = "planner"

    # Placeholder for future job types
    CUSTOM = "custom"


@dataclass
class JobResult:
    """Result of a job execution.

    Attributes:
        success: Whether the job completed successfully
        data: Result data (if successful)
        error: Error message (if failed)
        metadata: Additional metadata about the job
    """

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobContext:
    """Context passed to job functions.

    Attributes:
        job_id: Unique identifier for the job
        job_type: Type of job being executed
        user_id: User who initiated the job
        workspace_id: Workspace context for the job
    """

    job_id: str
    job_type: JobType
    user_id: str | None = None
    workspace_id: str | None = None


def get_redis_settings() -> RedisSettings:
    """Get ARQ Redis settings from application config.

    Returns:
        RedisSettings configured from environment variables.
    """
    return RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.redis_db,
        password=settings.redis_password or None,
    )


async def get_redis_pool():
    """Get or create a Redis connection pool for ARQ.

    Returns:
        ARQ Redis pool connection.
    """
    return await create_pool(get_redis_settings())
