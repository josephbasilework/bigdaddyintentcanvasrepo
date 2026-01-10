"""Tests for context API endpoint."""

import pytest
from fastapi import FastAPI, testclient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.intent_decipherer import IntentClassification, IntentDecipheringResult
from app.api.context import get_decipherer
from app.api.context import router as context_router
from app.context.router import ContextRouter
from app.database import get_db
from app.models.intent import AssumptionResolutionDB
from app.models.intent import Base as IntentBase


class FakeIntentDecipherer:
    """Stub intent decipherer for API tests."""

    def __init__(self, result: IntentDecipheringResult) -> None:
        self.result = result
        self.confidence_threshold = 0.8

    async def decipher(self, text: str) -> IntentDecipheringResult:
        return self.result


def build_result(intent_name: str, confidence: float) -> IntentDecipheringResult:
    """Helper to create an IntentDecipheringResult for tests."""
    primary = IntentClassification(
        name=intent_name,
        confidence=confidence,
        description=f"{intent_name} intent",
    )
    return IntentDecipheringResult(
        primary_intent=primary,
        should_auto_execute=False,
        reasoning="LLM ok",
    )


def build_assumption_result() -> IntentDecipheringResult:
    """Helper to create an IntentDecipheringResult with assumptions."""
    primary = IntentClassification(
        name="research",
        confidence=0.82,
        description="Research a topic based on the request",
    )
    return IntentDecipheringResult(
        primary_intent=primary,
        alternative_intents=[
            IntentClassification(
                name="analyze",
                confidence=0.55,
                description="Analyze existing data for insights",
            )
        ],
        assumptions=[
            {
                "id": "assumption-1",
                "text": "Use last quarter's data",
                "confidence": 0.65,
                "category": "parameter",
                "explanation": "No timeframe specified",
            },
            {
                "id": "assumption-2",
                "text": "Deliver results as a summary",
                "confidence": 0.92,
                "category": "intent",
            },
        ],
        should_auto_execute=False,
        reasoning="Ambiguity requires confirmation of timeframe.",
    )


@pytest.fixture
def app(monkeypatch) -> FastAPI:
    """Create a test FastAPI app with the context router."""
    fake = FakeIntentDecipherer(result=build_result("chat", 0.5))
    router = ContextRouter(intent_decipherer=fake)
    monkeypatch.setattr("app.api.context.get_context_router", lambda: router)

    app = FastAPI()
    app.include_router(context_router)
    return app


@pytest.fixture
def client(app: FastAPI) -> testclient.TestClient:
    """Create a test client for the context endpoint."""
    return testclient.TestClient(app)


@pytest.fixture
def assumptions_db() -> sessionmaker:
    """Provide a shared in-memory database for assumption tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    IntentBase.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def assumptions_app(assumptions_db: sessionmaker) -> FastAPI:
    """Create a test app with overrides for assumption endpoints."""
    app = FastAPI()
    app.include_router(context_router)

    decipherer = FakeIntentDecipherer(result=build_assumption_result())

    def override_get_decipherer() -> FakeIntentDecipherer:
        return decipherer

    def override_get_db():
        db = assumptions_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_decipherer] = override_get_decipherer
    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
def assumptions_client(assumptions_app: FastAPI) -> testclient.TestClient:
    """Create a test client for assumption endpoints."""
    return testclient.TestClient(assumptions_app)


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
        """Test submitting plain text without slash command."""
        response = client.post(
            "/api/context",
            json={"text": "Hello, how are you?", "attachments": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["handler"] == "clarification_handler"
        assert data["confidence"] == 0.5
        assert data["status"] == "clarification_required"

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


class TestAssumptionEndpoints:
    """Test suite for assumption generation and resolution endpoints."""

    def test_generate_assumptions_returns_intent_and_alternatives(
        self, assumptions_client: testclient.TestClient
    ) -> None:
        response = assumptions_client.post(
            "/api/context/assumptions",
            json={"text": "Research quarterly performance"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "research"
        assert data["confidence"] == 0.82
        assert data["alternatives"][0]["name"] == "analyze"
        assert data["intent_description"] == "Research a topic based on the request"
        assert len(data["assumptions"]) == 1
        assert data["assumptions"][0]["id"] == "assumption-1"
        assert data["session_id"] is not None

    def test_resolve_assumption_persists_feedback(
        self,
        assumptions_client: testclient.TestClient,
        assumptions_db: sessionmaker,
    ) -> None:
        response = assumptions_client.post(
            "/api/context/assumptions/resolve",
            json={
                "assumption_id": "assumption-1",
                "action": "reject",
                "original_text": "Use last quarter's data",
                "category": "parameter",
                "feedback": "Need a specific date range",
                "session_id": "session-123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "reject"
        assert data["feedback"] == "Need a specific date range"
        assert "REJECTED" in data["final_text"]

        db = assumptions_db()
        try:
            record = (
                db.query(AssumptionResolutionDB)
                .filter(AssumptionResolutionDB.assumption_id == "assumption-1")
                .one()
            )
        finally:
            db.close()
        assert record.action == "reject"
        assert "Need a specific date range" in record.final_text
