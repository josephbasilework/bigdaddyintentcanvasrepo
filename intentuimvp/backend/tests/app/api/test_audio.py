"""Integration tests for audio block API endpoints."""

import asyncio
import base64
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, testclient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models to register them with Base
import app.models.audio_block  # noqa: F401 - Side-effect import to register models
import app.models.canvas  # noqa: F401 - Side-effect import to register models
from app.api.audio import router as audio_router
from app.database import Base, get_async_db
from app.models.canvas import Canvas


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
    """Create async engine for audio API tests."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_file}")
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def sync_session_local(sync_engine):
    """Create sync session factory for test setup."""
    return sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


@pytest.fixture
def async_session_maker(async_engine):
    """Create async session factory for audio endpoints."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
def audio_app(async_session_maker) -> FastAPI:
    """Create a test FastAPI app with audio router."""
    app = FastAPI()
    app.include_router(audio_router)

    async def override_get_async_db():
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_async_db] = override_get_async_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(audio_app: FastAPI) -> testclient.TestClient:
    """Create test client for audio endpoints."""
    return testclient.TestClient(audio_app)


def create_canvas(sync_session_local, name: str = "Test Canvas") -> int:
    """Create a canvas and return its ID."""
    with sync_session_local() as session:
        canvas = Canvas(user_id="default_user", name=name)
        session.add(canvas)
        session.commit()
        session.refresh(canvas)
        return canvas.id


def create_test_audio_data() -> str:
    """Create base64-encoded test audio data."""
    # Create a minimal WAV file (1 second of silence)
    wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt "
    wav_fmt = b"\x10\x00\x00\x00\x01\x00\x01\x00\x44\xAC\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00"
    wav_data = b"data\x00\x00\x00\x00" + b"\x00" * 36
    wav_bytes = wav_header + wav_fmt + wav_data
    return base64.b64encode(wav_bytes).decode("utf-8")


