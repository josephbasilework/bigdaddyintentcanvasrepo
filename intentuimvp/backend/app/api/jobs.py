"""Job management API endpoints.

Provides REST endpoints for:
- Getting job status and details
- Listing user jobs
- Cancelling jobs
- Retrying failed jobs
- Getting job results
- Job artifact storage and retrieval
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.jobs.artifact_storage import (
    ArtifactMetadata,
    StoredArtifact,
    get_artifact_storage,
)
from app.jobs.client import JobEnqueueError, enqueue_doc_generation, retry_job
from app.jobs.progress import progress_tracker
from app.models.artifact import ArtifactType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Create async engine for artifact operations
_settings = get_settings()
# Convert sqlite:// to sqlite+aiosqlite:// for async support
_db_url = _settings.database_url
if _db_url.startswith("sqlite://"):
    _db_url = _db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

_async_engine = create_async_engine(_db_url)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session for artifact operations.

    Yields:
        AsyncSession: SQLAlchemy async session
    """
    async_session_maker = async_sessionmaker(
        bind=_async_engine, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session


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


class RetryJobResponse(BaseModel):
    """Retry job response model."""

    success: bool
    original_job_id: str
    new_job_id: str | None = None
    retry_count: int
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


@router.post("/{job_id}/retry", response_model=RetryJobResponse)
async def retry_job_endpoint(job_id: str) -> RetryJobResponse:
    """Retry a failed job.

    Re-enqueues a failed job with the same parameters.
    The job will have a new job ID for the retry attempt.

    Args:
        job_id: ARQ job ID (UUID string) to retry

    Returns:
        Success status, new job ID, and message

    Raises:
        HTTPException: If job not found (404) or cannot be retried (400)
    """
    job = await progress_tracker.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    try:
        result = await retry_job(job_id)
        return RetryJobResponse(**result)
    except JobEnqueueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
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


# Artifact endpoints

class ArtifactListResponse(BaseModel):
    """Artifact list response model."""

    artifacts: list[StoredArtifact]
    total: int


class CreateArtifactRequest(BaseModel):
    """Request model for creating an artifact."""

    metadata: ArtifactMetadata
    content: str  # Base64 encoded or direct string content


class CleanupResponse(BaseModel):
    """Response model for cleanup operations."""

    deleted_count: int
    artifacts: list[StoredArtifact]


@router.get("/{job_id}/artifacts", response_model=ArtifactListResponse)
async def list_job_artifacts(
    job_id: str,
    artifact_type: ArtifactType | None = Query(None, description="Filter by artifact type"),
    include_archived: bool = Query(False, description="Include archived artifacts"),
    db: AsyncSession = Depends(get_async_db),
) -> ArtifactListResponse:
    """List artifacts for a job.

    Args:
        job_id: ARQ job ID (UUID string)
        artifact_type: Optional filter by artifact type
        include_archived: Whether to include archived artifacts
        db: Database session

    Returns:
        List of artifacts for the job

    Raises:
        HTTPException: If job not found (404)
    """
    # Verify job exists
    job = await progress_tracker.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    storage = get_artifact_storage()
    artifacts = await storage.list_job_artifacts(
        db,
        job_id,
        artifact_type=artifact_type,
        include_archived=include_archived,
    )

    return ArtifactListResponse(artifacts=artifacts, total=len(artifacts))


@router.get("/artifacts/{artifact_id}", response_model=StoredArtifact)
async def get_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_async_db),
) -> StoredArtifact:
    """Get artifact metadata by ID.

    Args:
        artifact_id: The artifact ID
        db: Database session

    Returns:
        Artifact metadata

    Raises:
        HTTPException: If artifact not found (404)
    """
    storage = get_artifact_storage()
    artifact = await storage.get_artifact(db, artifact_id)

    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found",
        )

    return artifact


