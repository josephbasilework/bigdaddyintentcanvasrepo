"""Job progress tracking and WebSocket event streaming.

This module provides:
- Progress event types for real-time job updates
- Job progress tracker for database updates with state machine validation
- Integration with WebSocket manager for streaming

Implements NFR-OBS-003: Job system lifecycle events, duration, outcomes
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
from app.jobs.base import JobStateMachine
from app.agui import JobProgressMessage
from app.logging_config import get_correlation_id
from app.models.job import Job
from app.models.turn import TurnActor, TurnType
from app.telemetry import emit_job_completed
from app.services.turns import log_turn_for_user_sync
from app.ws.websocket import manager as ws_manager

logger = logging.getLogger(__name__)
settings = get_settings()


def _log_job_turn_sync(
    job: Job,
    turn_type: TurnType,
    summary: str,
    payload: dict[str, Any],
) -> None:
    """Log a job-related turn using a standalone sync session."""
    db = SessionLocal()
    try:
        log_turn_for_user_sync(
            db,
            user_id=job.user_id,
            workspace_id=job.workspace_id,
            actor=TurnActor.SYSTEM,
            turn_type=turn_type,
            summary=summary,
            payload=payload,
        )
    finally:
        db.close()


async def _log_job_turn(
    job: Job,
    turn_type: TurnType,
    summary: str,
    payload: dict[str, Any],
) -> None:
    await asyncio.to_thread(_log_job_turn_sync, job, turn_type, summary, payload)


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
) -> tuple[Job | None, bool]:
    """Synchronous helper to update job progress in the database.

    Validates state transitions using JobStateMachine before updating status.
    """
    db = SessionLocal()
    try:
        job = db.execute(select(Job).where(Job.job_id == job_id)).scalar_one_or_none()
        started = False
        if job:
            job.progress_percent = progress_percent
            job.current_step = current_step
            job.step_number = step_number
            job.steps_total = steps_total
            if job.status == "queued":
                # Validate transition from queued to in_progress
                JobStateMachine.validate_transition(job.status, "in_progress")
                job.status = "in_progress"
                job.started_at = datetime.now()
                started = True
            elif job.status == "in_progress" and job.started_at is None:
                job.started_at = datetime.now()
                started = True
            db.commit()
            db.refresh(job)
            return job, started
        return None, False
    finally:
        db.close()


def _complete_job_sync(job_id: str, result_data: str | None) -> None:
    """Synchronous helper to mark a job as complete in the database.

    Validates state transition using JobStateMachine before updating status.
    """
    db = SessionLocal()
    try:
        job = db.execute(select(Job).where(Job.job_id == job_id)).scalar_one_or_none()
        if job:
            # Validate transition to complete
            JobStateMachine.validate_transition(job.status, "complete")
            job.status = "complete"
            job.progress_percent = 100.0
            job.completed_at = datetime.now()
            job.result_data = result_data
            db.commit()
    finally:
        db.close()


def _fail_job_sync(job_id: str, error_message: str) -> None:
    """Synchronous helper to mark a job as failed in the database.

    Validates state transition using JobStateMachine before updating status.

    Special case: If job is in 'queued' status, transition to 'in_progress' first
    since the worker has picked up the job and is executing it.
    """
    db = SessionLocal()
    try:
        job = db.execute(select(Job).where(Job.job_id == job_id)).scalar_one_or_none()
        if job:
            # If job is queued, it means worker picked it up but failed before
            # first progress update. Transition to in_progress first.
            if job.status == "queued":
                job.status = "in_progress"
                job.started_at = datetime.now()

            # Now validate and transition to failed
            JobStateMachine.validate_transition(job.status, "failed")
            job.status = "failed"
            job.completed_at = datetime.now()
            job.error_message = error_message
            db.commit()
    finally:
        db.close()


def _cancel_job_sync(job_id: str) -> None:
    """Synchronous helper to mark a job as cancelled in the database.

    Validates state transition using JobStateMachine before updating status.
    """
    db = SessionLocal()
    try:
        job = db.execute(select(Job).where(Job.job_id == job_id)).scalar_one_or_none()
        if job:
            # Validate transition to cancelled
            JobStateMachine.validate_transition(job.status, "cancelled")
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
        """Create a new job in the database and emit queued event.

        Implements NFR-OBS-003: Logs job lifecycle event (queued).
        """
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

        # Log job lifecycle event (NFR-OBS-003)
        logger.info(
            "Job queued",
            extra={
                "event": "job_lifecycle",
                "job_id": job_id,
                "job_type": job_type,
                "status": "queued",
                "user_id": user_id,
                "workspace_id": workspace_id,
                "correlation_id": get_correlation_id(),
            },
        )

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
        """Update job progress and emit progress event.

        Implements NFR-OBS-003: Logs job lifecycle event (progress).
        """
        job, started = await asyncio.to_thread(
            _update_progress_sync,
            job_id,
            progress_percent,
            current_step,
            step_number,
            steps_total,
        )

        if job:
            if started:
                await self.emit_event(
                    ProgressEvent(
                        event_type=ProgressEventType.STARTED,
                        job_id=job_id,
                        job_type=job.job_type,
                        status=job.status,
                        progress_percent=progress_percent,
                        current_step=current_step,
                        step_number=step_number,
                        steps_total=steps_total,
                    )
                )

                # Log job start (NFR-OBS-003)
                logger.info(
                    "Job started",
                    extra={
                        "event": "job_lifecycle",
                        "job_id": job_id,
                        "job_type": job.job_type,
                        "status": job.status,
                        "user_id": job.user_id,
                        "workspace_id": job.workspace_id,
                        "correlation_id": get_correlation_id(),
                    },
                )
                await _log_job_turn(
                    job,
                    TurnType.JOB_STARTED,
                    "Job started",
                    {
                        "job_id": job_id,
                        "job_type": job.job_type,
                        "status": job.status,
                        "progress_percent": progress_percent,
                        "current_step": current_step,
                        "step_number": step_number,
                        "steps_total": steps_total,
                    },
                )

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

            # Log job progress (NFR-OBS-003)
            logger.info(
                "Job progress updated",
                extra={
                    "event": "job_lifecycle",
                    "job_id": job_id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "progress_percent": progress_percent,
                    "current_step": current_step,
                    "step_number": step_number,
                    "steps_total": steps_total,
                    "correlation_id": get_correlation_id(),
                },
            )
            await _log_job_turn(
                job,
                TurnType.JOB_PROGRESS,
                "Job progress updated",
                {
                    "job_id": job_id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "progress_percent": progress_percent,
                    "current_step": current_step,
                    "step_number": step_number,
                    "steps_total": steps_total,
                    "data": data or {},
                },
            )

    async def complete_job(
        self,
        job_id: str,
        result_data: dict[str, Any] | None = None,
    ) -> None:
        """Mark job as complete and emit completion event.

        Implements NFR-OBS-003: Logs job lifecycle event (complete) with duration.
        """
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

            # Calculate job duration
            duration_ms = 0
            if job.started_at and job.completed_at:
                duration_ms = (job.completed_at - job.started_at).total_seconds() * 1000

            # Log job completion with duration (NFR-OBS-003)
            logger.info(
                "Job completed",
                extra={
                    "event": "job_lifecycle",
                    "job_id": job_id,
                    "job_type": job.job_type,
                    "status": "complete",
                    "duration_ms": round(duration_ms, 2) if duration_ms else None,
                    "outcome": "success",
                    "correlation_id": get_correlation_id(),
                },
            )
            await _log_job_turn(
                job,
                TurnType.JOB_COMPLETED,
                "Job completed",
                {
                    "job_id": job_id,
                    "job_type": job.job_type,
                    "status": "complete",
                    "result": result_data,
                },
            )

            # Emit telemetry event for Research Job Completion metric (JM-8)
            emit_job_completed(
                job_id=job_id,
                job_type=job.job_type,
                status="success",
                execution_duration_ms=int(duration_ms) if duration_ms else 0,
                user_id=job.user_id,
                correlation_id=get_correlation_id(),
            )

    async def fail_job(
        self,
        job_id: str,
        error_message: str,
    ) -> None:
        """Mark job as failed and emit failure event.

        Implements NFR-OBS-003: Logs job lifecycle event (failed) with duration.
        """
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

            # Calculate job duration
            duration_ms = 0
            if job.started_at and job.completed_at:
                duration_ms = (job.completed_at - job.started_at).total_seconds() * 1000

            # Log job failure with duration (NFR-OBS-003, NFR-OBS-005)
            logger.error(
                "Job failed",
                extra={
                    "event": "job_lifecycle",
                    "job_id": job_id,
                    "job_type": job.job_type,
                    "status": "failed",
                    "duration_ms": round(duration_ms, 2) if duration_ms else None,
                    "outcome": "failure",
                    "error_message": error_message,
                    "correlation_id": get_correlation_id(),
                },
            )
            await _log_job_turn(
                job,
                TurnType.JOB_FAILED,
                "Job failed",
                {
                    "job_id": job_id,
                    "job_type": job.job_type,
                    "status": "failed",
                    "error": error_message,
                },
            )

            # Emit telemetry event for Research Job Completion metric (JM-8)
            emit_job_completed(
                job_id=job_id,
                job_type=job.job_type,
                status="failed",
                execution_duration_ms=int(duration_ms) if duration_ms else 0,
                failure_reason=error_message[:500],  # Truncate long error messages
                user_id=job.user_id,
                correlation_id=get_correlation_id(),
            )

    async def cancel_job(self, job_id: str) -> None:
        """Mark job as cancelled and emit cancellation event.

        Implements NFR-OBS-003: Logs job lifecycle event (cancelled).
        """
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

            # Calculate job duration
            duration_ms = 0
            if job.started_at and job.completed_at:
                duration_ms = (job.completed_at - job.started_at).total_seconds() * 1000

            # Log job cancellation (NFR-OBS-003)
            logger.info(
                "Job cancelled",
                extra={
                    "event": "job_lifecycle",
                    "job_id": job_id,
                    "job_type": job.job_type,
                    "status": "cancelled",
                    "duration_ms": round(duration_ms, 2) if duration_ms else None,
                    "outcome": "cancelled",
                    "correlation_id": get_correlation_id(),
                },
            )

            # Emit telemetry event for Research Job Completion metric (JM-8)
            emit_job_completed(
                job_id=job_id,
                job_type=job.job_type,
                status="cancelled",
                execution_duration_ms=int(duration_ms) if duration_ms else 0,
                user_id=job.user_id,
                correlation_id=get_correlation_id(),
            )

    async def emit_event(self, event: ProgressEvent) -> None:
        """Emit a progress event to subscribed WebSocket connections."""
        if event.timestamp is None:
            event.timestamp = datetime.now().isoformat()

        payload = {
            "job_id": event.job_id,
            "job_type": event.job_type,
            "status": event.status,
            "progress_percent": event.progress_percent,
            "current_step": event.current_step,
            "step_number": event.step_number,
            "steps_total": event.steps_total,
            "data": event.data,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp,
        }
        logger.debug(f"Emitting event: {event.event_type} for job {event.job_id}")
        await ws_manager.broadcast_agui(JobProgressMessage(payload=payload))

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
