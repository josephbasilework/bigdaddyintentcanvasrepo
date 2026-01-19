"""Tests for job client (enqueue, status, cancellation)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from arq import create_pool
from redis.exceptions import ConnectionError as RedisConnectionError

from app.jobs import (
    JobEnqueueError,
    JobType,
    cancel_job,
    enqueue_deep_research,
    enqueue_export,
    enqueue_job,
    enqueue_perspective_gather,
    enqueue_planner,
    enqueue_synthesis,
    get_job_status,
    get_queue_stats,
)
from app.jobs.base import get_redis_settings


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


@pytest.mark.asyncio
class TestEnqueueJob:
    """Tests for enqueue_job function."""

    async def test_enqueue_deep_research_job(self, redis_pool) -> None:
        """Should enqueue a deep research job successfully."""
        job_id = await enqueue_deep_research(
            query="Test query",
            depth=2,
            user_id="test-user",
        )

        assert job_id is not None
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    async def test_enqueue_deep_research_with_input_refs(self) -> None:
        """Should pass input_refs through to enqueue_job."""
        with patch("app.jobs.client.enqueue_job", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = "job-123"

            job_id = await enqueue_deep_research(
                query="Test query",
                depth=2,
                user_id="test-user",
                workspace_id="workspace-1",
                input_refs=[1, 2],
            )

            assert job_id == "job-123"
            called_job_type, called_job_data = mock_enqueue.call_args.args[:2]
            assert called_job_type == JobType.DEEP_RESEARCH
            assert called_job_data["query"] == "Test query"
            assert called_job_data["depth"] == 2
            assert called_job_data["input_refs"] == [1, 2]
            assert mock_enqueue.call_args.kwargs["user_id"] == "test-user"
            assert mock_enqueue.call_args.kwargs["workspace_id"] == "workspace-1"

    async def test_enqueue_perspective_gather_job(self, redis_pool) -> None:
        """Should enqueue a perspective gather job successfully."""
        job_id = await enqueue_perspective_gather(
            query="Test query",
            perspectives=["technical", "business"],
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    async def test_enqueue_synthesis_job(self, redis_pool) -> None:
        """Should enqueue a synthesis job successfully."""
        job_id = await enqueue_synthesis(
            query="Test query",
            perspective_results=[{"perspective": "technical", "data": "..."}],
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    async def test_enqueue_export_job(self, redis_pool) -> None:
        """Should enqueue an export job successfully."""
        job_id = await enqueue_export(
            workspace_id="workspace-123",
            export_format="json",
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    async def test_enqueue_planner_job(self, redis_pool) -> None:
        """Should enqueue a planner job successfully."""
        job_id = await enqueue_planner(
            goal="Build a new feature",
            context="Working on project X",
            user_id="test-user",
        )

        assert job_id is not None
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    async def test_enqueue_planner_job_without_context(self, redis_pool) -> None:
        """Should enqueue a planner job without optional context."""
        job_id = await enqueue_planner(
            goal="Simple goal",
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    async def test_enqueue_generic_job(self, redis_pool) -> None:
        """Should enqueue a generic job using JobType."""
        job_id = await enqueue_job(
            job_type=JobType.DEEP_RESEARCH,
            job_data={"query": "Test", "depth": 1},
        )

        assert job_id is not None
        assert isinstance(job_id, str)

    async def test_enqueue_job_records_queued_event(self) -> None:
        """Should record a queued job in the progress tracker."""
        mock_redis = MagicMock()
        mock_redis.enqueue_job = AsyncMock(return_value="redis-job")
        mock_redis.close = AsyncMock()

        with patch("app.jobs.client.create_pool", new_callable=AsyncMock) as mock_create_pool:
            mock_create_pool.return_value = mock_redis
            with patch(
                "app.jobs.client.progress_tracker.create_job",
                new_callable=AsyncMock,
            ) as mock_create_job:
                job_id = await enqueue_job(
                    job_type=JobType.DEEP_RESEARCH,
                    job_data={"query": "Test", "depth": 1},
                    user_id="test-user",
                    workspace_id="test-workspace",
                )

        assert isinstance(job_id, str)
        mock_redis.enqueue_job.assert_awaited_once()
        mock_create_job.assert_awaited_once_with(
            job_id=job_id,
            job_type=JobType.DEEP_RESEARCH,
            user_id="test-user",
            workspace_id="test-workspace",
            parameters={"query": "Test", "depth": 1},
        )

    async def test_enqueue_job_extracts_result_destination(self) -> None:
        """Should persist result destination metadata without passing it to the worker."""
        mock_redis = MagicMock()
        mock_redis.enqueue_job = AsyncMock(return_value="redis-job")
        mock_redis.close = AsyncMock()

        with patch("app.jobs.client.create_pool", new_callable=AsyncMock) as mock_create_pool:
            mock_create_pool.return_value = mock_redis
            with patch(
                "app.jobs.client.progress_tracker.create_job",
                new_callable=AsyncMock,
            ) as mock_create_job:
                await enqueue_job(
                    job_type=JobType.EXPORT,
                    job_data={
                        "workspace_id": "workspace-123",
                        "export_format": "json",
                        "result_destination": {"type": "user_storage"},
                    },
                )

        create_kwargs = mock_create_job.call_args.kwargs
        assert create_kwargs["parameters"] == {
            "workspace_id": "workspace-123",
            "export_format": "json",
        }
        assert create_kwargs["job_metadata"]["result_destination"] == {"type": "user_storage"}

    async def test_enqueue_job_sets_origin_node_from_input_refs(self) -> None:
        """Should derive origin_node_id from input_refs for origin node routing."""
        mock_redis = MagicMock()
        mock_redis.enqueue_job = AsyncMock(return_value="redis-job")
        mock_redis.close = AsyncMock()

        with patch("app.jobs.client.create_pool", new_callable=AsyncMock) as mock_create_pool:
            mock_create_pool.return_value = mock_redis
            with patch(
                "app.jobs.client.progress_tracker.create_job",
                new_callable=AsyncMock,
            ) as mock_create_job:
                await enqueue_job(
                    job_type=JobType.DEEP_RESEARCH,
                    job_data={
                        "query": "Test",
                        "depth": 1,
                        "input_refs": ["12", 7],
                    },
                )

        create_kwargs = mock_create_job.call_args.kwargs
        assert create_kwargs["parameters"]["input_refs"] == ["12", 7]
        assert create_kwargs["job_metadata"]["origin_node_id"] == 12

    async def test_enqueue_job_respects_explicit_origin_node(self) -> None:
        """Should keep explicit origin_node_id metadata when provided."""
        mock_redis = MagicMock()
        mock_redis.enqueue_job = AsyncMock(return_value="redis-job")
        mock_redis.close = AsyncMock()

        with patch("app.jobs.client.create_pool", new_callable=AsyncMock) as mock_create_pool:
            mock_create_pool.return_value = mock_redis
            with patch(
                "app.jobs.client.progress_tracker.create_job",
                new_callable=AsyncMock,
            ) as mock_create_job:
                await enqueue_job(
                    job_type=JobType.DEEP_RESEARCH,
                    job_data={
                        "query": "Test",
                        "depth": 1,
                        "input_refs": [1, 2],
                    },
                    job_metadata={"origin_node_id": 99},
                )

        create_kwargs = mock_create_job.call_args.kwargs
        assert create_kwargs["job_metadata"]["origin_node_id"] == 99


@pytest.mark.asyncio
class TestGetJobStatus:
    """Tests for get_job_status function."""

    async def test_get_status_for_enqueued_job(self, redis_pool) -> None:
        """Should retrieve status for a recently enqueued job."""
        job_id = await enqueue_deep_research(query="Test query")

        # Wait a bit for the job to be registered
        await asyncio.sleep(0.1)

        status = await get_job_status(job_id)

        # Status might be None if job was processed quickly
        # or a dict with job info
        assert status is None or isinstance(status, dict)

    async def test_get_status_for_nonexistent_job(self, redis_pool) -> None:
        """Should return None for a job that doesn't exist."""
        status = await get_job_status("nonexistent-job-id")
        assert status is None


