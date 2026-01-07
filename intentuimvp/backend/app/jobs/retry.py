"""Job retry and recovery module.

Provides:
- Retry policy configuration (max attempts, backoff strategy)
- Failure detection and classification (transient vs permanent)
- Automatic retry logic with exponential backoff
- Recovery state preservation through checkpointing
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from functools import wraps
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.jobs.base import JobResult
from app.models.job import Job

logger = logging.getLogger(__name__)
settings = get_settings()


class FailureType(StrEnum):
    """Classification of failure types for retry decisions."""

    TRANSIENT = "transient"  # Temporary failures (network, rate limits, etc.)
    PERMANENT = "permanent"  # Permanent failures (invalid input, auth, etc.)
    UNKNOWN = "unknown"  # Unclassified failure


class BackoffStrategy(StrEnum):
    """Backoff strategies for retry attempts."""

    EXPONENTIAL = "exponential"  # Exponential backoff: 2^n * base_delay
    LINEAR = "linear"  # Linear backoff: n * base_delay
    FIXED = "fixed"  # Fixed delay: base_delay
    IMMEDIATE = "immediate"  # No delay between retries


@dataclass
class RetryPolicy:
    """Retry policy configuration for jobs.

    Attributes:
        max_attempts: Maximum number of retry attempts (default 3)
        backoff_strategy: Strategy for calculating retry delay
        base_delay: Base delay in seconds for backoff calculation
        max_delay: Maximum delay in seconds between retries
        retry_transient_only: If True, only retry transient failures
    """

    max_attempts: int = 3
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    retry_transient_only: bool = True

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay before next retry attempt.

        Args:
            attempt: Retry attempt number (1-indexed)

        Returns:
            Delay in seconds, capped at max_delay
        """
        if self.backoff_strategy == BackoffStrategy.IMMEDIATE:
            return 0.0
        elif self.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.base_delay
        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = attempt * self.base_delay
        else:  # EXPONENTIAL
            delay = (2 ** (attempt - 1)) * self.base_delay

        return min(delay, self.max_delay)

    def should_retry(self, attempt: int, failure_type: FailureType) -> bool:
        """Determine if a job should be retried.

        Args:
            attempt: Current retry attempt number
            failure_type: Type of failure that occurred

        Returns:
            True if job should be retried
        """
        if attempt > self.max_attempts:
            return False

        if self.retry_transient_only and failure_type == FailureType.PERMANENT:
            return False

        return True


# Default retry policies for different job types
DEFAULT_RETRY_POLICIES: dict[str, RetryPolicy] = {
    "deep_research": RetryPolicy(
        max_attempts=3,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        base_delay=2.0,
        max_delay=60.0,
        retry_transient_only=True,
    ),
    "perspective_gather": RetryPolicy(
        max_attempts=3,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        base_delay=1.0,
        max_delay=30.0,
        retry_transient_only=True,
    ),
    "synthesis": RetryPolicy(
        max_attempts=2,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        base_delay=2.0,
        max_delay=30.0,
        retry_transient_only=True,
    ),
    "export": RetryPolicy(
        max_attempts=2,
        backoff_strategy=BackoffStrategy.LINEAR,
        base_delay=5.0,
        max_delay=30.0,
        retry_transient_only=False,
    ),
}


class RetryableError(Exception):
    """Base exception for errors that can be retried."""

    def __init__(self, message: str, failure_type: FailureType = FailureType.TRANSIENT):
        self.failure_type = failure_type
        super().__init__(message)


class TransientError(RetryableError):
    """Exception for transient failures that should be retried."""

    def __init__(self, message: str):
        super().__init__(message, FailureType.TRANSIENT)


class PermanentError(RetryableError):
    """Exception for permanent failures that should not be retried."""

    def __init__(self, message: str):
        super().__init__(message, FailureType.PERMANENT)


def classify_exception(exc: Exception) -> FailureType:
    """Classify an exception as transient or permanent.

    Args:
        exc: Exception to classify

    Returns:
        FailureType classification
    """
    # Check if it's already a RetryableError
    if isinstance(exc, RetryableError):
        return exc.failure_type

    # Check for specific transient error patterns
    transient_patterns = [
        "timeout",
        "connection",
        "network",
        "rate limit",
        "temporary",
        "unavailable",
        "ECONNRESET",
        "ETIMEDOUT",
        "503",
        "502",
        "429",
    ]

    error_str = str(exc).lower()
    error_type = type(exc).__name__.lower()

    for pattern in transient_patterns:
        if pattern.lower() in error_str or pattern.lower() in error_type:
            return FailureType.TRANSIENT

    # Check for specific permanent error patterns
    permanent_patterns = [
        "authentication",
        "unauthorized",
        "forbidden",
        "not found",
        "invalid",
        "validation",
        "401",
        "403",
        "404",
        "422",
    ]

    for pattern in permanent_patterns:
        if pattern.lower() in error_str or pattern.lower() in error_type:
            return FailureType.PERMANENT

    # Default to unknown - conservative approach (may retry)
    return FailureType.UNKNOWN


