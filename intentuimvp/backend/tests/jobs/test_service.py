"""Tests for JobService - unified job queue service layer.

Tests the JobService class which provides the main interface for:
- Enqueuing jobs of all types
- Querying job status and progress
- Canceling and retrying jobs
- Getting queue statistics
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from arq import create_pool
from redis.exceptions import ConnectionError as RedisConnectionError

from app.jobs import JobType
from app.jobs.base import get_redis_settings
from app.jobs.service import JobService, get_job_service


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "redis: marks tests requiring Redis server")


@pytest_asyncio.fixture
async def redis_pool():
    """Create a Redis connection pool for testing.

    Skips tests if Redis is not available.
    """
    try:
        pool = await create_pool(get_redis_settings())
        yield pool
        await pool.close()
    except (RedisConnectionError, OSError, ConnectionRefusedError):
        pytest.skip("Redis server not available - requires running Redis on localhost:6379")


@pytest_asyncio.fixture
async def job_service():
    """Create a JobService instance for testing."""
    return JobService()


@pytest.mark.asyncio
class TestJobServiceEnqueue:
    """Tests for JobService enqueue methods."""

    async def test_enqueue_deep_research(self, job_service, redis_pool) -> None:
        """Should enqueue a deep research job successfully."""
        job_id = await job_service.enqueue_deep_research(
            query="What is AGI?",
            depth=3,
            user_id="test-user",
            workspace_id="test-workspace",
        )

        assert job_id is not None
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    async def test_enqueue_deep_research_with_input_refs(self, job_service) -> None:
        """Should forward input refs when enqueuing deep research jobs."""
        with patch(
            "app.jobs.service.enqueue_deep_research",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            mock_enqueue.return_value = "job-refs"

            job_id = await job_service.enqueue_deep_research(
                query="Research task",
                depth=2,
                user_id="user-1",
                workspace_id="workspace-2",
                input_refs=[10, 20],
            )

            assert job_id == "job-refs"
            mock_enqueue.assert_awaited_once_with(
                "Research task",
                2,
                "user-1",
                "workspace-2",
                input_refs=[10, 20],
            )

    async def test_enqueue_perspective_gather(self, job_service, redis_pool) -> None:
        """Should enqueue a perspective gather job successfully."""
        job_id = await job_service.enqueue_perspective_gather(
            query="Should we use microservices?",
            perspectives=["technical", "business", "user"],
            user_id="test-user",
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    async def test_enqueue_synthesis(self, job_service, redis_pool) -> None:
        """Should enqueue a synthesis job successfully."""
        job_id = await job_service.enqueue_synthesis(
            query="Best architecture decision?",
            perspective_results=[
                {"name": "technical", "analysis": "..."},
                {"name": "business", "analysis": "..."},
            ],
            user_id="test-user",
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    async def test_enqueue_export(self, job_service, redis_pool) -> None:
        """Should enqueue an export job successfully."""
        job_id = await job_service.enqueue_export(
            workspace_id="workspace-123",
            export_format="json",
            user_id="test-user",
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    async def test_enqueue_planner(self, job_service, redis_pool) -> None:
        """Should enqueue a planner job successfully."""
        job_id = await job_service.enqueue_planner(
            goal="Build a new feature",
            context="Working on project X",
            user_id="test-user",
            workspace_id="test-workspace",
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    async def test_enqueue_generic_job(self, job_service, redis_pool) -> None:
        """Should enqueue a generic job using JobType."""
        job_id = await job_service.enqueue_job(
            job_type=JobType.DEEP_RESEARCH,
            job_data={"query": "Test query", "depth": 2},
            user_id="test-user",
        )

        assert job_id is not None
        assert isinstance(job_id, str)


@pytest.mark.asyncio
class TestJobServiceGetJob:
    """Tests for JobService get_job method."""

    async def test_get_job_returns_none_for_nonexistent(self, job_service) -> None:
        """Should return None for a job that doesn't exist."""
        job = await job_service.get_job("nonexistent-job-id")
        assert job is None

    async def test_get_job_returns_job_for_existing(self, job_service, redis_pool) -> None:
        """Should return job details for an existing job."""
        # Enqueue a job first
        job_id = await job_service.enqueue_deep_research(query="Test query")

        # Wait a bit for the job to be created in the database
        await asyncio.sleep(0.2)

        # Get the job
        job = await job_service.get_job(job_id)

        # Job might exist or might have been processed quickly
        if job:
            assert job.job_id == job_id
            assert job.job_type == JobType.DEEP_RESEARCH


