"""Job progress tracking and WebSocket event streaming.

This module provides:
- Progress event types for real-time job updates
- Job progress tracker for database updates
- Integration with WebSocket manager for streaming
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models.job import Job
from app.ws.websocket import manager as ws_manager

logger = logging.getLogger(__name__)
settings = get_settings()


def _create_job_sync(
    job_id: str,
    job_type: str,
    user_id: str | None,
    workspace_id: str | None,
    parameters: str | None,
) -> Job:
    """Synchronous helper to create a job in the database."""
    db = SessionLocal()
    try:
        job = Job(
            job_id=job_id,
            user_id=user_id,
            workspace_id=workspace_id,
            job_type=job_type,
            status="queued",
            parameters=parameters,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def _update_progress_sync(
    job_id: str,
    progress_percent: float,
    current_step: str | None,
    step_number: int | None,
    steps_total: int | None,
) -> None:
    """Synchronous helper to update job progress in the database."""
    db = SessionLocal()
    try:
        job = db.execute(select(Job).where(Job.job_id == job_id)).scalar_one_or_none()
        if job:
            job.progress_percent = progress_percent
            job.current_step = current_step
            job.step_number = step_number
            job.steps_total = steps_total
            if job.status == "queued":
                job.status = "in_progress"
                job.started_at = datetime.now()
            db.commit()
    finally:
        db.close()


def _complete_job_sync(job_id: str, result_data: str | None) -> None:
    """Synchronous helper to mark a job as complete in the database."""
    db = SessionLocal()
    try:
        job = db.execute(select(Job).where(Job.job_id == job_id)).scalar_one_or_none()
        if job:
            job.status = "complete"
            job.progress_percent = 100.0
            job.completed_at = datetime.now()
            job.result_data = result_data
            db.commit()
    finally:
        db.close()


def _fail_job_sync(job_id: str, error_message: str) -> None:
    """Synchronous helper to mark a job as failed in the database."""
    db = SessionLocal()
    try:
        job = db.execute(select(Job).where(Job.job_id == job_id)).scalar_one_or_none()
        if job:
            job.status = "failed"
            job.completed_at = datetime.now()
            job.error_message = error_message
            db.commit()
    finally:
        db.close()


def _cancel_job_sync(job_id: str) -> None:
    """Synchronous helper to mark a job as cancelled in the database."""
    db = SessionLocal()
    try:
        job = db.execute(select(Job).where(Job.job_id == job_id)).scalar_one_or_none()
        if job:
            job.status = "cancelled"
            job.completed_at = datetime.now()
            db.commit()
    finally:
        db.close()


def _get_job_sync(job_id: str) -> Job | None:
    """Synchronous helper to get a job from the database."""
    db = SessionLocal()
    try:
        return db.execute(select(Job).where(Job.job_id == job_id)).scalar_one_or_none()
    finally:
        db.close()


def _get_user_jobs_sync(user_id: str, status: str | None, limit: int) -> list[Job]:
    """Synchronous helper to get user jobs from the database."""
    db = SessionLocal()
    try:
        query = select(Job).where(Job.user_id == user_id)
        if status:
            query = query.where(Job.status == status)
        query = query.order_by(Job.created_at.desc()).limit(limit)
        return list(db.scalars(query).all())
    finally:
        db.close()


class ProgressEventType(StrEnum):
    """Types of progress events for WebSocket streaming."""

    QUEUED = "job_queued"
    STARTED = "job_started"
    PROGRESS = "job_progress"
    COMPLETE = "job_complete"
    FAILED = "job_failed"
    CANCELLED = "job_cancelled"


@dataclass
class ProgressEvent:
    """A progress event for WebSocket streaming.

    Attributes:
        event_type: Type of progress event (queued, started, progress, complete, failed, cancelled)
        job_id: Unique identifier for the job
        job_type: Type of job (deep_research, perspective_gather, etc.)
        status: Current job status
        progress_percent: Progress percentage (0-100)
        current_step: Description of current step
        steps_total: Total number of steps
        step_number: Current step number (1-indexed)
        data: Additional event data (e.g., result, error)
        timestamp: Event timestamp
    """

    event_type: ProgressEventType
    job_id: str
    job_type: str
    status: str
    progress_percent: float = 0.0
    current_step: str | None = None
    steps_total: int | None = None
    step_number: int | None = None
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str | None = None

    def to_json(self) -> str:
        """Convert event to JSON string for WebSocket transmission."""
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

        return json.dumps(
            {
                "type": self.event_type,
                "job_id": self.job_id,
                "job_type": self.job_type,
                "status": self.status,
                "progress_percent": self.progress_percent,
                "current_step": self.current_step,
                "steps_total": self.steps_total,
                "step_number": self.step_number,
                "data": self.data,
                "timestamp": self.timestamp,
            }
        )


class JobProgressTracker:
    """Tracks job progress and emits WebSocket events.

    This class provides a singleton instance for managing job progress updates
    across the application. It handles:
    - Database updates for job progress
    - WebSocket event broadcasting
    - Per-job and per-user subscriptions
    """

    _instance: "JobProgressTracker | None" = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> "JobProgressTracker":
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the progress tracker (only once)."""
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        # Track which connections are subscribed to which jobs
        # Format: {job_id: set([user_id1, user_id2, ...])}
        self._job_subscriptions: dict[str, set[str]] = {}

    async def create_job(
        self,
        job_id: str,
        job_type: str,
        user_id: str | None = None,
        workspace_id: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> Job:
        """Create a new job in the database and emit queued event."""
        parameters_json = json.dumps(parameters) if parameters else None
        job = await asyncio.to_thread(
            _create_job_sync, job_id, job_type, user_id, workspace_id, parameters_json
        )

        # Emit queued event
        await self.emit_event(
            ProgressEvent(
                event_type=ProgressEventType.QUEUED,
                job_id=job_id,
                job_type=job_type,
                status="queued",
                data={"parameters": parameters} if parameters else {},
            )
        )

        logger.info(f"Job {job_id} created and queued")
        return job

    async def update_progress(
        self,
        job_id: str,
        progress_percent: float,
        current_step: str | None = None,
        step_number: int | None = None,
        steps_total: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Update job progress and emit progress event."""
        await asyncio.to_thread(
            _update_progress_sync, job_id, progress_percent, current_step, step_number, steps_total
        )

        # Get job for event emission
        job = await asyncio.to_thread(_get_job_sync, job_id)
        if job:
            await self.emit_event(
                ProgressEvent(
                    event_type=ProgressEventType.PROGRESS,
                    job_id=job_id,
                    job_type=job.job_type,
                    status=job.status,
                    progress_percent=progress_percent,
                    current_step=current_step,
                    step_number=step_number,
                    steps_total=steps_total,
                    data=data or {},
                )
            )

    async def complete_job(
        self,
        job_id: str,
        result_data: dict[str, Any] | None = None,
    ) -> None:
        """Mark job as complete and emit completion event."""
        result_data_json = json.dumps(result_data) if result_data else None
        await asyncio.to_thread(_complete_job_sync, job_id, result_data_json)

        job = await asyncio.to_thread(_get_job_sync, job_id)
        if job:
            await self.emit_event(
                ProgressEvent(
                    event_type=ProgressEventType.COMPLETE,
                    job_id=job_id,
                    job_type=job.job_type,
                    status="complete",
                    progress_percent=100.0,
                    data={"result": result_data} if result_data else {},
                )
            )
            logger.info(f"Job {job_id} completed successfully")

    async def fail_job(
        self,
        job_id: str,
        error_message: str,
    ) -> None:
        """Mark job as failed and emit failure event."""
        await asyncio.to_thread(_fail_job_sync, job_id, error_message)

        job = await asyncio.to_thread(_get_job_sync, job_id)
        if job:
            await self.emit_event(
                ProgressEvent(
                    event_type=ProgressEventType.FAILED,
                    job_id=job_id,
                    job_type=job.job_type,
                    status="failed",
                    data={"error": error_message},
                )
            )
            logger.error(f"Job {job_id} failed: {error_message}")

    async def cancel_job(self, job_id: str) -> None:
        """Mark job as cancelled and emit cancellation event."""
        await asyncio.to_thread(_cancel_job_sync, job_id)

        job = await asyncio.to_thread(_get_job_sync, job_id)
        if job:
            await self.emit_event(
                ProgressEvent(
                    event_type=ProgressEventType.CANCELLED,
                    job_id=job_id,
                    job_type=job.job_type,
                    status="cancelled",
                )
            )
            logger.info(f"Job {job_id} cancelled")

    async def emit_event(self, event: ProgressEvent) -> None:
        """Emit a progress event to subscribed WebSocket connections."""
        event_json = event.to_json()
        logger.debug(f"Emitting event: {event.event_type} for job {event.job_id}")
        await ws_manager.broadcast(event_json)

    async def get_job(self, job_id: str) -> Job | None:
        """Get job by ID."""
        return await asyncio.to_thread(_get_job_sync, job_id)

    async def get_user_jobs(
        self,
        user_id: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Job]:
        """Get jobs for a user."""
        return await asyncio.to_thread(_get_user_jobs_sync, user_id, status, limit)


# Global singleton instance
progress_tracker = JobProgressTracker()
