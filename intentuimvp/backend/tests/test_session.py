"""Unit tests for WorkspaceSession model and SessionRepository."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.canvas import Canvas
from app.models.session import WorkspaceSession, generate_session_id
from app.repositories.session_repo import SessionRepository


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(in_memory_db):
    """Create a database session for testing."""
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=in_memory_db)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_canvas(db_session: Session) -> Canvas:
    """Create a test canvas."""
    canvas = Canvas(user_id="test-user", name="Test Canvas")
    db_session.add(canvas)
    db_session.commit()
    db_session.refresh(canvas)
    return canvas


class TestGenerateSessionId:
    """Tests for session ID generation."""

    def test_generate_session_id_returns_uuid(self):
        """Test that generate_session_id returns a valid UUID string."""
        session_id = generate_session_id()
        assert session_id is not None
        assert isinstance(session_id, str)
        assert len(session_id) == 36  # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    def test_generate_session_id_unique(self):
        """Test that generated session IDs are unique."""
        ids = [generate_session_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique


class TestWorkspaceSessionModel:
    """Tests for WorkspaceSession model."""

    def test_create_session(self, db_session: Session, test_canvas: Canvas):
        """Test creating a workspace session."""
        session = WorkspaceSession(
            workspace_id=test_canvas.id,
            user_id="test-user",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.id is not None
        assert session.session_id is not None  # Auto-generated
        assert session.workspace_id == test_canvas.id
        assert session.user_id == "test-user"
        assert session.created_at is not None
        assert session.last_active_at is not None
        assert session.resumed_count == 0

    def test_session_id_unique(self, db_session: Session, test_canvas: Canvas):
        """Test that session_id is unique."""
        session1 = WorkspaceSession(
            workspace_id=test_canvas.id,
            user_id="test-user",
        )
        session2 = WorkspaceSession(
            workspace_id=test_canvas.id,
            user_id="test-user",
        )
        db_session.add(session1)
        db_session.add(session2)
        db_session.commit()

        assert session1.session_id != session2.session_id

    def test_session_to_dict(self, db_session: Session, test_canvas: Canvas):
        """Test session serialization to dictionary."""
        session = WorkspaceSession(
            workspace_id=test_canvas.id,
            user_id="test-user",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        result = session.to_dict()
        assert result["id"] == session.id
        assert result["sessionId"] == session.session_id
        assert result["workspaceId"] == test_canvas.id
        assert result["userId"] == "test-user"
        assert "createdAt" in result
        assert "lastActiveAt" in result
        assert result["resumedCount"] == 0

    def test_session_workspace_relationship(
        self, db_session: Session, test_canvas: Canvas
    ):
        """Test that session has a workspace relationship."""
        session = WorkspaceSession(
            workspace_id=test_canvas.id,
            user_id="test-user",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Session should reference the workspace
        assert session.workspace_id == test_canvas.id
        # Relationship should be accessible
        assert session.workspace is not None
        assert session.workspace.id == test_canvas.id


class TestSessionRepository:
    """Tests for SessionRepository."""

    def test_create_session(self, db_session: Session, test_canvas: Canvas):
        """Test creating a session via repository."""
        repo = SessionRepository(db_session)
        session = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )

        assert session.id is not None
        assert session.session_id is not None
        assert session.workspace_id == test_canvas.id
        assert session.user_id == "test-user"

    def test_create_session_with_custom_id(
        self, db_session: Session, test_canvas: Canvas
    ):
        """Test creating a session with a custom session_id."""
        repo = SessionRepository(db_session)
        custom_id = "custom-session-id-12345"
        session = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
            session_id=custom_id,
        )

        assert session.session_id == custom_id

    def test_get_by_session_id(self, db_session: Session, test_canvas: Canvas):
        """Test retrieving a session by session_id."""
        repo = SessionRepository(db_session)
        created = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )

        retrieved = repo.get_by_session_id(created.session_id)
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_by_session_id_not_found(self, db_session: Session):
        """Test that get_by_session_id returns None for nonexistent session."""
        repo = SessionRepository(db_session)
        result = repo.get_by_session_id("nonexistent-session-id")
        assert result is None

    def test_get_by_user_and_workspace(
        self, db_session: Session, test_canvas: Canvas
    ):
        """Test retrieving session by user and workspace."""
        repo = SessionRepository(db_session)
        created = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )

        retrieved = repo.get_by_user_and_workspace(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_resume_session(self, db_session: Session, test_canvas: Canvas):
        """Test resuming an existing session."""
        repo = SessionRepository(db_session)
        created = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )
        original_last_active = created.last_active_at

        # Simulate time passing (in tests, might be same timestamp)
        resumed = repo.resume_session(created.session_id, "test-user")

        assert resumed is not None
        assert resumed.id == created.id
        assert resumed.resumed_count == 1
        # last_active_at should be updated (might be same in fast tests)
        assert resumed.last_active_at >= original_last_active

    def test_resume_session_wrong_user(self, db_session: Session, test_canvas: Canvas):
        """Test that resume fails for wrong user."""
        repo = SessionRepository(db_session)
        created = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )

        # Try to resume as different user
        result = repo.resume_session(created.session_id, "other-user")
        assert result is None

    def test_resume_session_not_found(self, db_session: Session):
        """Test that resume returns None for nonexistent session."""
        repo = SessionRepository(db_session)
        result = repo.resume_session("nonexistent-session", "test-user")
        assert result is None

    def test_get_or_create_session_creates_new(
        self, db_session: Session, test_canvas: Canvas
    ):
        """Test get_or_create creates a new session when none exists."""
        repo = SessionRepository(db_session)
        session, is_new = repo.get_or_create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )

        assert session is not None
        assert is_new is True

    def test_get_or_create_session_resumes_existing(
        self, db_session: Session, test_canvas: Canvas
    ):
        """Test get_or_create resumes existing session when session_id provided."""
        repo = SessionRepository(db_session)
        created = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )

        session, is_new = repo.get_or_create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
            session_id=created.session_id,
        )

        assert session is not None
        assert session.id == created.id
        assert is_new is False
        assert session.resumed_count == 1

    def test_get_or_create_session_creates_when_invalid_id(
        self, db_session: Session, test_canvas: Canvas
    ):
        """Test get_or_create creates new session when invalid session_id."""
        repo = SessionRepository(db_session)
        session, is_new = repo.get_or_create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
            session_id="invalid-session-id",
        )

        assert session is not None
        assert is_new is True
        assert session.session_id != "invalid-session-id"

    def test_delete_session(self, db_session: Session, test_canvas: Canvas):
        """Test deleting a session."""
        repo = SessionRepository(db_session)
        created = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )

        result = repo.delete_session(created.session_id)
        assert result is True

        # Verify deletion
        retrieved = repo.get_by_session_id(created.session_id)
        assert retrieved is None

    def test_delete_session_not_found(self, db_session: Session):
        """Test delete returns False for nonexistent session."""
        repo = SessionRepository(db_session)
        result = repo.delete_session("nonexistent-session")
        assert result is False

    def test_update_activity(self, db_session: Session, test_canvas: Canvas):
        """Test updating session activity timestamp."""
        repo = SessionRepository(db_session)
        created = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )

        result = repo.update_activity(created.session_id)
        assert result is True

    def test_update_activity_not_found(self, db_session: Session):
        """Test update_activity returns False for nonexistent session."""
        repo = SessionRepository(db_session)
        result = repo.update_activity("nonexistent-session")
        assert result is False

    def test_get_active_sessions_for_user(
        self, db_session: Session, test_canvas: Canvas
    ):
        """Test getting active sessions for a user."""
        repo = SessionRepository(db_session)

        # Create multiple sessions
        session1 = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )
        session2 = repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )

        active = repo.get_active_sessions_for_user("test-user")
        assert len(active) == 2
        session_ids = [s.session_id for s in active]
        assert session1.session_id in session_ids
        assert session2.session_id in session_ids

    def test_get_active_sessions_excludes_other_users(
        self, db_session: Session, test_canvas: Canvas
    ):
        """Test that get_active_sessions only returns sessions for the specified user."""
        # Create another canvas for another user
        other_canvas = Canvas(user_id="other-user", name="Other Canvas")
        db_session.add(other_canvas)
        db_session.commit()

        repo = SessionRepository(db_session)

        repo.create_session(
            user_id="test-user",
            workspace_id=test_canvas.id,
        )
        repo.create_session(
            user_id="other-user",
            workspace_id=other_canvas.id,
        )

        active = repo.get_active_sessions_for_user("test-user")
        assert len(active) == 1
        assert active[0].user_id == "test-user"