@dataclass
class CheckpointState:
    """Checkpoint state for job recovery.

    Attributes:
        job_id: Job identifier
        step_name: Name of the step being checkpointed
        step_number: Current step number
        data: Checkpoint data for recovery
        timestamp: When checkpoint was created
    """

    job_id: str
    step_name: str
    step_number: int
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "step_name": self.step_name,
            "step_number": self.step_number,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointState":
        """Create CheckpointState from dictionary."""
        return cls(
            job_id=data["job_id"],
            step_name=data["step_name"],
            step_number=data["step_number"],
            data=data.get("data", {}),
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
        )


# Synchronous helper functions for checkpoint manager
def _save_checkpoint_sync(
    job_id: str, step_name: str, step_number: int, checkpoint: CheckpointState
) -> None:
    """Synchronous helper to save a checkpoint."""
    db = SessionLocal()
    try:
        result = db.execute(select(Job).where(Job.job_id == job_id))
        job = result.scalar_one_or_none()

        if job:
            metadata = {}
            if job.job_metadata:
                try:
                    metadata = json.loads(job.job_metadata)
                except json.JSONDecodeError:
                    pass

            metadata["last_checkpoint"] = checkpoint.to_dict()
            job.job_metadata = json.dumps(metadata)
            db.commit()
    finally:
        db.close()


def _load_checkpoint_sync(job_id: str) -> CheckpointState | None:
    """Synchronous helper to load a checkpoint."""
    db = SessionLocal()
    try:
        result = db.execute(select(Job).where(Job.job_id == job_id))
        job = result.scalar_one_or_none()

        if job and job.job_metadata:
            try:
                metadata = json.loads(job.job_metadata)
                checkpoint_data = metadata.get("last_checkpoint")
                if checkpoint_data:
                    return CheckpointState.from_dict(checkpoint_data)
            except (json.JSONDecodeError, KeyError):
                pass

        return None
    finally:
        db.close()


def _clear_checkpoint_sync(job_id: str) -> None:
    """Synchronous helper to clear a checkpoint."""
    db = SessionLocal()
    try:
        result = db.execute(select(Job).where(Job.job_id == job_id))
        job = result.scalar_one_or_none()

        if job and job.job_metadata:
            try:
                metadata = json.loads(job.job_metadata)
                metadata.pop("last_checkpoint", None)
                job.job_metadata = json.dumps(metadata)
                db.commit()
            except json.JSONDecodeError:
                pass
    finally:
        db.close()


class CheckpointManager:
    """Manager for job checkpoint state preservation.

    Stores checkpoint data in job_metadata field for recovery.
    """

    async def save_checkpoint(
        self,
        job_id: str,
        step_name: str,
        step_number: int,
        data: dict[str, Any],
    ) -> None:
        """Save a checkpoint for a job.

        Args:
            job_id: Job identifier
            step_name: Name of the step being checkpointed
            step_number: Current step number
            data: Checkpoint data for recovery
        """
        checkpoint = CheckpointState(
            job_id=job_id,
            step_name=step_name,
            step_number=step_number,
            data=data,
        )

        await asyncio.to_thread(
            _save_checkpoint_sync, job_id, step_name, step_number, checkpoint
        )
        logger.info(f"[{job_id}] Checkpoint saved: {step_name} (step {step_number})")

    async def load_checkpoint(self, job_id: str) -> CheckpointState | None:
        """Load the last checkpoint for a job.

        Args:
            job_id: Job identifier

        Returns:
            CheckpointState if found, None otherwise
        """
        return await asyncio.to_thread(_load_checkpoint_sync, job_id)

    async def clear_checkpoint(self, job_id: str) -> None:
        """Clear checkpoint data for a job.

        Args:
            job_id: Job identifier
        """
        await asyncio.to_thread(_clear_checkpoint_sync, job_id)
        logger.info(f"[{job_id}] Checkpoint cleared")


# Global checkpoint manager
checkpoint_manager = CheckpointManager()


