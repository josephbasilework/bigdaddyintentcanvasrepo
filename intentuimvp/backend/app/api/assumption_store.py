"""In-memory storage for resolved assumptions.

This module provides a simple in-memory store for assumption resolutions.
In production, this should be replaced with a persistent store (Redis, database).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.intent_memory import IntentMemoryStore


def _get_safety() -> Any:
    """Lazy import to avoid circular dependency."""
    from app.agents.safety import get_safety

    return get_safety()


def _get_intent_memory_store() -> IntentMemoryStore | None:
    """Lazy import to avoid circular dependency."""
    try:
        from app.services.intent_memory import get_intent_memory_store

        return get_intent_memory_store()
    except Exception:  # pragma: no cover
        return None


class AssumptionStore:
    """In-memory store for resolved assumptions.

    Stores assumption resolutions by session_id for use in execution.
    Integrates with intent memory for learning from user decisions.
    """

    def __init__(
        self,
        *,
        intent_memory_store: IntentMemoryStore | None = None,
    ) -> None:
        """Initialize the assumption store.

        Args:
            intent_memory_store: Optional intent memory store for learning.
                If None, will try to get the singleton instance.
        """
        self._sessions: dict[str, dict[str, Any]] = {}
        self._completion_events: dict[str, asyncio.Event] = {}
        self._intent_memory_store: IntentMemoryStore | None = None
        if intent_memory_store is not None:
            self._intent_memory_store = intent_memory_store
        else:
            self._intent_memory_store = _get_intent_memory_store()

    def _init_session(
        self,
        session_id: str,
        assumptions: list[dict[str, Any]] | None = None,
        original_text: str | None = None,
        handler: str | None = None,
        user_id: str | None = None,
        workspace_id: str | int | None = None,
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
            "clarifications": [],
        }
        if original_text is not None:
            session["original_text"] = original_text
        if handler is not None:
            session["handler"] = handler
        if user_id is not None:
            session["user_id"] = user_id
        if workspace_id is not None:
            session["workspace_id"] = workspace_id
        self._sessions[session_id] = session
        self._completion_events[session_id] = asyncio.Event()
        return session

    def create_session(
        self,
        session_id: str | None = None,
        assumptions: list[dict[str, Any]] | None = None,
        original_text: str | None = None,
        handler: str | None = None,
        user_id: str | None = None,
        workspace_id: str | int | None = None,
    ) -> str:
        """Create a new assumption resolution session.

        Args:
            session_id: Optional session ID. If None, generates a UUID.
            assumptions: Optional list of assumptions for this session.
            original_text: Optional original user text for Intent Index integration.
            handler: Optional handler name for Intent Index integration.
            user_id: Optional user ID for intent memory learning.
            workspace_id: Optional workspace ID for scoped learning.

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
            if original_text is not None:
                session["original_text"] = original_text
            if handler is not None:
                session["handler"] = handler
            if user_id is not None:
                session["user_id"] = user_id
            if workspace_id is not None:
                session["workspace_id"] = workspace_id
            self._completion_events.setdefault(
                resolved_session_id, asyncio.Event()
            )
            return resolved_session_id

        self._init_session(
            resolved_session_id,
            assumptions=assumptions,
            original_text=original_text,
            handler=handler,
            user_id=user_id,
            workspace_id=workspace_id,
        )
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
        source: str = "user",
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
            "source": source,
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
        try:
            _get_safety().log_approval_event(
                session_id=session_id,
                assumption_id=assumption_id,
                action=action,
                category=category,
                original_text=original_text,
                final_text=final_text,
                feedback=feedback,
                source=source,
            )
        except Exception:
            logger.warning(
                "Failed to log approval audit event", exc_info=True
            )

        # Record resolution to intent memory for learning
        self._record_to_intent_memory(session_id, original_text, category, action)

        self._update_completion(session_id)

        return resolution

    def _record_to_intent_memory(
        self,
        session_id: str,
        assumption_text: str,
        category: str,
        action: str,
    ) -> None:
        """Record assumption resolution to intent memory for learning."""
        if self._intent_memory_store is None:
            return
        session = self._sessions.get(session_id)
        if not session:
            return
        user_id = session.get("user_id")
        if not user_id:
            return
        workspace_id = session.get("workspace_id")
        try:
            self._intent_memory_store.record_assumption_resolution(
                user_id=user_id,
                assumption_text=assumption_text,
                category=category,
                action=action,
                workspace_id=workspace_id,
                session_id=session_id,
            )
            logger.debug(
                "Recorded assumption resolution to intent memory: "
                f"user={user_id}, category={category}, action={action}"
            )
        except Exception:
            logger.warning(
                "Failed to record assumption resolution to intent memory",
                exc_info=True,
            )

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

    def apply_auto_confirm(
        self,
        session_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Apply auto-confirmation to session assumptions using intent memory.

        Checks all assumptions in the session against intent memory to
        automatically confirm assumptions that match learned patterns.

        Args:
            session_id: The session ID.

        Returns:
            Tuple of (auto_confirmed, remaining) assumption lists.
            auto_confirmed contains assumptions that were automatically resolved.
            remaining contains assumptions that still need user confirmation.
        """
        session = self._sessions.get(session_id)
        if not session:
            return [], []
        assumptions = session.get("assumptions", [])
        if not assumptions:
            return [], []
        if self._intent_memory_store is None:
            return [], assumptions

        user_id = session.get("user_id")
        if not user_id:
            return [], assumptions

        workspace_id = session.get("workspace_id")
        try:
            confirmed, remaining = self._intent_memory_store.auto_confirm_assumptions(
                user_id=user_id,
                assumptions=assumptions,
                workspace_id=workspace_id,
                session_id=session_id,
            )
        except Exception:
            logger.warning("Failed to apply auto-confirm", exc_info=True)
            return [], assumptions

        # Record auto-confirmed assumptions as resolved
        auto_confirmed_list = []
        for assumption, memory_entry in confirmed:
            assumption_id = str(assumption.get("id", ""))
            original_text = str(assumption.get("text", ""))
            category = str(assumption.get("category", ""))
            if assumption_id:
                resolution = {
                    "assumption_id": assumption_id,
                    "action": "accept",
                    "original_text": original_text,
                    "final_text": original_text,
                    "category": category,
                    "timestamp": time.time(),
                    "feedback": None,
                    "source": "auto_confirm",
                    "memory_entry_id": memory_entry.entry_id,
                }
                # Remove any existing resolution
                session["resolved_assumptions"] = [
                    r
                    for r in session.get("resolved_assumptions", [])
                    if r["assumption_id"] != assumption_id
                ]
                session["resolved_assumptions"].append(resolution)
                auto_confirmed_list.append(assumption)
                logger.info(
                    f"Auto-confirmed assumption {assumption_id} via intent memory "
                    f"(entry={memory_entry.entry_id})"
                )

        # Update expected IDs to exclude auto-confirmed
        remaining_ids = [str(a.get("id", "")).strip() for a in remaining if a.get("id")]
        session["expected_assumption_ids"] = remaining_ids

        self._update_completion(session_id)
        return auto_confirmed_list, remaining

    def record_clarification(self, session_id: str, text: str) -> dict[str, Any]:
        """Record a clarification response for a session."""
        if session_id not in self._sessions:
            self._init_session(session_id)
        entry = {"text": text.strip(), "timestamp": time.time()}
        clarifications = self._sessions[session_id].setdefault("clarifications", [])
        clarifications.append(entry)
        logger.info("Recorded clarification for session %s", session_id)
        return entry

    def get_clarifications(self, session_id: str) -> list[dict[str, Any]]:
        """Get clarification responses for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        return session.get("clarifications", [])

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
            assumptions = session.get("assumptions") or []
            resolved = session.get("resolved_assumptions") or []
            if assumptions and len(resolved) >= len(assumptions):
                return True
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
