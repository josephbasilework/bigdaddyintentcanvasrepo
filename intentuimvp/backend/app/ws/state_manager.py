"""State sequence manager for WebSocket state sync protocol.

This module manages the sequence numbers and state for the AG-UI
state sync protocol. It provides:
- Monotonically increasing sequence numbers
- Checksum computation for state updates
- Full state snapshot generation
"""

import asyncio
import logging
from typing import Any

from app.agui import (
    JSONPatchOperation,
    compute_checksum,
)

logger = logging.getLogger(__name__)


class StateSequenceManager:
    """Manages state sequence tracking and sync.

    This class provides thread-safe sequence number management and
    state tracking for the WebSocket state sync protocol.
    """

    def __init__(self) -> None:
        """Initialize the state sequence manager."""
        self._sequence: int = 0
        self._lock = asyncio.Lock()
        self._state: dict[str, Any] = {}

    async def get_sequence(self) -> int:
        """Get the current sequence number.

        Returns:
            The current sequence number.
        """
        async with self._lock:
            return self._sequence

    async def next_sequence(self) -> int:
        """Get the next sequence number and increment.

        Returns:
            The next sequence number to use.
        """
        async with self._lock:
            seq = self._sequence
            self._sequence += 1
            return seq

    async def create_state_update(
        self, patch: list[dict[str, Any]]
    ) -> tuple[int, str]:
        """Create a state update with sequence and checksum.

        Args:
            patch: JSON Patch operations as dictionaries.

        Returns:
            A tuple of (sequence_number, checksum).
        """
        async with self._lock:
            seq = self._sequence
            self._sequence += 1

        # Compute checksum for the patch (wrap in dict for checksum function)
        checksum = compute_checksum({"patch": patch})

        return seq, checksum

    async def get_full_state(self) -> dict[str, Any]:
        """Get the full current state.

        Returns:
            A copy of the current state.
        """
        async with self._lock:
            return self._state.copy()

    async def update_state(self, patch: list[JSONPatchOperation]) -> None:
        """Apply a patch to the state.

        Args:
            patch: JSON Patch operations to apply.
        """
        async with self._lock:
            for operation in patch:
                path = operation.path

                if operation.op == "add":
                    self._set_at_path(self._state, path, operation.value)
                elif operation.op == "remove":
                    self._remove_at_path(self._state, path)
                elif operation.op == "replace":
                    self._set_at_path(self._state, path, operation.value)
                elif operation.op == "move":
                    from_path = operation.from_
                    if from_path is None:
                        raise ValueError("move operation requires 'from' path")
                    value = self._get_at_path(self._state, from_path)
                    self._remove_at_path(self._state, from_path)
                    self._set_at_path(self._state, path, value)
                elif operation.op == "copy":
                    from_path = operation.from_
                    if from_path is None:
                        raise ValueError("copy operation requires 'from' path")
                    value = self._get_at_path(self._state, from_path)
                    self._set_at_path(self._state, path, value)
                elif operation.op == "test":
                    # Test operation - verify value matches
                    current = self._get_at_path(self._state, path)
                    if current != operation.value:
                        raise ValueError(
                            f"Test failed at {path}: "
                            f"expected {operation.value}, got {current}"
                        )

    def _set_at_path(self, state: dict[str, Any], path: str, value: Any) -> None:
        """Set a value at a JSON Pointer path.

        Args:
            state: The state dictionary to modify.
            path: JSON Pointer path (e.g., "/nodes/abc123").
            value: The value to set.
        """
        if path == "" or path == "/":
            # Root path - this would mean replacing entire state
            if isinstance(value, dict):
                state.clear()
                state.update(value)
            return

        parts = path.strip("/").split("/")
        current: Any = state

        # Navigate to the parent
        for part in parts[:-1]:
            if part.isdigit():
                part = int(part)  # type: ignore[assignment]
            if part not in current:
                current[part] = {}  # type: ignore[index]
            current = current[part]  # type: ignore[index]

        # Set the final value
        key = parts[-1]
        if key.isdigit():
            key = int(key)  # type: ignore[assignment]
        current[key] = value  # type: ignore[index]

    def _get_at_path(self, state: dict[str, Any], path: str) -> Any:
        """Get a value at a JSON Pointer path.

        Args:
            state: The state dictionary to read.
            path: JSON Pointer path (e.g., "/nodes/abc123").

        Returns:
            The value at the path.

        Raises:
            KeyError: If the path doesn't exist.
        """
        if path == "" or path == "/":
            return state

        parts = path.strip("/").split("/")
        current: Any = state

        for part in parts:
            if part.isdigit():
                part = int(part)  # type: ignore[assignment]
            if part not in current:
                raise KeyError(f"Path not found: {path}")
            current = current[part]  # type: ignore[index]

        return current

    def _remove_at_path(self, state: dict[str, Any], path: str) -> None:
        """Remove a value at a JSON Pointer path.

        Args:
            state: The state dictionary to modify.
            path: JSON Pointer path (e.g., "/nodes/abc123").

        Raises:
            KeyError: If the path doesn't exist.
        """
        if path == "" or path == "/":
            state.clear()
            return

        parts = path.strip("/").split("/")
        current: Any = state

        # Navigate to the parent
        for part in parts[:-1]:
            if part.isdigit():
                part = int(part)  # type: ignore[assignment]
            if part not in current:
                raise KeyError(f"Path not found: {path}")
            current = current[part]  # type: ignore[index]

        # Remove the final key
        key = parts[-1]
        if key.isdigit():
            key = int(key)  # type: ignore[assignment]
        if key not in current:
            raise KeyError(f"Path not found: {path}")
        del current[key]  # type: ignore[arg-type]

    async def create_snapshot(self) -> tuple[int, dict[str, Any], str]:
        """Create a full state snapshot with sequence and checksum.

        Returns:
            A tuple of (sequence_number, state_dict, checksum).
        """
        async with self._lock:
            seq = self._sequence
            state = self._state.copy()

        checksum = compute_checksum(state)
        return seq, state, checksum


# Global state manager instance
_state_manager: StateSequenceManager | None = None


def get_state_manager() -> StateSequenceManager:
    """Get the global state manager instance.

    Returns:
        The global StateSequenceManager instance.
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = StateSequenceManager()
    return _state_manager
