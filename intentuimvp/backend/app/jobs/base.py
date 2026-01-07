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
    """Status of a job in the queue."""

    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(StrEnum):
    """Types of jobs supported by the system."""

    # Research jobs (Phase 1.5)
    DEEP_RESEARCH = "deep_research"
    PERSPECTIVE_GATHER = "perspective_gather"
    SYNTHESIS = "synthesis"

    # General async jobs
    EXPORT = "export"
    IMPORT = "import"

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