async def execute_with_retry(
    job_id: str,
    job_type: str,
    func: Callable,
    retry_policy: RetryPolicy | None = None,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
) -> JobResult:
    """Execute a job function with automatic retry logic.

    Args:
        job_id: Job identifier
        job_type: Type of job (e.g., "deep_research")
        func: Async function to execute
        retry_policy: Optional retry policy (uses default if None)
        args: Positional arguments to pass to func
        kwargs: Keyword arguments to pass to func

    Returns:
        JobResult from function execution

    Raises:
        Exception: If all retries are exhausted
    """
    if kwargs is None:
        kwargs = {}

    policy = retry_policy or DEFAULT_RETRY_POLICIES.get(job_type, RetryPolicy())

    attempt = 0
    last_error: Exception | None = None

    while attempt < policy.max_attempts + 1:
        attempt += 1
        try:
            logger.info(f"[{job_id}] Executing attempt {attempt}/{policy.max_attempts + 1}")

            # Execute the function
            result = await func(*args, **kwargs)
            return result

        except Exception as e:
            last_error = e
            failure_type = classify_exception(e)

            logger.warning(
                f"[{job_id}] Attempt {attempt} failed: {e} (type: {failure_type})"
            )

            # Check if we should retry
            if attempt >= policy.max_attempts + 1:
                logger.error(f"[{job_id}] All retry attempts exhausted")
                raise

            if not policy.should_retry(attempt, failure_type):
                logger.info(f"[{job_id}] Not retrying: {failure_type} failure")
                raise

            # Calculate and apply delay
            delay = policy.calculate_delay(attempt)
            if delay > 0:
                logger.info(f"[{job_id}] Waiting {delay}s before retry...")
                await asyncio.sleep(delay)

    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected retry loop completion")


def with_retry(
    job_type: str,
    retry_policy: RetryPolicy | None = None,
) -> Callable:
    """Decorator to add retry logic to job functions.

    Args:
        job_type: Type of job (e.g., "deep_research")
        retry_policy: Optional retry policy (uses default if None)

    Returns:
        Decorated function with retry logic

    Example:
        @with_retry("deep_research")
        async def my_job(ctx: dict, query: str) -> JobResult:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> JobResult:
            # Extract job_id from context (first arg should be ctx dict)
            ctx = args[0] if args else {}
            job_id = ctx.get("job_id", "unknown")

            return await execute_with_retry(
                job_id=job_id,
                job_type=job_type,
                func=func,
                retry_policy=retry_policy,
                args=args,
                kwargs=kwargs,
            )

        return wrapper

    return decorator


async def get_job_retry_state(job_id: str) -> dict[str, Any] | None:
    """Get retry state information for a job.

    Args:
        job_id: Job identifier

    Returns:
        Dict with retry state or None if job not found
    """
    return await asyncio.to_thread(_get_job_retry_state_sync, job_id)


async def increment_job_retry_count(job_id: str) -> None:
    """Increment the retry count for a job.

    Args:
        job_id: Job identifier
    """
    await asyncio.to_thread(_increment_job_retry_count_sync, job_id)


# Synchronous helpers for retry state management
def _get_job_retry_state_sync(job_id: str) -> dict[str, Any] | None:
    """Synchronous helper to get retry state."""
    db = SessionLocal()
    try:
        result = db.execute(select(Job).where(Job.job_id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            return None

        retry_info = {
            "job_id": job_id,
            "status": job.status,
            "can_retry": False,
            "retry_count": 0,
            "max_attempts": 3,
        }

        if job.job_metadata:
            try:
                metadata = json.loads(job.job_metadata)
                retry_info["retry_count"] = metadata.get("retry_count", 0)
                retry_info["max_attempts"] = metadata.get("max_attempts", 3)
                retry_info["can_retry"] = (
                    job.status == "failed"
                    and retry_info["retry_count"] < retry_info["max_attempts"]
                )
            except json.JSONDecodeError:
                pass

        return retry_info
    finally:
        db.close()


def _increment_job_retry_count_sync(job_id: str) -> None:
    """Synchronous helper to increment retry count."""
    db = SessionLocal()
    try:
        result = db.execute(select(Job).where(Job.job_id == job_id))
        job = result.scalar_one_or_none()

        if job:
            metadata = {}
            if job.job_metadata:
                try:
                    metadata = json.loads(job.job_metadata)
                except json.JSONDecodeError:
                    pass

            metadata["retry_count"] = metadata.get("retry_count", 0) + 1
            job.job_metadata = json.dumps(metadata)
            db.commit()
            logger.info(f"[{job_id}] Retry count: {metadata['retry_count']}")
    finally:
        db.close()
