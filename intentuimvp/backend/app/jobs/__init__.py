"""Job queue infrastructure using ARQ (Async Redis Queue).

This module provides:
- Job definitions and types
- ARQ worker for processing async jobs
- Client for enqueueing jobs
- Job status tracking

Example:
    ```python
    from app.jobs import enqueue_deep_research, JobType

    # Enqueue a deep research job
    job_id = await enqueue_deep_research(
        query="What is the future of AI?",
        depth=3,
        user_id="user-123"
    )
    ```
"""

from app.jobs.base import (
    JobContext,
    JobResult,
    JobStatus,
    JobType,
    get_redis_pool,
    get_redis_settings,
)
from app.jobs.client import (
    JobEnqueueError,
    cancel_job,
    enqueue_deep_research,
    enqueue_export,
    enqueue_job,
    enqueue_perspective_gather,
    enqueue_synthesis,
    get_job_status,
    get_queue_stats,
)
from app.jobs.worker import WorkerSettings

__all__ = [
    # Base types
    "JobContext",
    "JobResult",
    "JobStatus",
    "JobType",
    # Client functions
    "enqueue_job",
    "enqueue_deep_research",
    "enqueue_perspective_gather",
    "enqueue_synthesis",
    "enqueue_export",
    "get_job_status",
    "cancel_job",
    "get_queue_stats",
    "JobEnqueueError",
    # Worker and utilities
    "WorkerSettings",
    "get_redis_pool",
    "get_redis_settings",
]
