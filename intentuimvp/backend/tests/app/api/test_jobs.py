"""Integration tests for jobs API endpoints.

Tests the perspective-analysis endpoint (FR-012: Multi-Judge Compute).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, testclient

from app.api import jobs


@pytest.fixture
def jobs_app() -> FastAPI:
    """Create a test FastAPI app with jobs router."""
    app = FastAPI()
    app.include_router(jobs.router)
    return app


@pytest.fixture
def client(jobs_app: FastAPI) -> testclient.TestClient:
    """Create test client for job endpoints."""
    return testclient.TestClient(jobs_app)


class TestPerspectiveAnalysisEndpoint:
    """Test suite for perspective-analysis endpoint (FR-012)."""

    def test_create_perspective_analysis_success(
        self,
        client: testclient.TestClient,
    ) -> None:
        """Test successfully creating a perspective analysis job."""
        mock_job_id = "test-job-uuid-1234"

        # Patch the function where it's imported in the api.jobs module
        with patch.object(
            jobs,
            "enqueue_perspective_analysis",
            new=AsyncMock(return_value=mock_job_id),
        ) as mock_enqueue:
            response = client.post(
                "/api/jobs/perspective-analysis?user_id=user-1",
                json={
                    "topic": "AI safety concerns",
                    "perspectives": ["skeptic", "advocate", "synthesizer"],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == mock_job_id
            assert data["topic"] == "AI safety concerns"
            assert data["perspectives"] == ["skeptic", "advocate", "synthesizer"]
            assert data["status"] == "queued"

            # Verify enqueue_perspective_analysis was called correctly
            mock_enqueue.assert_called_once_with(
                topic="AI safety concerns",
                perspectives=["skeptic", "advocate", "synthesizer"],
                user_id="user-1",
                workspace_id=None,
                input_refs=None,
            )

    def test_create_perspective_analysis_with_input_refs(
        self,
        client: testclient.TestClient,
    ) -> None:
        """Test creating a perspective analysis job with input_refs."""
        mock_job_id = "test-job-uuid-5678"

        with patch.object(
            jobs,
            "enqueue_perspective_analysis",
            new=AsyncMock(return_value=mock_job_id),
        ) as mock_enqueue:
            response = client.post(
                "/api/jobs/perspective-analysis?user_id=user-1&workspace_id=ws-1",
                json={
                    "topic": "Test topic",
                    "perspectives": ["technical", "business"],
                    "input_refs": [1, 2, 3],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == mock_job_id

            # Verify input_refs and workspace_id were passed
            mock_enqueue.assert_called_once_with(
                topic="Test topic",
                perspectives=["technical", "business"],
                user_id="user-1",
                workspace_id="ws-1",
                input_refs=[1, 2, 3],
            )

    def test_create_perspective_analysis_default_perspectives(
        self,
        client: testclient.TestClient,
    ) -> None:
        """Test that default perspectives are used when not provided."""
        mock_job_id = "test-job-uuid-9999"

        with patch.object(
            jobs,
            "enqueue_perspective_analysis",
            new=AsyncMock(return_value=mock_job_id),
        ) as mock_enqueue:
            response = client.post(
                "/api/jobs/perspective-analysis?user_id=user-1",
                json={"topic": "Test topic"},
            )

            assert response.status_code == 200
            # Default perspectives should be applied
            mock_enqueue.assert_called_once()
            call_kwargs = mock_enqueue.call_args.kwargs
            assert call_kwargs["perspectives"] == ["skeptic", "advocate", "synthesizer"]

    def test_create_perspective_analysis_enqueue_error(
        self,
        client: testclient.TestClient,
    ) -> None:
        """Test handling JobEnqueueError."""
        from app.jobs.client import JobEnqueueError

        with patch(
            "app.jobs.client.enqueue_perspective_analysis",
            new=AsyncMock(side_effect=JobEnqueueError("Queue is full")),
        ):
            response = client.post(
                "/api/jobs/perspective-analysis?user_id=user-1",
                json={"topic": "Test topic"},
            )

            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "Queue is full" in data["detail"]

    def test_create_perspective_analysis_unexpected_error(
        self,
        client: testclient.TestClient,
    ) -> None:
        """Test handling unexpected errors."""
        with patch(
            "app.jobs.client.enqueue_perspective_analysis",
            new=AsyncMock(side_effect=RuntimeError("Unexpected failure")),
        ):
            response = client.post(
                "/api/jobs/perspective-analysis?user_id=user-1",
                json={"topic": "Test topic"},
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Failed to enqueue perspective analysis job" in data["detail"]

    def test_create_perspective_analysis_missing_user_id(
        self,
        client: testclient.TestClient,
    ) -> None:
        """Test that missing user_id returns validation error."""
        response = client.post(
            "/api/jobs/perspective-analysis",  # Missing user_id query param
            json={"topic": "Test topic"},
        )

        assert response.status_code == 422  # Validation error

    def test_create_perspective_analysis_invalid_perspective(
        self,
        client: testclient.TestClient,
    ) -> None:
        """Test that invalid perspective types are still passed through."""
        # The API layer doesn't validate perspective types - it passes them through
        # to the job layer which handles validation
        mock_job_id = "test-job-uuid-0000"

        with patch.object(
            jobs,
            "enqueue_perspective_analysis",
            new=AsyncMock(return_value=mock_job_id),
        ) as mock_enqueue:
            response = client.post(
                "/api/jobs/perspective-analysis?user_id=user-1",
                json={
                    "topic": "Test topic",
                    "perspectives": ["invalid_perspective"],
                },
            )

            # The endpoint should accept the request and pass it to the job layer
            assert response.status_code == 200
            mock_enqueue.assert_called_once_with(
                topic="Test topic",
                perspectives=["invalid_perspective"],
                user_id="user-1",
                workspace_id=None,
                input_refs=None,
            )