@router.get("/artifacts/{artifact_id}/content")
async def get_artifact_content(
    artifact_id: int,
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Get artifact content.

    Args:
        artifact_id: The artifact ID
        db: Database session

    Returns:
        Artifact content as file download or inline response

    Raises:
        HTTPException: If artifact not found (404)
    """
    storage = get_artifact_storage()
    result = await storage.get_artifact_content(db, artifact_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found",
        )

    artifact, content = result

    # Determine content type
    media_type = artifact.mime_type or "application/octet-stream"

    # Return as file download with proper headers
    return Response(
        content=content.encode("utf-8") if isinstance(content, str) else content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename or artifact.artifact_name}"',
        },
    )


@router.delete("/artifacts/{artifact_id}", response_model=dict)
async def delete_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """Delete an artifact.

    Args:
        artifact_id: The artifact ID
        db: Database session

    Returns:
        Success status

    Raises:
        HTTPException: If artifact not found (404)
    """
    storage = get_artifact_storage()
    success = await storage.delete_artifact(db, artifact_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found",
        )

    return {"success": True, "message": f"Artifact {artifact_id} deleted"}


@router.post("/artifacts/cleanup", response_model=CleanupResponse)
async def cleanup_artifacts(
    dry_run: bool = Query(False, description="If true, only report expired artifacts"),
    db: AsyncSession = Depends(get_async_db),
) -> CleanupResponse:
    """Cleanup expired artifacts.

    Deletes artifacts that have exceeded their archive_after_days TTL.

    Args:
        dry_run: If True, only report expired artifacts without deleting
        db: Database session

    Returns:
        Count and list of deleted artifacts
    """
    storage = get_artifact_storage()
    deleted = await storage.cleanup_expired_artifacts(db, dry_run=dry_run)

    return CleanupResponse(deleted_count=len(deleted), artifacts=deleted)


# Doc generation endpoints


class DocGenerationRequest(BaseModel):
    """Request model for doc generation."""

    source_job_id: str = Field(..., description="Job ID to generate documentation from")
    doc_format: str = Field(default="markdown", description="Output format (markdown, html, text)")
    include_metadata: bool = Field(default=True, description="Include timestamps and metadata")


class DocGenerationResponse(BaseModel):
    """Response model for doc generation."""

    job_id: str = Field(description="Doc generation job ID")
    source_job_id: str = Field(description="Source job ID")
    status: str = Field(description="Status of the doc generation job")


@router.post("/generate-doc", response_model=DocGenerationResponse)
async def generate_doc(
    request: DocGenerationRequest,
    user_id: str = Query(..., description="User ID for the job"),
    workspace_id: str | None = Query(None, description="Workspace ID for the job"),
) -> DocGenerationResponse:
    """Generate documentation from a job's artifacts.

    Creates a background job that generates structured documentation
    from the specified job's result artifacts.

    Args:
        request: Doc generation request parameters
        user_id: User ID for the job context
        workspace_id: Optional workspace ID for the job context

    Returns:
        Doc generation job ID for tracking

    Raises:
        HTTPException: If source job not found (404) or enqueue fails (400)
    """
    # Verify source job exists
    source_job = await progress_tracker.get_job(request.source_job_id)
    if not source_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source job {request.source_job_id} not found",
        )

    # Verify source job is complete
    if source_job.status != "complete":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source job must be complete, current status: {source_job.status}",
        )

    try:
        # Enqueue doc generation job
        doc_job_id = await enqueue_doc_generation(
            source_job_id=request.source_job_id,
            doc_format=request.doc_format,
            include_metadata=request.include_metadata,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        return DocGenerationResponse(
            job_id=doc_job_id,
            source_job_id=request.source_job_id,
            status="queued",
        )

    except Exception as e:
        logger.error(f"Failed to enqueue doc generation job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue doc generation job: {str(e)}",
        )


# Perspective Analysis endpoints (FR-012: Multi-Judge Compute)


class PerspectiveAnalysisRequest(BaseModel):
    """Request model for triggering perspective analysis (FR-012: Multi-Judge Compute)."""

    topic: str = Field(..., description="Topic to analyze from multiple perspectives")
    perspectives: list[str] = Field(
        default_factory=list,
        description="List of perspectives to analyze (e.g., skeptic, advocate, synthesizer)",
    )
    input_refs: list[int] | None = Field(
        default=None,
        description="Optional list of node IDs to link critic nodes to",
    )


class PerspectiveAnalysisResponse(BaseModel):
    """Response model for perspective analysis job."""

    job_id: str = Field(description="Perspective analysis job ID")
    topic: str = Field(description="Topic being analyzed")
    perspectives: list[str] = Field(description="Perspectives being analyzed")
    status: str = Field(description="Status of the perspective analysis job")


@router.post("/perspective-analysis", response_model=PerspectiveAnalysisResponse)
async def trigger_perspective_analysis(
    request: PerspectiveAnalysisRequest,
    user_id: str = Query(..., description="User ID for the job"),
    workspace_id: str | None = Query(None, description="Workspace ID for the job"),
) -> PerspectiveAnalysisResponse:
    """Trigger a perspective analysis job (FR-012: Multi-Judge Compute).

    This endpoint uses the PerspectiveAgent to analyze a topic from multiple perspectives
    (skeptic, advocate, synthesizer) and creates critic + synthesis nodes on the canvas.
    It supports rerunning with more compute by accepting custom perspective lists.

    Args:
        request: Perspective analysis request parameters
        user_id: User ID for the job context
        workspace_id: Optional workspace ID for the job context

    Returns:
        Perspective analysis job ID for tracking

    Raises:
        HTTPException: If enqueue fails (400) or server error (500)
    """
    from app.jobs.client import enqueue_perspective_gather

    # Default perspectives if none provided
    perspectives = request.perspectives or ["skeptic", "advocate", "synthesizer"]

    try:
        job_id = await enqueue_perspective_gather(
            query=request.topic,
            perspectives=perspectives,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        return PerspectiveAnalysisResponse(
            job_id=job_id,
            topic=request.topic,
            perspectives=perspectives,
            status="queued",
        )

    except Exception as e:
        logger.error(f"Failed to enqueue perspective analysis job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue perspective analysis job: {str(e)}",
        )
