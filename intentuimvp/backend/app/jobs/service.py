"""JobService - Unified service layer for job queue operations.

This module provides the JobService class, which is the main interface for:
- Enqueuing jobs of all types
- Querying job status and progress
- Canceling and retrying jobs
- Getting queue statistics

The JobService wraps the lower-level client functions and progress tracker
into a cohesive, easy-to-use API.

WHERE: app/jobs/service.py
WHAT: JobService class - unified interface to ARQ job queue
HOW: Wraps enqueue functions, progress tracker, and ARQ client
WHY: Provides clean service layer for API endpoints and agent tools

Example:
    from app.jobs import JobService, JobType

    service = JobService()

    # Enqueue a deep research job
    job_id = await service.enqueue_job(
        job_type=JobType.DEEP_RESEARCH,
        job_data={"query": "What is AGI?", "depth": 3},
        user_id="user-123",
        workspace_id="workspace-456"
    )

    # Get job status
    job = await service.get_job(job_id)

    # Cancel a job
    await service.cancel_job(job_id)
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.jobs.base import JobType
from app.jobs.client import (
    cancel_job as client_cancel_job,
)
from app.jobs.client import (
    enqueue_deep_research,
    enqueue_export,
    enqueue_job,
    enqueue_perspective_gather,
    enqueue_synthesis,
    enqueue_transcription,
    retry_job,
)
from app.jobs.client import (
    get_job_status as client_get_job_status,
)
from app.jobs.client import (
    get_queue_stats as client_get_queue_stats,
)
from app.jobs.progress import progress_tracker

logger = logging.getLogger(__name__)


class JobService:
    """Unified service for job queue operations.

    Provides a high-level interface for managing background jobs processed
    by the ARQ worker. All job operations go through this service.

    Methods:
        - enqueue_job: Generic job enqueue
        - enqueue_deep_research: Enqueue deep research job
        - enqueue_perspective_gather: Enqueue perspective gathering job
        - enqueue_synthesis: Enqueue synthesis job
        - enqueue_export: Enqueue export job
        - get_job: Get job details from database
        - get_job_status: Get job status from Redis queue
        - get_user_jobs: List jobs for a user
        - cancel_job: Cancel a pending/running job
        - retry_job: Retry a failed job
        - get_queue_stats: Get queue statistics
    """

    async def enqueue_job(
        self,
        job_type: JobType,
        job_data: dict[str, Any],
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> str:
        """Enqueue a job for processing.

        Creates the job in the database (via progress_tracker) and enqueues
        it to ARQ for processing by the worker.

        Args:
            job_type: Type of job to enqueue
            job_data: Data to pass to the job function
            user_id: Optional user ID for the job context
            workspace_id: Optional workspace ID for the job context

        Returns:
            Job ID (UUID) that can be used to track the job

        Raises:
            JobEnqueueError: If the job fails to enqueue

        Example:
            ```python
            service = JobService()
            job_id = await service.enqueue_job(
                job_type=JobType.DEEP_RESEARCH,
                job_data={"query": "What is the future of AI?", "depth": 3},
                user_id="user-123"
            )
            ```
        """
        job_id = await enqueue_job(job_type, job_data, user_id, workspace_id)
        logger.info(f"JobService: Enqueued job {job_id} of type {job_type}")
        return job_id

    async def enqueue_deep_research(
        self,
        query: str,
        depth: int = 3,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> str:
        """Enqueue a deep research job.

        Conducts multi-perspective research with web search and LLM-as-judge synthesis.

        Args:
            query: Research query to investigate
            depth: Research depth (1-5, default 3)
            user_id: Optional user ID
            workspace_id: Optional workspace ID

        Returns:
            Job ID

        Example:
            ```python
            service = JobService()
            job_id = await service.enqueue_deep_research(
                query="What are the implications of AGI?",
                depth=3,
                user_id="user-123"
            )
            ```
        """
        job_id = await enqueue_deep_research(query, depth, user_id, workspace_id)
        logger.info(f"JobService: Enqueued deep research job {job_id}")
        return job_id

    async def enqueue_perspective_gather(
        self,
        query: str,
        perspectives: list[str],
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> str:
        """Enqueue a perspective gathering job.

        Conducts focused analysis from specified analytical perspectives.

        Args:
            query: Research query
            perspectives: List of perspectives to gather (e.g., ["technical", "business"])
            user_id: Optional user ID
            workspace_id: Optional workspace ID

        Returns:
            Job ID

        Example:
            ```python
            service = JobService()
            job_id = await service.enqueue_perspective_gather(
                query="Should we adopt microservices?",
                perspectives=["technical", "business", "user"],
                user_id="user-123"
            )
            ```
        """
        job_id = await enqueue_perspective_gather(query, perspectives, user_id, workspace_id)
        logger.info(f"JobService: Enqueued perspective gather job {job_id}")
        return job_id

    async def enqueue_synthesis(
        self,
        query: str,
        perspective_results: list[dict[str, Any]],
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> str:
        """Enqueue a synthesis job.

        Uses Judge Agent to evaluate, score, and synthesize results from
        multiple perspective analyses.

        Args:
            query: Original research query
            perspective_results: Results from perspective gathering jobs
            user_id: Optional user ID
            workspace_id: Optional workspace ID

        Returns:
            Job ID

        Example:
            ```python
            service = JobService()
            job_id = await service.enqueue_synthesis(
                query="What is the best architecture?",
                perspective_results=[
                    {"name": "technical", "analysis": "..."},
                    {"name": "business", "analysis": "..."}
                ],
                user_id="user-123"
            )
            ```
        """
        job_id = await enqueue_synthesis(query, perspective_results, user_id, workspace_id)
        logger.info(f"JobService: Enqueued synthesis job {job_id}")
        return job_id

    async def enqueue_export(
        self,
        workspace_id: str,
        export_format: str = "json",
        user_id: str | None = None,
    ) -> str:
        """Enqueue an export job.

        Exports a workspace to a file.

        Args:
            workspace_id: Workspace to export
            export_format: Export format (json, csv, etc.)
            user_id: Optional user ID

        Returns:
            Job ID

        Example:
            ```python
            service = JobService()
            job_id = await service.enqueue_export(
                workspace_id="workspace-456",
                export_format="json",
                user_id="user-123"
            )
            ```
        """
        job_id = await enqueue_export(workspace_id, export_format, user_id)
        logger.info(f"JobService: Enqueued export job {job_id}")
        return job_id

    async def enqueue_transcription(
        self,
        audio_block_id: int,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> str:
        """Enqueue a transcription job.

        Transcribes audio content from an audio block.

        Args:
            audio_block_id: Audio block to transcribe
            user_id: Optional user ID
            workspace_id: Optional workspace ID

        Returns:
            Job ID

        Example:
            ```python
            service = JobService()
            job_id = await service.enqueue_transcription(
                audio_block_id=123,
                user_id="user-123"
            )
            ```
        """
        job_id = await enqueue_transcription(audio_block_id, user_id, workspace_id)
        logger.info(f"JobService: Enqueued transcription job {job_id}")
        return job_id

    async def get_job(self, job_id: str):
        """Get job details from the database.

        Returns the full job record with current status, progress, and results.

        Args:
            job_id: Job ID to look up

        Returns:
            Job model instance or None if not found

        Example:
            ```python
            service = JobService()
            job = await service.get_job("abc-123-def")
            if job:
                print(f"Status: {job.status}, Progress: {job.progress_percent}%")
            ```
        """
        return await progress_tracker.get_job(job_id)

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get job status from the Redis queue.

        Returns ARQ queue status (different from database status).

        Args:
            job_id: Job ID to check

        Returns:
            Job status dict or None if not found

        Example:
            ```python
            service = JobService()
            status = await service.get_job_status("abc-123-def")
            if status:
                print(f"Queue status: {status['status']}")
            ```
        """
        return await client_get_job_status(job_id)

    async def get_user_jobs(
        self,
        user_id: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list:
        """List jobs for a user.

        Args:
            user_id: User ID to filter jobs
            status: Optional status filter (pending, queued, in_progress, complete, failed, cancelled)
            limit: Maximum number of jobs to return (default 100)

        Returns:
            List of Job model instances

        Example:
            ```python
            service = JobService()
            jobs = await service.get_user_jobs(
                user_id="user-123",
                status="in_progress",
                limit=10
            )
            ```
        """
        return await progress_tracker.get_user_jobs(user_id=user_id, status=status, limit=limit)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or in-progress job.

        Marks the job as cancelled in the database and removes from queue.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancelled successfully, False otherwise

        Example:
            ```python
            service = JobService()
            success = await service.cancel_job("abc-123-def")
            if success:
                print("Job cancelled successfully")
            ```
        """
        # First update database status
        await progress_tracker.cancel_job(job_id)
        # Then remove from queue
        result = await client_cancel_job(job_id)
        logger.info(f"JobService: Cancel job {job_id}, queue_removed={result}")
        return result

    async def retry_job(self, job_id: str) -> dict[str, Any]:
        """Retry a failed job.

        Re-enqueues a failed job with the same parameters.
        Creates a new job ID for the retry attempt.

        Args:
            job_id: Job ID to retry

        Returns:
            Dict with success status, new job ID, and message

        Raises:
            JobEnqueueError: If the job cannot be retried or fails to enqueue

        Example:
            ```python
            service = JobService()
            result = await service.retry_job("abc-123-def")
            if result["success"]:
                new_job_id = result["new_job_id"]
                print(f"Job re-enqueued as {new_job_id}")
            ```
        """
        result = await retry_job(job_id)
        logger.info(f"JobService: Retry job {job_id}, new_job_id={result.get('new_job_id')}")
        return result

    async def get_queue_stats(self) -> dict[str, Any]:
        """Get job queue statistics.

        Returns statistics about the current state of the job queue.

        Returns:
            Dict with queue statistics

        Example:
            ```python
            service = JobService()
            stats = await service.get_queue_stats()
            print(f"Queue length: {stats['queue_length']}")
            ```
        """
        stats = await client_get_queue_stats()
        logger.debug(f"JobService: Queue stats: {stats}")
        return stats

    async def health_check(self) -> dict[str, Any]:
        """Health check for the job service.

        Checks connectivity to Redis and reports queue status.

        Returns:
            Dict with health status

        Example:
            ```python
            service = JobService()
            health = await service.health_check()
            print(f"Healthy: {health['healthy']}")
            ```
        """
        try:
            stats = await self.get_queue_stats()
            return {
                "healthy": "error" not in stats,
                "timestamp": datetime.now(UTC).isoformat(),
                "queue_length": stats.get("queue_length", -1),
                "service": "JobService",
                "version": "1.0.0",
            }
        except Exception as e:
            logger.error(f"JobService health check failed: {e}")
            return {
                "healthy": False,
                "timestamp": datetime.now(UTC).isoformat(),
                "error": str(e),
                "service": "JobService",
                "version": "1.0.0",
            }


# Singleton instance for convenient access
_job_service: JobService | None = None


def get_job_service() -> JobService:
    """Get the singleton JobService instance.

    Returns:
        JobService instance

    Example:
        ```python
        from app.jobs.service import get_job_service

        service = get_job_service()
        job_id = await service.enqueue_deep_research("What is AGI?")
        ```
    """
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service
