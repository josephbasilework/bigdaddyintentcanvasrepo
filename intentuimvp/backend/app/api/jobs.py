"""Job management API endpoints.

Provides REST endpoints for:
- Getting job status and details
- Listing user jobs
- Cancelling jobs
- Getting job results
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.jobs.progress import progress_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# Response models
class JobResponse(BaseModel):
    """Job response model."""

    id: int
    job_id: str
    user_id: str | None
    workspace_id: str | None
    job_type: str
    status: str
    progress_percent: float
    current_step: str | None
    steps_total: int | None
    step_number: int | None
    parameters: str | None
    result_data: str | None
    error_message: str | None
    metadata: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    updated_at: str

    @classmethod
    def from_job(cls, job: Any) -> "JobResponse":
        """Create JobResponse from Job model."""
        job_dict = job.to_dict()
        return cls(**job_dict)


class JobListResponse(BaseModel):
    """Job list response model."""

    jobs: list[JobResponse]
    total: int


class CancelJobResponse(BaseModel):
    """Cancel job response model."""

    success: bool
    message: str


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    """Get job details by ID.

    Args:
        job_id: ARQ job ID (UUID string)

    Returns:
        Job details including current status and progress

    Raises:
        HTTPException: If job not found (404)
    """
    job = await progress_tracker.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return JobResponse.from_job(job)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    user_id: str = Query(..., description="User ID to filter jobs"),
    status: str | None = Query(None, description="Filter by job status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of jobs to return"),
) -> JobListResponse:
    """List jobs for a user.

    Args:
        user_id: User ID to filter jobs
        status: Optional status filter (pending, queued, in_progress, complete, failed, cancelled)
        limit: Maximum number of jobs to return (1-500, default 100)

    Returns:
        List of jobs for the user
    """
    jobs = await progress_tracker.get_user_jobs(user_id=user_id, status=status, limit=limit)
    return JobListResponse(
        jobs=[JobResponse.from_job(job) for job in jobs],
        total=len(jobs),
    )


@router.post("/{job_id}/cancel", response_model=CancelJobResponse)
async def cancel_job(job_id: str) -> CancelJobResponse:
    """Cancel a job.

    Args:
        job_id: ARQ job ID (UUID string)

    Returns:
        Success status and message

    Raises:
        HTTPException: If job not found (404)
    """
    job = await progress_tracker.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Check if job can be cancelled
    if job.status in ("complete", "failed", "cancelled"):
        return CancelJobResponse(
            success=False,
            message=f"Job cannot be cancelled (status: {job.status})",
        )

    await progress_tracker.cancel_job(job_id)
    return CancelJobResponse(
        success=True,
        message=f"Job {job_id} cancelled successfully",
    )


@router.get("/stats/queue")
async def get_queue_stats() -> dict[str, Any]:
    """Get job queue statistics.

    Returns:
        Queue statistics including counts by status
    """
    # This is a placeholder - would integrate with ARQ queue stats
    # For now, return empty stats
    return {
        "pending": 0,
        "queued": 0,
        "in_progress": 0,
        "complete": 0,
        "failed": 0,
        "cancelled": 0,
    }
