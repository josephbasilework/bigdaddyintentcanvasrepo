"""In-memory storage for resolved assumptions.

This module provides a simple in-memory store for assumption resolutions.
In production, this should be replaced with a persistent store (Redis, database).
"""

import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class AssumptionStore:
    """In-memory store for resolved assumptions.

    Stores assumption resolutions by session_id for use in execution.
    """

    def __init__(self) -> None:
        """Initialize the assumption store."""
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_session(self) -> str:
        """Create a new assumption resolution session.

        Returns:
            Session ID for tracking assumption resolutions.
        """
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "id": session_id,
            "created_at": time.time(),
            "resolved_assumptions": [],
            "is_complete": False,
        }
        logger.info(f"Created assumption session: {session_id}")
        return session_id

    def resolve_assumption(
        self,
        session_id: str,
        assumption_id: str,
        action: str,
        original_text: str,
        category: str,
        edited_text: str | None = None,
    ) -> dict[str, Any]:
        """Record an assumption resolution.

        Args:
            session_id: The session ID.
            assumption_id: The assumption being resolved.
            action: One of 'accept', 'reject', 'edit'.
            original_text: The original assumption text.
            category: The assumption category.
            edited_text: If action is 'edit', the edited text.

        Returns:
            The recorded resolution.
        """
        if session_id not in self._sessions:
            logger.warning(f"Session not found, creating new: {session_id}")
            self._sessions[session_id] = {
                "id": session_id,
                "created_at": time.time(),
                "resolved_assumptions": [],
                "is_complete": False,
            }

        final_text = original_text
        if action == "edit" and edited_text:
            final_text = edited_text
        elif action == "reject":
            final_text = "[REJECTED]"

        resolution = {
            "assumption_id": assumption_id,
            "action": action,
            "original_text": original_text,
            "final_text": final_text,
            "category": category,
            "timestamp": time.time(),
        }

        # Remove any existing resolution for this assumption
        self._sessions[session_id]["resolved_assumptions"] = [
            r
            for r in self._sessions[session_id]["resolved_assumptions"]
            if r["assumption_id"] != assumption_id
        ]

        # Add the new resolution
        self._sessions[session_id]["resolved_assumptions"].append(resolution)
        logger.info(
            f"Resolved assumption {assumption_id} in session {session_id}: {action}"
        )

        return resolution

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            Session data or None if not found.
        """
        return self._sessions.get(session_id)

    def get_resolved_assumptions(
        self, session_id: str
    ) -> list[dict[str, Any]]:
        """Get all resolved assumptions for a session.

        Args:
            session_id: The session ID.

        Returns:
            List of resolved assumptions.
        """
        session = self._sessions.get(session_id)
        if not session:
            return []
        return session.get("resolved_assumptions", [])

    def mark_complete(self, session_id: str) -> None:
        """Mark a session as complete.

        Args:
            session_id: The session ID.
        """
        if session_id in self._sessions:
            self._sessions[session_id]["is_complete"] = True
            logger.info(f"Marked session {session_id} as complete")

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: The session ID.

        Returns:
            True if deleted, False if not found.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

    def cleanup_old_sessions(self, max_age_seconds: int = 3600) -> int:
        """Clean up sessions older than max_age_seconds.

        Args:
            max_age_seconds: Maximum age in seconds (default 1 hour).

        Returns:
            Number of sessions deleted.
        """
        now = time.time()
        to_delete = [
            sid
            for sid, session in self._sessions.items()
            if now - session.get("created_at", 0) > max_age_seconds
        ]

        for sid in to_delete:
            del self._sessions[sid]

        if to_delete:
            logger.info(f"Cleaned up {len(to_delete)} old sessions")

        return len(to_delete)


# Singleton instance
_store: AssumptionStore | None = None


def get_assumption_store() -> AssumptionStore:
    """Get the singleton assumption store instance.

    Returns:
        Assumption store instance.
    """
    global _store
    if _store is None:
        _store = AssumptionStore()
    return _store
