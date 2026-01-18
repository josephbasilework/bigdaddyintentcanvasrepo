"""Integration tests for attachment API endpoints."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI, testclient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models to register them with Base
import app.models.artifact  # noqa: F401 - Side-effect import to register models
import app.models.event  # noqa: F401 - Side-effect import to register models
import app.models.intent as intent_models  # noqa: F401 - Side-effect import to register models
import app.models.node  # noqa: F401 - Side-effect import to register models
import app.models.session  # noqa: F401 - Side-effect import to register models
import app.models.turn  # noqa: F401 - Side-effect import to register models
from app.api.attachments import router as attachments_router
from app.api.commands import router as commands_router
from app.database import Base, get_async_db, get_db
from app.models.intent import AttachmentDB


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
    intent_models.Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def async_engine(test_db_file: str):
    """Create async engine for attachment API tests."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_file}")
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def sync_session_local(sync_engine):
    """Create sync session factory for test setup."""
    return sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


@pytest.fixture
def async_session_maker(async_engine):
    """Create async session factory for attachment endpoints."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
def attachments_app(async_session_maker, sync_session_local) -> FastAPI:
    """Create a test FastAPI app with attachment router."""
    app = FastAPI()
    app.include_router(attachments_router)
    app.include_router(commands_router)

    async def override_get_async_db():
        async with async_session_maker() as session:
            yield session

    def override_get_db():
        db = sync_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_async_db] = override_get_async_db
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(attachments_app: FastAPI) -> testclient.TestClient:
    """Create test client for attachment endpoints."""
    return testclient.TestClient(attachments_app)


def _upload_text_file(client: testclient.TestClient) -> dict:
    payload = [("files", ("notes.txt", b"Hello from attachment", "text/plain"))]
    response = client.post("/api/attachments", files=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["count"] == 1
    return data["attachments"][0]


def test_upload_and_fetch_attachment(client: testclient.TestClient) -> None:
    """Uploading an attachment stores metadata and content."""
    attachment = _upload_text_file(client)
    attachment_id = attachment["id"]

    assert attachment["filename"] == "notes.txt"
    assert attachment["attachment_type"] == "document"
    assert attachment["text_preview"].startswith("Hello")
    assert attachment["content_url"]

    meta_response = client.get(f"/api/attachments/{attachment_id}")
    assert meta_response.status_code == 200
    meta = meta_response.json()
    assert meta["id"] == attachment_id
    assert meta["filename"] == "notes.txt"

    content_response = client.get(f"/api/attachments/{attachment_id}/content")
    assert content_response.status_code == 200
    assert content_response.content == b"Hello from attachment"


def test_upload_rejects_unknown_type(client: testclient.TestClient) -> None:
    """Unsupported file types are rejected."""
    payload = [("files", ("malware.exe", b"nope", "application/octet-stream"))]
    response = client.post("/api/attachments", files=payload)
    assert response.status_code == 400


def test_submit_command_links_attachment(
    client: testclient.TestClient,
    sync_session_local,
    monkeypatch,
) -> None:
    """Submitting a command links attachments to a turn."""
    monkeypatch.setattr("app.api.commands.enqueue_command", lambda submission: None)

    attachment = _upload_text_file(client)
    attachment_id = attachment["id"]

    response = client.post(
        "/api/commands",
        json={
            "command": "/research attachments",
            "attachments": [attachment_id],
            "session_id": "session-test",
        },
    )
    assert response.status_code == 202

    with sync_session_local() as session:
        row = session.query(AttachmentDB).filter(AttachmentDB.id == attachment_id).one()
        assert row.turn_id is not None
        assert row.session_id == "session-test"
