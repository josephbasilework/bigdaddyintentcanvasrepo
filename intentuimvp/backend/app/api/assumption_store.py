"""In-memory storage for resolved assumptions.

This module provides a simple in-memory store for assumption resolutions.
In production, this should be replaced with a persistent store (Redis, database).
"""

import asyncio
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
        self._completion_events: dict[str, asyncio.Event] = {}

    def _init_session(
        self,
        session_id: str,
        assumptions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Initialize a new session record."""
        normalized_assumptions = assumptions or []
        expected_ids = [
            str(item["id"]).strip()
            for item in normalized_assumptions
            if item.get("id")
        ]
        session = {
            "id": session_id,
            "created_at": time.time(),
            "resolved_assumptions": [],
            "is_complete": False,
            "assumptions": normalized_assumptions,
            "expected_assumption_ids": expected_ids,
        }
        self._sessions[session_id] = session
        self._completion_events[session_id] = asyncio.Event()
        return session

    def create_session(
        self,
        session_id: str | None = None,
        assumptions: list[dict[str, Any]] | None = None,
    ) -> str:
        """Create a new assumption resolution session.

        Returns:
            Session ID for tracking assumption resolutions.
        """
        resolved_session_id = session_id or str(uuid.uuid4())
        if resolved_session_id in self._sessions:
            session = self._sessions[resolved_session_id]
            if assumptions is not None:
                session["assumptions"] = assumptions
                session["expected_assumption_ids"] = [
                    str(item["id"]).strip()
                    for item in assumptions
                    if item.get("id")
                ]
                self._update_completion(resolved_session_id)
            self._completion_events.setdefault(
                resolved_session_id, asyncio.Event()
            )
            return resolved_session_id

        self._init_session(resolved_session_id, assumptions=assumptions)
        logger.info(f"Created assumption session: {resolved_session_id}")
        return resolved_session_id

    def resolve_assumption(
        self,
        session_id: str,
        assumption_id: str,
        action: str,
        original_text: str,
        category: str,
        edited_text: str | None = None,
        feedback: str | None = None,
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
            self._init_session(session_id)

        final_text = original_text
        if action == "edit" and edited_text:
            final_text = edited_text
        elif action == "reject":
            final_text = "[REJECTED]" if not feedback else f"[REJECTED] {feedback}"

        resolution = {
            "assumption_id": assumption_id,
            "action": action,
            "original_text": original_text,
            "final_text": final_text,
            "category": category,
            "timestamp": time.time(),
            "feedback": feedback,
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
        self._update_completion(session_id)

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

    def get_assumptions(self, session_id: str) -> list[dict[str, Any]]:
        """Get assumptions for a session.

        Args:
            session_id: The session ID.

        Returns:
            List of assumptions for the session.
        """
        session = self._sessions.get(session_id)
        if not session:
            return []
        return session.get("assumptions", [])

    def mark_complete(self, session_id: str) -> None:
        """Mark a session as complete.

        Args:
            session_id: The session ID.
        """
        if session_id in self._sessions:
            self._sessions[session_id]["is_complete"] = True
            event = self._completion_events.get(session_id)
            if event is not None:
                event.set()
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
            self._completion_events.pop(session_id, None)
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
            self._completion_events.pop(sid, None)

        if to_delete:
            logger.info(f"Cleaned up {len(to_delete)} old sessions")

        return len(to_delete)

    async def wait_for_completion(
        self, session_id: str, timeout_s: float | None = None
    ) -> bool:
        """Wait for a session to be marked complete.

        Args:
            session_id: The session ID.
            timeout_s: Optional timeout in seconds.

        Returns:
            True if session completed, False if timed out or missing.
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        if session.get("is_complete"):
            return True

        if self._has_all_resolved(session):
            session["is_complete"] = True
            event = self._completion_events.get(session_id)
            if event is not None:
                event.set()
            return True

        event = self._completion_events.setdefault(session_id, asyncio.Event())
        try:
            if timeout_s is None:
                await event.wait()
                return True
            await asyncio.wait_for(event.wait(), timeout=timeout_s)
            return True
        except TimeoutError:
            return False

    def _has_all_resolved(self, session: dict[str, Any]) -> bool:
        """Check if all expected assumptions have been resolved."""
        expected_ids = session.get("expected_assumption_ids") or []
        if not expected_ids:
            return False
        resolved_ids = {
            resolution["assumption_id"]
            for resolution in session.get("resolved_assumptions", [])
        }
        return set(expected_ids).issubset(resolved_ids)

    def _update_completion(self, session_id: str) -> None:
        """Update completion status based on resolved assumptions."""
        session = self._sessions.get(session_id)
        if not session:
            return
        if session.get("is_complete"):
            event = self._completion_events.get(session_id)
            if event is not None:
                event.set()
            return
        if self._has_all_resolved(session):
            session["is_complete"] = True
            event = self._completion_events.get(session_id)
            if event is not None:
                event.set()


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
