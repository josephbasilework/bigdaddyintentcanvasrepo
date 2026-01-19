"""Pytest configuration and shared fixtures for API tests."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI, testclient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models to register them with Base
import app.models.artifact  # noqa: F401
import app.models.audio_block  # noqa: F401
import app.models.backup  # noqa: F401
import app.models.canvas  # noqa: F401
import app.models.dashboard_subscription  # noqa: F401
import app.models.edge  # noqa: F401
import app.models.hook  # noqa: F401
import app.models.job  # noqa: F401
import app.models.node  # noqa: F401
import app.models.notification  # noqa: F401
import app.models.preferences  # noqa: F401
import app.models.session  # noqa: F401
import app.models.telemetry_event  # noqa: F401
import app.models.turn  # noqa: F401
from app.api.commands import router as commands_router
from app.api.edges import router as edges_router
from app.api.nodes import router as nodes_router
from app.api.notifications import router as notifications_router
from app.api.telemetry import router as telemetry_router
from app.api.workspace import router as workspace_router
from app.api.reminders import router as reminders_router
from app.database import Base, get_async_db, get_db


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
def async_engine_for_tests(test_db_file: str):
    """Create async engine for tests."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_file}")
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def async_session_maker(async_engine_for_tests):
    """Create async session factory for tests."""
    return async_sessionmaker(
        async_engine_for_tests,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
def db_session(sync_engine):
    """Get sync database session for tests."""
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
    session = session_local()
    yield session
    session.close()


@pytest.fixture
async def async_db(async_session_maker):
    """Get async database session for tests."""
    async with async_session_maker() as session:
        yield session


@pytest.fixture
def app_client(async_session_maker) -> testclient.TestClient:
    """Create test client with all API routers."""
    app = FastAPI()

    # Include all API routers
    app.include_router(commands_router)
    app.include_router(edges_router)
    app.include_router(nodes_router)
    app.include_router(notifications_router)
    app.include_router(reminders_router)
    app.include_router(telemetry_router)
    app.include_router(workspace_router)

    # Override database dependencies
    async def override_get_async_db():
        async with async_session_maker() as session:
            yield session

    def override_get_db():
        session_local = sessionmaker(autocommit=False, autoflush=False)
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_async_db] = override_get_async_db
    app.dependency_overrides[get_db] = override_get_db

    with testclient.TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