class TestAudioBlockEndpoints:
    """Test suite for audio block API endpoints."""

    def test_create_and_get_audio_block_with_data(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test creating an audio block with base64 data and retrieving it."""
        canvas_id = create_canvas(sync_session_local)
        audio_data = create_test_audio_data()

        payload = {
            "canvas_id": canvas_id,
            "audio_data": audio_data,
            "duration": 1.0,
        }
        response = client.post("/api/audio/blocks", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["canvasId"] == canvas_id
        assert data["status"] == "ready"
        assert data["duration"] == 1.0
        assert data["audioUri"]  # Should be a file path
        assert "created_at" in data
        assert "updated_at" in data

        block_id = data["id"]
        get_response = client.get(f"/api/audio/blocks/{block_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["id"] == block_id
        assert get_data["canvasId"] == canvas_id

    def test_create_audio_block_with_uri(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test creating an audio block with a pre-existing URI."""
        canvas_id = create_canvas(sync_session_local)

        payload = {
            "canvas_id": canvas_id,
            "audio_uri": "https://example.com/audio/recording.webm",
            "duration": 5.5,
        }
        response = client.post("/api/audio/blocks", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["canvasId"] == canvas_id
        assert data["audioUri"] == "https://example.com/audio/recording.webm"
        assert data["duration"] == 5.5

    def test_create_audio_block_neither_data_nor_uri(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test creating an audio block without audio_data or audio_uri returns 400."""
        canvas_id = create_canvas(sync_session_local)

        payload = {
            "canvas_id": canvas_id,
        }
        response = client.post("/api/audio/blocks", json=payload)
        assert response.status_code == 400

    def test_update_audio_block_transcription(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test updating audio block transcription."""
        canvas_id = create_canvas(sync_session_local)
        audio_data = create_test_audio_data()

        create_payload = {
            "canvas_id": canvas_id,
            "audio_data": audio_data,
        }
        create_response = client.post("/api/audio/blocks", json=create_payload)
        assert create_response.status_code == 201
        block_id = create_response.json()["id"]

        update_payload = {
            "transcription": "This is a test transcription.",
        }
        update_response = client.put(f"/api/audio/blocks/{block_id}", json=update_payload)
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["transcription"] == "This is a test transcription."

    def test_update_audio_block_status(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test updating audio block status."""
        canvas_id = create_canvas(sync_session_local)
        audio_data = create_test_audio_data()

        create_payload = {
            "canvas_id": canvas_id,
            "audio_data": audio_data,
        }
        create_response = client.post("/api/audio/blocks", json=create_payload)
        assert create_response.status_code == 201
        block_id = create_response.json()["id"]

        update_payload = {
            "status": "transcribing",
        }
        update_response = client.put(f"/api/audio/blocks/{block_id}", json=update_payload)
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["status"] == "transcribing"

    def test_update_audio_block_empty_payload(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test updating an audio block with no fields returns 400."""
        canvas_id = create_canvas(sync_session_local)
        audio_data = create_test_audio_data()

        response = client.post(
            "/api/audio/blocks",
            json={"canvas_id": canvas_id, "audio_data": audio_data},
        )
        block_id = response.json()["id"]

        update_response = client.put(f"/api/audio/blocks/{block_id}", json={})
        assert update_response.status_code == 400

    def test_list_audio_blocks_by_canvas(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test listing audio blocks filtered by canvas ID."""
        canvas_id = create_canvas(sync_session_local, name="Canvas A")
        other_canvas_id = create_canvas(sync_session_local, name="Canvas B")
        audio_data = create_test_audio_data()

        # Create blocks on first canvas
        for _ in range(2):
            response = client.post(
                "/api/audio/blocks",
                json={"canvas_id": canvas_id, "audio_data": audio_data},
            )
            assert response.status_code == 201

        # Create block on second canvas
        response = client.post(
            "/api/audio/blocks",
            json={"canvas_id": other_canvas_id, "audio_data": audio_data},
        )
        assert response.status_code == 201

        list_response = client.get(f"/api/audio/blocks?canvas_id={canvas_id}")
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data["count"] == 2
        assert all(block["canvasId"] == canvas_id for block in list_data["audio_blocks"])

    def test_delete_audio_block(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test deleting an audio block."""
        canvas_id = create_canvas(sync_session_local)
        audio_data = create_test_audio_data()

        response = client.post(
            "/api/audio/blocks",
            json={"canvas_id": canvas_id, "audio_data": audio_data},
        )
        assert response.status_code == 201
        block_id = response.json()["id"]

        delete_response = client.delete(f"/api/audio/blocks/{block_id}")
        assert delete_response.status_code == 204

        get_response = client.get(f"/api/audio/blocks/{block_id}")
        assert get_response.status_code == 404

    def test_get_audio_block_content(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test retrieving audio content for playback."""
        canvas_id = create_canvas(sync_session_local)
        audio_data = create_test_audio_data()

        response = client.post(
            "/api/audio/blocks",
            json={"canvas_id": canvas_id, "audio_data": audio_data},
        )
        assert response.status_code == 201
        block_id = response.json()["id"]

        content_response = client.get(f"/api/audio/blocks/{block_id}/content")
        assert content_response.status_code == 200
        assert content_response.content
        assert content_response.headers["content-type"].startswith("audio/")

    def test_transcribe_audio_block(
        self,
        client: testclient.TestClient,
        sync_session_local,
    ) -> None:
        """Test enqueuing transcription for an audio block."""
        canvas_id = create_canvas(sync_session_local)
        audio_data = create_test_audio_data()

        response = client.post(
            "/api/audio/blocks",
            json={"canvas_id": canvas_id, "audio_data": audio_data},
        )
        assert response.status_code == 201
        block_id = response.json()["id"]

        with patch("app.api.audio.JobService") as mock_service:
            mock_service.return_value.enqueue_transcription = AsyncMock(
                return_value="job-123"
            )
            transcribe_response = client.post(f"/api/audio/blocks/{block_id}/transcribe")

        assert transcribe_response.status_code == 200
        data = transcribe_response.json()
        assert data["job_id"] == "job-123"
        assert data["status"] == "queued"

        refresh_response = client.get(f"/api/audio/blocks/{block_id}")
        assert refresh_response.status_code == 200
        assert refresh_response.json()["status"] == "transcribing"
