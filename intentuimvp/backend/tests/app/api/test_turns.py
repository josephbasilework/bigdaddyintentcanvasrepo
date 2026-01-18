"""Integration tests for turn query API endpoints."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI, testclient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.models.canvas  # noqa: F401
import app.models.edge  # noqa: F401
import app.models.node  # noqa: F401
import app.models.turn  # noqa: F401
from app.api.turns import router as turns_router
from app.database import Base, get_async_db
from app.models.turn import TurnActor, TurnType
from app.repositories.turn_repo import TurnRepository


@pytest.fixture
def test_db_file():
    """Create temporary file for test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sync_engine(test_db_file: str):
    """Create sync engine for test database setup."""
    engine = create_engine(
        f"sqlite:///{test_db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def async_engine(test_db_file: str):
    """Create async engine for turn API tests."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_file}")
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def sync_session_local(sync_engine):
    """Create sync session factory for test setup."""
    return sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


@pytest.fixture
def async_session_maker(async_engine):
    """Create async session factory for turn endpoints."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
def turns_app(async_session_maker) -> FastAPI:
    """Create a test FastAPI app with turns router."""
    app = FastAPI()
    app.include_router(turns_router)

    async def override_get_async_db():
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_async_db] = override_get_async_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(turns_app: FastAPI) -> testclient.TestClient:
    """Create test client for turn endpoints."""
    return testclient.TestClient(turns_app)


def seed_turns(sync_session_local) -> None:
    """Seed the database with sample turns."""
    with sync_session_local() as session:
        repo = TurnRepository(session)
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="Input 1",
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.SYSTEM,
            turn_type=TurnType.NODE_CREATED,
            summary="Node created",
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.AGENT,
            turn_type=TurnType.AGENT_RESPONSE,
            summary="Agent response",
            payload={"response_type": "acknowledgment"},
        )
        repo.create_turn(
            session_id="session-1",
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="Input 2",
        )


class TestTurnEndpoints:
    """Test suite for turn API endpoints."""

    def test_list_turns_filters(self, client: testclient.TestClient, sync_session_local) -> None:
        """Test filtering turns by actor and type."""
        seed_turns(sync_session_local)

        response = client.get("/api/turns?session_id=session-1&actor=user")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert all(turn["actor"] == "user" for turn in data["turns"])

        response = client.get("/api/turns?session_id=session-1&type=node_created")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["turns"][0]["type"] == "node_created"

    def test_list_turns_after_sequence(
        self, client: testclient.TestClient, sync_session_local
    ) -> None:
        """Test pagination using after_sequence."""
        seed_turns(sync_session_local)

        response = client.get("/api/turns?session_id=session-1&after_sequence=1&limit=1")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["turns"][0]["sequenceNumber"] == 2

    def test_list_turns_response_type(
        self, client: testclient.TestClient, sync_session_local
    ) -> None:
        """Response type is included when available."""
        seed_turns(sync_session_local)

        response = client.get("/api/turns?session_id=session-1&type=agent_response")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["turns"][0]["responseType"] == "acknowledgment"
