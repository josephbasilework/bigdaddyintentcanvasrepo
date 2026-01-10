"""Tests for state sync protocol implementation."""

import pytest

from app.agui import (
    JSONPatchOperation,
    StateSnapshotMessage,
    StateSnapshotPayload,
    StateSyncRequestMessage,
    StateSyncRequestPayload,
    StateUpdateMessage,
    StateUpdatePayload,
    compute_checksum,
)


class TestComputeChecksum:
    """Tests for compute_checksum function."""

    def test_compute_checksum_returns_correct_format(self):
        """Test that checksum is in correct format."""
        data = {"test": "data", "number": 123}
        checksum = compute_checksum(data)

        assert checksum.startswith("sha256:")
        assert len(checksum) == 71  # "sha256:" + 64 hex chars

    def test_compute_checksum_is_deterministic(self):
        """Test that same data produces same checksum."""
        data = {"test": "data", "number": 123}
        checksum1 = compute_checksum(data)
        checksum2 = compute_checksum(data)

        assert checksum1 == checksum2

    def test_compute_checksum_different_data_different_checksum(self):
        """Test that different data produces different checksums."""
        data1 = {"test": "data1"}
        data2 = {"test": "data2"}

        checksum1 = compute_checksum(data1)
        checksum2 = compute_checksum(data2)

        assert checksum1 != checksum2

    def test_compute_checksum_order_independent(self):
        """Test that key order doesn't affect checksum."""
        data1 = {"b": 2, "a": 1}
        data2 = {"a": 1, "b": 2}

        checksum1 = compute_checksum(data1)
        checksum2 = compute_checksum(data2)

        assert checksum1 == checksum2


class TestJSONPatchOperation:
    """Tests for JSONPatchOperation model."""

    def test_valid_patch_operation(self):
        """Test creating a valid patch operation."""
        op = JSONPatchOperation(op="add", path="/nodes/abc123", value={"id": "abc123"})
        assert op.op == "add"
        assert op.path == "/nodes/abc123"
        assert op.value == {"id": "abc123"}

    def test_move_operation_with_from(self):
        """Test move operation with from path."""
        op = JSONPatchOperation(op="move", path="/new/path", **{"from": "/old/path"})
        assert op.op == "move"
        assert op.model_dump(by_alias=True)["from"] == "/old/path"

    def test_invalid_operation_raises_error(self):
        """Test that invalid operation raises error."""
        with pytest.raises(ValueError):
            JSONPatchOperation(op="invalid", path="/test")  # type: ignore


class TestStateUpdatePayload:
    """Tests for StateUpdatePayload model."""

    def test_valid_state_update_payload(self):
        """Test creating a valid state update payload."""
        payload = StateUpdatePayload(
            sequence=1,
            patch=[JSONPatchOperation(op="add", path="/test", value="data")],
            checksum="sha256:" + "a" * 64,
        )
        assert payload.sequence == 1
        assert len(payload.patch) == 1
        assert payload.checksum.startswith("sha256:")

    def test_sequence_must_be_non_negative(self):
        """Test that sequence must be non-negative."""
        with pytest.raises(ValueError):
            StateUpdatePayload(
                sequence=-1,
                patch=[],
                checksum="sha256:" + "a" * 64,
            )

    def test_invalid_checksum_format_raises_error(self):
        """Test that invalid checksum format raises error."""
        with pytest.raises(ValueError):
            StateUpdatePayload(
                sequence=1,
                patch=[],
                checksum="invalid",
            )

    def test_checksum_too_short_raises_error(self):
        """Test that checksum too short raises error."""
        with pytest.raises(ValueError):
            StateUpdatePayload(
                sequence=1,
                patch=[],
                checksum="sha256:" + "a" * 63,
            )

    def test_checksum_invalid_hex_raises_error(self):
        """Test that checksum with invalid hex raises error."""
        with pytest.raises(ValueError):
            StateUpdatePayload(
                sequence=1,
                patch=[],
                checksum="sha256:" + "g" * 64,  # 'g' is not valid hex
            )


class TestStateUpdateMessage:
    """Tests for StateUpdateMessage model."""

    def test_valid_state_update_message(self):
        """Test creating a valid state update message."""
        message = StateUpdateMessage(
            payload={
                "sequence": 1,
                "patch": [JSONPatchOperation(op="add", path="/test", value="data")],
                "checksum": "sha256:" + "a" * 64,
            }
        )
        assert message.type == "state.update"
        assert message.source == "agent"
        assert message.target == "ui"


