"""Repository for workspace session operations."""

from datetime import UTC, datetime, timedelta
from logging import getLogger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.session import WorkspaceSession, generate_session_id

logger = getLogger(__name__)


class SessionRepository:
    """Repository for WorkspaceSession CRUD operations.

    Uses SQLAlchemy ORM for database access. Provides methods for
    creating, reading, resuming, and managing workspace sessions.
    """

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session (sync)
        """
        self.db = db

    def get_by_session_id(self, session_id: str) -> WorkspaceSession | None:
        """Get session by session_id.

        Args:
            session_id: The unique session identifier (UUID)

        Returns:
            WorkspaceSession if found, None otherwise
        """
        return (
            self.db.query(WorkspaceSession)
            .filter(WorkspaceSession.session_id == session_id)
            .first()
        )

    def get_by_user_and_workspace(
        self, user_id: str, workspace_id: int
    ) -> WorkspaceSession | None:
        """Get the most recent session for a user/workspace combination.

        Args:
            user_id: User identifier
            workspace_id: Canvas/workspace identifier

        Returns:
            Most recent WorkspaceSession if found, None otherwise
        """
        return (
            self.db.query(WorkspaceSession)
            .filter(
                WorkspaceSession.user_id == user_id,
                WorkspaceSession.workspace_id == workspace_id,
            )
            .order_by(WorkspaceSession.last_active_at.desc())
            .first()
        )

    def get_active_sessions_for_user(
        self, user_id: str, max_age_hours: int = 24
    ) -> list[WorkspaceSession]:
        """Get all active sessions for a user within the given time window.

        Args:
            user_id: User identifier
            max_age_hours: Maximum age in hours for a session to be considered active

        Returns:
            List of active WorkspaceSessions
        """
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        return list(
            self.db.query(WorkspaceSession)
            .filter(
                WorkspaceSession.user_id == user_id,
                WorkspaceSession.last_active_at >= cutoff,
            )
            .order_by(WorkspaceSession.last_active_at.desc())
            .all()
        )

    def create_session(
        self,
        user_id: str,
        workspace_id: int,
        session_id: str | None = None,
    ) -> WorkspaceSession:
        """Create a new workspace session.

        Args:
            user_id: User identifier
            workspace_id: Canvas/workspace identifier
            session_id: Optional pre-generated session ID (for testing or client-provided)

        Returns:
            Created WorkspaceSession
        """
        session = WorkspaceSession(
            session_id=session_id or generate_session_id(),
            workspace_id=workspace_id,
            user_id=user_id,
            resumed_count=0,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        logger.info(
            f"Created session {session.session_id} for user {user_id}, "
            f"workspace {workspace_id}"
        )
        return session

    def resume_session(self, session_id: str, user_id: str) -> WorkspaceSession | None:
        """Resume an existing session, updating last_active_at and resumed_count.

        Validates that the session belongs to the requesting user.

        Args:
            session_id: The session to resume
            user_id: The user attempting to resume (for ownership validation)

        Returns:
            Updated WorkspaceSession if valid, None if not found or unauthorized
        """
        session = self.get_by_session_id(session_id)
        if session is None:
            logger.warning(f"Session {session_id} not found for resume")
            return None

        if session.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to resume session {session_id} "
                f"owned by {session.user_id}"
            )
            return None

        session.last_active_at = datetime.now(UTC)
        session.resumed_count += 1
        self.db.commit()
        self.db.refresh(session)
        logger.info(
            f"Resumed session {session_id} (resume count: {session.resumed_count})"
        )
        return session

    def update_activity(self, session_id: str) -> bool:
        """Update the last_active_at timestamp for a session.

        Args:
            session_id: The session to update

        Returns:
            True if updated, False if not found
        """
        session = self.get_by_session_id(session_id)
        if session is None:
            return False

        session.last_active_at = datetime.now(UTC)
        self.db.commit()
        return True

    def get_or_create_session(
        self,
        user_id: str,
        workspace_id: int,
        session_id: str | None = None,
    ) -> tuple[WorkspaceSession, bool]:
        """Get an existing session by ID or create a new one.

        If session_id is provided, attempts to resume that session (validating ownership).
        If not found or not provided, creates a new session for the user/workspace.

        Args:
            user_id: User identifier
            workspace_id: Canvas/workspace identifier
            session_id: Optional session ID to resume

        Returns:
            Tuple of (WorkspaceSession, is_new_session)
        """
        if session_id:
            session = self.resume_session(session_id, user_id)
            if session is not None:
                return session, False

        # Create new session
        new_session = self.create_session(user_id, workspace_id)
        return new_session, True

    def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID.

        Args:
            session_id: The session to delete

        Returns:
            True if deleted, False if not found
        """
        session = self.get_by_session_id(session_id)
        if session is None:
            return False

        self.db.delete(session)
        self.db.commit()
        logger.info(f"Deleted session {session_id}")
        return True

    def cleanup_inactive_sessions(self, max_age_hours: int = 168) -> int:
        """Delete sessions that have been inactive for longer than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours (default: 7 days / 168 hours)

        Returns:
            Number of sessions deleted
        """
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        result = (
            self.db.query(WorkspaceSession)
            .filter(WorkspaceSession.last_active_at < cutoff)
            .delete()
        )
        self.db.commit()
        logger.info(f"Cleaned up {result} inactive sessions older than {max_age_hours}h")
        return result