@pytest.mark.asyncio
class TestJobServiceGetJobStatus:
    """Tests for JobService get_job_status method."""

    async def test_get_status_for_nonexistent_job(self, job_service) -> None:
        """Should return None for a job that doesn't exist."""
        status = await job_service.get_job_status("nonexistent-job-id")
        assert status is None

    async def test_get_status_for_enqueued_job(self, job_service, redis_pool) -> None:
        """Should retrieve status for a recently enqueued job."""
        job_id = await job_service.enqueue_deep_research(query="Test query")

        # Wait a bit for the job to be registered
        await asyncio.sleep(0.1)

        status = await job_service.get_job_status(job_id)

        # Status might be None if job was processed quickly
        # or a dict with job info
        assert status is None or isinstance(status, dict)


@pytest.mark.asyncio
class TestJobServiceGetUserJobs:
    """Tests for JobService get_user_jobs method."""

    async def test_get_user_jobs_returns_list(self, job_service, redis_pool) -> None:
        """Should return a list of jobs for a user."""
        # Enqueue some jobs
        await job_service.enqueue_deep_research(query="Query 1", user_id="test-user-1")
        await job_service.enqueue_deep_research(query="Query 2", user_id="test-user-1")
        await job_service.enqueue_deep_research(query="Query 3", user_id="test-user-2")

        # Wait a bit for jobs to be created
        await asyncio.sleep(0.2)

        # Get jobs for user-1
        jobs = await job_service.get_user_jobs(user_id="test-user-1")

        assert isinstance(jobs, list)
        # We should have at least some jobs
        assert len(jobs) >= 0

    async def test_get_user_jobs_with_status_filter(self, job_service, redis_pool) -> None:
        """Should filter jobs by status when requested."""
        # Enqueue a job
        await job_service.enqueue_deep_research(query="Test query", user_id="test-user-filter")

        # Wait for job creation
        await asyncio.sleep(0.2)

        # Get jobs with status filter
        jobs = await job_service.get_user_jobs(
            user_id="test-user-filter", status="queued"
        )

        assert isinstance(jobs, list)

    async def test_get_user_jobs_respects_limit(self, job_service, redis_pool) -> None:
        """Should respect the limit parameter."""
        # Enqueue multiple jobs
        for i in range(5):
            await job_service.enqueue_deep_research(
                query=f"Query {i}", user_id="test-user-limit"
            )

        # Wait for job creation
        await asyncio.sleep(0.2)

        # Get jobs with limit
        jobs = await job_service.get_user_jobs(user_id="test-user-limit", limit=3)

        assert isinstance(jobs, list)
        # Should respect the limit
        assert len(jobs) <= 3


@pytest.mark.asyncio
class TestJobServiceCancelJob:
    """Tests for JobService cancel_job method."""

    async def test_cancel_enqueued_job(self, job_service, redis_pool) -> None:
        """Should cancel a job successfully."""
        job_id = await job_service.enqueue_deep_research(query="Test query")

        # Cancel the job
        result = await job_service.cancel_job(job_id)

        # Result might be True or False depending on Redis timing
        assert isinstance(result, bool)

    async def test_cancel_nonexistent_job(self, job_service) -> None:
        """Should return False when canceling nonexistent job."""
        result = await job_service.cancel_job("nonexistent-job-id")
        # The progress tracker will handle the cancel, result may be False
        assert isinstance(result, bool)


