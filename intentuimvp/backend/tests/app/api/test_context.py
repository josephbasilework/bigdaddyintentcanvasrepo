"""Tests for context API endpoint."""

import pytest
from fastapi import FastAPI, testclient

from app.api.context import router as context_router


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI app with the context router."""
    app = FastAPI()
    app.include_router(context_router)
    return app


@pytest.fixture
def client(app: FastAPI) -> testclient.TestClient:
    """Create a test client for the context endpoint."""
    return testclient.TestClient(app)


class TestContextEndpoint:
    """Test suite for POST /api/context endpoint."""

    def test_submit_context_slash_command(self, client: testclient.TestClient) -> None:
        """Test submitting context with slash command."""
        response = client.post(
            "/api/context",
            json={"text": "/help", "attachments": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["handler"] == "help_handler"
        assert data["confidence"] == 1.0
        assert data["status"] == "routed"
        assert "reason" in data

    def test_submit_context_research_command(self, client: testclient.TestClient) -> None:
        """Test submitting /research command."""
        response = client.post(
            "/api/context",
            json={"text": "/research AI trends", "attachments": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["handler"] == "research_handler"
        assert data["confidence"] == 1.0

    def test_submit_context_plain_text(self, client: testclient.TestClient) -> None:
        """Test submitting plain text without slash command.

        Now uses LLM classification (Intent Decipherer) by default.
        When LLM fails (no gateway available), falls back to chat_handler
        with confidence 0.5 from Intent Decipherer's fallback.
        """
        response = client.post(
            "/api/context",
            json={"text": "Hello, how are you?", "attachments": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["handler"] == "chat_handler"
        # LLM classification is enabled, confidence from Intent Decipherer
        assert data["confidence"] == 0.5
        assert data["status"] == "routed"

    def test_submit_context_with_attachments(self, client: testclient.TestClient) -> None:
        """Test submitting context with attachments."""
        response = client.post(
            "/api/context",
            json={"text": "/research", "attachments": ["file1.txt", "file2.pdf"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["handler"] == "research_handler"

    def test_submit_context_empty_text(self, client: testclient.TestClient) -> None:
        """Test submitting context with empty text returns 400."""
        response = client.post(
            "/api/context",
            json={"text": "", "attachments": []},
        )
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]

    def test_submit_context_whitespace_only(self, client: testclient.TestClient) -> None:
        """Test submitting context with only whitespace returns 400."""
        response = client.post(
            "/api/context",
            json={"text": "   ", "attachments": []},
        )
        assert response.status_code == 400

    def test_submit_context_missing_text(self, client: testclient.TestClient) -> None:
        """Test submitting context without text field returns 422."""
        response = client.post(
            "/api/context",
            json={"attachments": []},
        )
        assert response.status_code == 422

    def test_submit_context_exceeds_max_length(self, client: testclient.TestClient) -> None:
        """Test submitting context that exceeds max length returns 400."""
        long_text = "a" * 10001
        response = client.post(
            "/api/context",
            json={"text": long_text, "attachments": []},
        )
        assert response.status_code == 400
        assert "exceeds maximum length" in response.json()["detail"]

    def test_submit_context_unknown_slash_command(self, client: testclient.TestClient) -> None:
        """Test submitting unknown slash command routes to help."""
        response = client.post(
            "/api/context",
            json={"text": "/unknown", "attachments": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["handler"] == "help_handler"
        assert data["confidence"] == 0.5

    def test_submit_context_no_attachments(self, client: testclient.TestClient) -> None:
        """Test submitting context without attachments field (defaults to empty list)."""
        response = client.post(
            "/api/context",
            json={"text": "test"},
        )
        assert response.status_code == 200

    def test_submit_context_clear_command(self, client: testclient.TestClient) -> None:
        """Test submitting /clear command."""
        response = client.post(
            "/api/context",
            json={"text": "/clear", "attachments": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["handler"] == "clear_handler"
        assert data["confidence"] == 1.0
