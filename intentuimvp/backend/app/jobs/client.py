"""Job client for enqueueing and managing jobs.

This module provides the interface for enqueueing jobs and checking their status.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from arq import create_pool

from app.jobs.base import JobType, get_redis_settings
from app.jobs.worker import (
    deep_research_job,
    export_job,
    perspective_gather_job,
    synthesis_job,
)

logger = logging.getLogger(__name__)


# Job function name mappings (for enqueue)
JOB_FUNCTIONS = {
    JobType.DEEP_RESEARCH: deep_research_job.__name__,
    JobType.PERSPECTIVE_GATHER: perspective_gather_job.__name__,
    JobType.SYNTHESIS: synthesis_job.__name__,
    JobType.EXPORT: export_job.__name__,
}


class JobEnqueueError(Exception):
    """Raised when a job fails to enqueue."""

    pass


async def enqueue_job(
    job_type: JobType,
    job_data: dict[str, Any],
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> str:
    """Enqueue a job for processing.

    Args:
        job_type: Type of job to enqueue
        job_data: Data to pass to the job function
        user_id: Optional user ID for the job context
        workspace_id: Optional workspace ID for the job context

    Returns:
        Job ID (UUID) that can be used to track the job

    Raises:
        JobEnqueueError: If the job fails to enqueue
    """
    job_id = str(uuid.uuid4())
    logger.info(f"Enqueueing job {job_id}: type={job_type}, data={job_data}")

    try:
        redis = await create_pool(get_redis_settings())

        function_name = JOB_FUNCTIONS.get(job_type)
        if not function_name:
            raise JobEnqueueError(f"Unknown job type: {job_type}")

        # Enqueue the job with ARQ
        job = await redis.enqueue_job(
            function_name,
            _job_id=job_id,
            _job_user_id=user_id,
            _job_workspace_id=workspace_id,
            **job_data,
        )

        await redis.close()
        logger.info(f"Job {job_id} enqueued successfully as {job}")
        return job_id

    except Exception as e:
        logger.error(f"Failed to enqueue job {job_id}: {e}")
        raise JobEnqueueError(f"Failed to enqueue job: {e}") from e


async def enqueue_deep_research(
    query: str,
    depth: int = 3,
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> str:
    """Enqueue a deep research job.

    Args:
        query: Research query
        depth: Research depth (1-5)
        user_id: Optional user ID
        workspace_id: Optional workspace ID

    Returns:
        Job ID
    """
    return await enqueue_job(
        JobType.DEEP_RESEARCH,
        {"query": query, "depth": depth},
        user_id=user_id,
        workspace_id=workspace_id,
    )


async def enqueue_perspective_gather(
    query: str,
    perspectives: list[str],
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> str:
    """Enqueue a perspective gathering job.

    Args:
        query: Research query
        perspectives: List of perspectives to gather
        user_id: Optional user ID
        workspace_id: Optional workspace ID

    Returns:
        Job ID
    """
    return await enqueue_job(
        JobType.PERSPECTIVE_GATHER,
        {"query": query, "perspectives": perspectives},
        user_id=user_id,
        workspace_id=workspace_id,
    )


async def enqueue_synthesis(
    query: str,
    perspective_results: list[dict[str, Any]],
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> str:
    """Enqueue a synthesis job.

    Args:
        query: Original research query
        perspective_results: Results from perspective gathering
        user_id: Optional user ID
        workspace_id: Optional workspace ID

    Returns:
        Job ID
    """
    return await enqueue_job(
        JobType.SYNTHESIS,
        {"query": query, "perspective_results": perspective_results},
        user_id=user_id,
        workspace_id=workspace_id,
    )


async def enqueue_export(
    workspace_id: str,
    export_format: str = "json",
    user_id: str | None = None,
) -> str:
    """Enqueue an export job.

    Args:
        workspace_id: Workspace to export
        export_format: Export format (json, csv, etc.)
        user_id: Optional user ID

    Returns:
        Job ID
    """
    return await enqueue_job(
        JobType.EXPORT,
        {"workspace_id": workspace_id, "export_format": export_format},
        user_id=user_id,
        workspace_id=workspace_id,
    )


async def get_job_status(job_id: str) -> dict[str, Any] | None:
    """Get the status of a job.

    Args:
        job_id: Job ID to check

    Returns:
        Job status dict or None if not found
    """
    try:
        redis = await create_pool(get_redis_settings())
        job_key = f"arq:job:{job_id}"
        job_data = await redis.hgetall(job_key)

        if not job_data:
            return None

        return {
            "job_id": job_id,
            "status": job_data.get(b"status", b"unknown").decode(),
            "function": job_data.get(b"function", b"unknown").decode(),
            "enqueue_time": job_data.get(b"enqueue_time", b"").decode(),
            "score": int(job_data.get(b"score", 0)),
        }

    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        return None
    finally:
        if "redis" in locals():
            await redis.close()


async def cancel_job(job_id: str) -> bool:
    """Cancel a pending or in-progress job.

    Args:
        job_id: Job ID to cancel

    Returns:
        True if cancelled successfully, False otherwise
    """
    try:
        redis = await create_pool(get_redis_settings())
        # ARQ doesn't have built-in cancellation, so we remove from queue
        job_key = f"arq:job:{job_id}"
        result = await redis.delete(job_key)
        await redis.close()
        return result > 0

    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        return False


async def get_queue_stats() -> dict[str, Any]:
    """Get statistics about the job queue.

    Returns:
        Dict with queue statistics
    """
    try:
        redis = await create_pool(get_redis_settings())
        queue_name = "intentui:jobs"
        queue_length = await redis.zcard(queue_name)
        await redis.close()

        return {
            "queue_length": queue_length,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        return {"queue_length": -1, "error": str(e)}