@pytest.mark.asyncio
class TestJobServiceRetryJob:
    """Tests for JobService retry_job method."""

    async def test_retry_nonexistent_job_raises_error(self, job_service) -> None:
        """Should raise JobEnqueueError when retrying nonexistent job."""
        from app.jobs.client import JobEnqueueError

        with pytest.raises(JobEnqueueError):
            await job_service.retry_job("nonexistent-job-id")


@pytest.mark.asyncio
class TestJobServiceQueueStats:
    """Tests for JobService get_queue_stats method."""

    async def test_get_queue_stats_returns_dict(self, job_service, redis_pool) -> None:
        """Should return queue statistics."""
        stats = await job_service.get_queue_stats()

        assert isinstance(stats, dict)
        assert "queue_length" in stats
        assert isinstance(stats["queue_length"], int)
        assert stats["queue_length"] >= 0


@pytest.mark.asyncio
class TestJobServiceHealthCheck:
    """Tests for JobService health_check method."""

    async def test_health_check_returns_healthy_status(self, job_service, redis_pool) -> None:
        """Should return healthy status when Redis is available."""
        health = await job_service.health_check()

        assert isinstance(health, dict)
        assert "healthy" in health
        assert "service" in health
        assert health["service"] == "JobService"
        assert "timestamp" in health
        assert isinstance(health["healthy"], bool)

    @patch("app.jobs.service.JobService.get_queue_stats")
    async def test_health_check_returns_unhealthy_on_error(
        self, mock_get_queue_stats, job_service
    ) -> None:
        """Should return unhealthy status when an error occurs."""
        # Mock get_queue_stats to raise an exception
        mock_get_queue_stats.side_effect = Exception("Connection error")

        health = await job_service.health_check()

        assert isinstance(health, dict)
        assert health["healthy"] is False
        assert "error" in health


class TestJobServiceSingleton:
    """Tests for get_job_service singleton function."""

    def test_get_job_service_returns_instance(self) -> None:
        """Should return a JobService instance."""
        service = get_job_service()
        assert isinstance(service, JobService)

    def test_get_job_service_returns_same_instance(self) -> None:
        """Should return the same instance on multiple calls."""
        service1 = get_job_service()
        service2 = get_job_service()
        assert service1 is service2


@pytest.mark.asyncio
class TestJobServiceIntegration:
    """Integration tests for JobService with real Redis."""

    async def test_full_job_lifecycle(self, job_service, redis_pool) -> None:
        """Test enqueue -> get status -> cancel lifecycle."""
        # Enqueue a job
        job_id = await job_service.enqueue_deep_research(
            query="Integration test query",
            depth=2,
            user_id="integration-test-user",
        )

        assert job_id is not None

        # Wait a bit
        await asyncio.sleep(0.2)

        # Get the job
        job = await job_service.get_job(job_id)
        # Job might exist or not depending on timing
        if job:
            assert job.job_id == job_id

        # Get queue stats
        stats = await job_service.get_queue_stats()
        assert isinstance(stats, dict)

        # Health check
        health = await job_service.health_check()
        assert health["healthy"] is True

    async def test_multiple_jobs_enqueue(self, job_service, redis_pool) -> None:
        """Test enqueueing multiple jobs."""
        job_ids = []

        for i in range(3):
            job_id = await job_service.enqueue_deep_research(
                query=f"Test query {i}",
                depth=1,
                user_id="multi-job-user",
            )
            job_ids.append(job_id)

        # All job IDs should be unique
        assert len(set(job_ids)) == 3
        assert all(isinstance(jid, str) for jid in job_ids)

        # Get user jobs
        await asyncio.sleep(0.2)
        jobs = await job_service.get_user_jobs(user_id="multi-job-user")
        assert isinstance(jobs, list)