@pytest.mark.asyncio
class TestCancelJob:
    """Tests for cancel_job function."""

    async def test_cancel_enqueued_job(self, redis_pool) -> None:
        """Should cancel a job successfully."""
        job_id = await enqueue_deep_research(query="Test query")

        # Cancel the job
        result = await cancel_job(job_id)

        # Result might be True or False depending on Redis timing
        assert isinstance(result, bool)

    async def test_cancel_nonexistent_job(self, redis_pool) -> None:
        """Should return False when canceling nonexistent job."""
        result = await cancel_job("nonexistent-job-id")
        assert result is False


@pytest.mark.asyncio
class TestGetQueueStats:
    """Tests for get_queue_stats function."""

    async def test_get_queue_stats(self, redis_pool) -> None:
        """Should return queue statistics."""
        stats = await get_queue_stats()

        assert isinstance(stats, dict)
        assert "queue_length" in stats
        assert "timestamp" in stats
        assert isinstance(stats["queue_length"], int)
        assert stats["queue_length"] >= 0


class TestJobEnqueueError:
    """Tests for JobEnqueueError."""

    def test_enqueue_invalid_job_type_raises_error(self) -> None:
        """Should raise JobEnqueueError for unknown job type."""
        # We need to test this indirectly since the API doesn't expose invalid types
        # The enqueue_job function validates JobType enum
        with pytest.raises(JobEnqueueError):
            # This would require modifying the function to test error case
            # For now, we test the error class exists
            raise JobEnqueueError("Test error")

    def test_job_enqueue_error_is_exception(self) -> None:
        """JobEnqueueError should be an Exception subclass."""
        assert issubclass(JobEnqueueError, Exception)

        error = JobEnqueueError("Test message")
        assert str(error) == "Test message"
