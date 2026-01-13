"""Tests for job lifecycle event logging.

Tests that the progress tracker emits structured job lifecycle events
as required by NFR-OBS-003: Job system lifecycle events, duration, outcomes.
"""

import logging

import pytest

from app.jobs.base import JobType
from app.jobs.progress import (
    progress_tracker,
)


@pytest.mark.asyncio
class TestJobLifecycleLogging:
    """Tests for job lifecycle event logging (NFR-OBS-003)."""

    async def test_job_queued_emits_lifecycle_event(self, caplog):
        """Test that job creation emits structured job_lifecycle event."""
        caplog.set_level(logging.INFO, logger="app.jobs.progress")

        job = await progress_tracker.create_job(
            job_id="test-job-queued",
            job_type=JobType.DEEP_RESEARCH,
            user_id="test-user",
            workspace_id="test-workspace",
            parameters={"query": "test query"},
        )

        assert job is not None
        assert job.job_id == "test-job-queued"

        # Find job_lifecycle event with status=queued
        lifecycle_logs = [
            record
            for record in caplog.records
            if getattr(record, "event", None) == "job_lifecycle"
            and getattr(record, "status", None) == "queued"
        ]
        assert len(lifecycle_logs) == 1
        log_entry = lifecycle_logs[0]
        assert log_entry.job_id == "test-job-queued"
        assert log_entry.job_type == JobType.DEEP_RESEARCH
        assert log_entry.user_id == "test-user"
        assert log_entry.workspace_id == "test-workspace"
        assert log_entry.correlation_id is not None

    async def test_job_progress_emits_lifecycle_event(self, caplog):
        """Test that job progress updates emit structured job_lifecycle events."""
        caplog.set_level(logging.INFO, logger="app.jobs.progress")

        # First create a job
        await progress_tracker.create_job(
            job_id="test-job-progress",
            job_type=JobType.PERSPECTIVE_GATHER,
            user_id="test-user",
            workspace_id="test-workspace",
        )

        # Clear previous logs
        caplog.clear()

        # Update progress
        await progress_tracker.update_progress(
            job_id="test-job-progress",
            progress_percent=50.0,
            current_step="Gathering technical perspective",
            step_number=1,
            steps_total=4,
        )

        # Find job_lifecycle event with progress update
        lifecycle_logs = [
            record
            for record in caplog.records
            if getattr(record, "event", None) == "job_lifecycle"
            and "progress" in record.getMessage().lower()
        ]
        assert len(lifecycle_logs) == 1
        log_entry = lifecycle_logs[0]
        assert log_entry.job_id == "test-job-progress"
        assert log_entry.job_type == JobType.PERSPECTIVE_GATHER
        assert log_entry.progress_percent == 50.0
        assert log_entry.current_step == "Gathering technical perspective"
        assert log_entry.step_number == 1
        assert log_entry.steps_total == 4
        assert log_entry.correlation_id is not None

    async def test_job_complete_emits_lifecycle_event_with_duration(self, caplog):
        """Test that job completion emits structured job_lifecycle event with duration."""
        caplog.set_level(logging.INFO, logger="app.jobs.progress")

        # Create a job
        await progress_tracker.create_job(
            job_id="test-job-complete",
            job_type=JobType.SYNTHESIS,
            user_id="test-user",
            workspace_id="test-workspace",
        )

        # Progress the job (queued -> in_progress transition needed before complete)
        await progress_tracker.update_progress(
            job_id="test-job-complete",
            progress_percent=50.0,
            current_step="Processing",
        )

        # Clear previous logs
        caplog.clear()

        # Complete the job
        result_data = {"synthesis": "test synthesis result"}
        await progress_tracker.complete_job(
            job_id="test-job-complete",
            result_data=result_data,
        )

        # Find job_lifecycle event with status=complete
        lifecycle_logs = [
            record
            for record in caplog.records
            if getattr(record, "event", None) == "job_lifecycle"
            and getattr(record, "status", None) == "complete"
        ]
        assert len(lifecycle_logs) == 1
        log_entry = lifecycle_logs[0]
        assert log_entry.job_id == "test-job-complete"
        assert log_entry.job_type == JobType.SYNTHESIS
        assert log_entry.status == "complete"
        assert log_entry.outcome == "success"
        assert log_entry.duration_ms is not None
        assert log_entry.duration_ms >= 0
        assert log_entry.correlation_id is not None

    async def test_job_failed_emits_lifecycle_event_with_duration(self, caplog):
        """Test that job failure emits structured job_lifecycle event with duration."""
        caplog.set_level(logging.INFO, logger="app.jobs.progress")

        # Create a job
        await progress_tracker.create_job(
            job_id="test-job-failed",
            job_type=JobType.PLANNER,
            user_id="test-user",
            workspace_id="test-workspace",
        )

        # Clear previous logs
        caplog.clear()

        # Fail the job
        await progress_tracker.fail_job(
            job_id="test-job-failed",
            error_message="Simulated planning failure",
        )

        # Find job_lifecycle event with status=failed
        lifecycle_logs = [
            record
            for record in caplog.records
            if getattr(record, "event", None) == "job_lifecycle"
            and getattr(record, "status", None) == "failed"
        ]
        assert len(lifecycle_logs) == 1
        log_entry = lifecycle_logs[0]
        assert log_entry.job_id == "test-job-failed"
        assert log_entry.job_type == JobType.PLANNER
        assert log_entry.status == "failed"
        assert log_entry.outcome == "failure"
        assert log_entry.error_message == "Simulated planning failure"
        assert log_entry.duration_ms is not None
        assert log_entry.duration_ms >= 0
        assert log_entry.correlation_id is not None

    async def test_job_cancelled_emits_lifecycle_event(self, caplog):
        """Test that job cancellation emits structured job_lifecycle event.

        Note: Jobs cancelled from queued state have no duration (never started).
        Jobs that started before cancellation will have duration_ms.
        """
        caplog.set_level(logging.INFO, logger="app.jobs.progress")

        # Create a job and progress it (so it has started_at)
        await progress_tracker.create_job(
            job_id="test-job-cancelled",
            job_type=JobType.TRANSCRIPTION,
            user_id="test-user",
            workspace_id="test-workspace",
        )

        # Progress the job to set started_at
        await progress_tracker.update_progress(
            job_id="test-job-cancelled",
            progress_percent=25.0,
            current_step="Starting transcription",
        )

        # Clear previous logs
        caplog.clear()

        # Cancel the job
        await progress_tracker.cancel_job(job_id="test-job-cancelled")

        # Find job_lifecycle event with status=cancelled
        lifecycle_logs = [
            record
            for record in caplog.records
            if getattr(record, "event", None) == "job_lifecycle"
            and getattr(record, "status", None) == "cancelled"
        ]
        assert len(lifecycle_logs) == 1
        log_entry = lifecycle_logs[0]
        assert log_entry.job_id == "test-job-cancelled"
        assert log_entry.job_type == JobType.TRANSCRIPTION
        assert log_entry.status == "cancelled"
        assert log_entry.outcome == "cancelled"
        # Job was progressed before cancellation, so it should have duration
        assert log_entry.duration_ms is not None
        assert log_entry.duration_ms >= 0
        assert log_entry.correlation_id is not None

    async def test_full_job_lifecycle_emits_all_events(self, caplog):
        """Test that a full job lifecycle emits all expected events in order."""
        caplog.set_level(logging.INFO, logger="app.jobs.progress")

        job_id = "test-job-full-lifecycle"

        # Create job
        await progress_tracker.create_job(
            job_id=job_id,
            job_type=JobType.DEEP_RESEARCH,
            user_id="test-user",
            workspace_id="test-workspace",
            parameters={"depth": 2},
        )

        # Update progress multiple times
        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=25.0,
            current_step="Gathering perspectives",
            step_number=1,
            steps_total=4,
        )

        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=75.0,
            current_step="Synthesizing results",
            step_number=3,
            steps_total=4,
        )

        # Complete job
        await progress_tracker.complete_job(
            job_id=job_id,
            result_data={"result": "test result"},
        )

        # Collect all job_lifecycle events
        lifecycle_logs = [
            record
            for record in caplog.records
            if getattr(record, "event", None) == "job_lifecycle"
        ]

        # Should have 4 events: queued, progress (x2), complete
        assert len(lifecycle_logs) >= 4

        # Verify event sequence
        events_by_status = {}
        for log in lifecycle_logs:
            status = getattr(log, "status", None)
            if status not in events_by_status:
                events_by_status[status] = []
            events_by_status[status].append(log)

        # Verify we got queued, progress, and complete events
        assert "queued" in events_by_status
        assert len(events_by_status["queued"]) == 1
        assert events_by_status["queued"][0].job_id == job_id

        # Progress events (we had 2 updates)
        assert "in_progress" in events_by_status
        assert len(events_by_status["in_progress"]) >= 2

        # Complete event
        assert "complete" in events_by_status
        assert len(events_by_status["complete"]) == 1
        complete_log = events_by_status["complete"][0]
        assert complete_log.job_id == job_id
        assert complete_log.duration_ms >= 0
        assert complete_log.outcome == "success"