class AsyncSessionRepository:
    """Async repository for WorkspaceSession CRUD operations.

    Uses SQLAlchemy async ORM for database access.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with async database session.

        Args:
            db: SQLAlchemy async session
        """
        self.db = db

    async def get_by_session_id(self, session_id: str) -> WorkspaceSession | None:
        """Get session by session_id.

        Args:
            session_id: The unique session identifier (UUID)

        Returns:
            WorkspaceSession if found, None otherwise
        """
        result = await self.db.execute(
            select(WorkspaceSession).filter(WorkspaceSession.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_workspace(
        self, user_id: str, workspace_id: int
    ) -> WorkspaceSession | None:
        """Get the most recent session for a user/workspace combination.

        Args:
            user_id: User identifier
            workspace_id: Canvas/workspace identifier

        Returns:
            Most recent WorkspaceSession if found, None otherwise
        """
        result = await self.db.execute(
            select(WorkspaceSession)
            .filter(
                WorkspaceSession.user_id == user_id,
                WorkspaceSession.workspace_id == workspace_id,
            )
            .order_by(WorkspaceSession.last_active_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_session(
        self,
        user_id: str,
        workspace_id: int,
        session_id: str | None = None,
    ) -> WorkspaceSession:
        """Create a new workspace session.

        Args:
            user_id: User identifier
            workspace_id: Canvas/workspace identifier
            session_id: Optional pre-generated session ID

        Returns:
            Created WorkspaceSession
        """
        session = WorkspaceSession(
            session_id=session_id or generate_session_id(),
            workspace_id=workspace_id,
            user_id=user_id,
            resumed_count=0,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        logger.info(
            f"Created session {session.session_id} for user {user_id}, "
            f"workspace {workspace_id}"
        )
        return session

    async def resume_session(
        self, session_id: str, user_id: str
    ) -> WorkspaceSession | None:
        """Resume an existing session, updating last_active_at and resumed_count.

        Args:
            session_id: The session to resume
            user_id: The user attempting to resume (for ownership validation)

        Returns:
            Updated WorkspaceSession if valid, None if not found or unauthorized
        """
        session = await self.get_by_session_id(session_id)
        if session is None:
            logger.warning(f"Session {session_id} not found for resume")
            return None

        if session.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to resume session {session_id} "
                f"owned by {session.user_id}"
            )
            return None

        session.last_active_at = datetime.now(UTC)
        session.resumed_count += 1
        await self.db.commit()
        await self.db.refresh(session)
        logger.info(
            f"Resumed session {session_id} (resume count: {session.resumed_count})"
        )
        return session

    async def get_or_create_session(
        self,
        user_id: str,
        workspace_id: int,
        session_id: str | None = None,
    ) -> tuple[WorkspaceSession, bool]:
        """Get an existing session by ID or create a new one.

        Args:
            user_id: User identifier
            workspace_id: Canvas/workspace identifier
            session_id: Optional session ID to resume

        Returns:
            Tuple of (WorkspaceSession, is_new_session)
        """
        if session_id:
            session = await self.resume_session(session_id, user_id)
            if session is not None:
                return session, False

        new_session = await self.create_session(user_id, workspace_id)
        return new_session, True

    async def update_activity(self, session_id: str) -> bool:
        """Update the last_active_at timestamp for a session.

        Args:
            session_id: The session to update

        Returns:
            True if updated, False if not found
        """
        session = await self.get_by_session_id(session_id)
        if session is None:
            return False

        session.last_active_at = datetime.now(UTC)
        await self.db.commit()
        return True