class TestStateSyncRequestPayload:
    """Tests for StateSyncRequestPayload model."""

    def test_valid_state_sync_request_payload(self):
        """Test creating a valid state sync request payload."""
        payload = StateSyncRequestPayload(last_sequence=5)
        assert payload.last_sequence == 5

    def test_null_last_sequence_is_valid(self):
        """Test that null last_sequence is valid (for initial sync)."""
        payload = StateSyncRequestPayload(last_sequence=None)
        assert payload.last_sequence is None


class TestStateSyncRequestMessage:
    """Tests for StateSyncRequestMessage model."""

    def test_valid_state_sync_request_message(self):
        """Test creating a valid state sync request message."""
        message = StateSyncRequestMessage(
            payload={"last_sequence": 5}
        )
        assert message.type == "state.sync_request"
        assert message.source == "ui"
        assert message.target == "agent"


class TestStateSnapshotPayload:
    """Tests for StateSnapshotPayload model."""

    def test_valid_state_snapshot_payload(self):
        """Test creating a valid state snapshot payload."""
        payload = StateSnapshotPayload(
            sequence=10,
            state={"nodes": {}, "edges": []},
            checksum="sha256:" + "a" * 64,
        )
        assert payload.sequence == 10
        assert payload.state == {"nodes": {}, "edges": []}
        assert payload.checksum.startswith("sha256:")


class TestStateSnapshotMessage:
    """Tests for StateSnapshotMessage model."""

    def test_valid_state_snapshot_message(self):
        """Test creating a valid state snapshot message."""
        message = StateSnapshotMessage(
            payload={
                "sequence": 10,
                "state": {"nodes": {}, "edges": []},
                "checksum": "sha256:" + "a" * 64,
            }
        )
        assert message.type == "state.snapshot"
        assert message.source == "agent"
        assert message.target == "ui"


class TestStateSequenceManager:
    """Tests for StateSequenceManager."""

    @pytest.mark.asyncio
    async def test_initial_sequence_is_zero(self):
        """Test that initial sequence is zero."""
        from app.ws.state_manager import StateSequenceManager

        manager = StateSequenceManager()
        assert await manager.get_sequence() == 0

    @pytest.mark.asyncio
    async def test_next_sequence_increments(self):
        """Test that next_sequence increments the counter."""
        from app.ws.state_manager import StateSequenceManager

        manager = StateSequenceManager()
        assert await manager.next_sequence() == 0
        assert await manager.next_sequence() == 1
        assert await manager.next_sequence() == 2

    @pytest.mark.asyncio
    async def test_get_sequence_does_not_increment(self):
        """Test that get_sequence does not increment the counter."""
        from app.ws.state_manager import StateSequenceManager

        manager = StateSequenceManager()
        assert await manager.get_sequence() == 0
        assert await manager.get_sequence() == 0

    @pytest.mark.asyncio
    async def test_create_state_update(self):
        """Test creating a state update."""
        from app.ws.state_manager import StateSequenceManager

        manager = StateSequenceManager()
        patch = [{"op": "add", "path": "/test", "value": "data"}]
        seq, checksum = await manager.create_state_update(patch)

        assert seq == 0
        assert checksum.startswith("sha256:")

    @pytest.mark.asyncio
    async def test_get_full_state_returns_empty_initially(self):
        """Test that get_full_state returns empty dict initially."""
        from app.ws.state_manager import StateSequenceManager

        manager = StateSequenceManager()
        state = await manager.get_full_state()
        assert state == {}

    @pytest.mark.asyncio
    async def test_update_state_applies_patch(self):
        """Test that update_state applies a patch."""
        from app.ws.state_manager import StateSequenceManager

        manager = StateSequenceManager()
        patch = [JSONPatchOperation(op="add", path="/test", value="data")]
        await manager.update_state(patch)

        state = await manager.get_full_state()
        assert state == {"test": "data"}

    @pytest.mark.asyncio
    async def test_create_snapshot(self):
        """Test creating a state snapshot."""
        from app.ws.state_manager import StateSequenceManager

        manager = StateSequenceManager()
        patch = [JSONPatchOperation(op="add", path="/test", value="data")]
        await manager.update_state(patch)

        seq, state, checksum = await manager.create_snapshot()

        assert seq == 0
        assert state == {"test": "data"}
        assert checksum.startswith("sha256:")

    @pytest.mark.asyncio
    async def test_global_state_manager(self):
        """Test that get_state_manager returns singleton instance."""
        from app.ws.state_manager import StateSequenceManager, get_state_manager

        manager1 = get_state_manager()
        manager2 = get_state_manager()

        assert manager1 is manager2
        assert isinstance(manager1, StateSequenceManager)
