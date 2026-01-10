"""Unit tests for AG-UI protocol schemas."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.agui.schemas import (
    AGUI_PROTOCOL_VERSION,
    AgentErrorMessage,
    AgentNotificationMessage,
    AgentProgressMessage,
    AgentRequestMessage,
    AgentResultMessage,
    AgentStatusMessage,
    AgentToUIMessageType,
    AGUIEnvelope,
    AGUIEvent,
    AGUIEventType,
    UICancelMessage,
    UICommandMessage,
    UIContext,
    UIContextCanvas,
    UIContextMessage,
    UIContextViewport,
    UIContextWorkspace,
    UIResponseMessage,
    UIToAgentMessageType,
)


class TestAGUIEnvelope:
    """Tests for AGUIEnvelope base model."""

    def test_envelope_required_fields(self):
        """Test that envelope requires source and target."""
        envelope = AGUIEnvelope(
            source="agent",
            target="ui",
        )
        assert envelope.version == AGUI_PROTOCOL_VERSION
        assert envelope.source == "agent"
        assert envelope.target == "ui"
        assert envelope.message_id is not None
        assert envelope.timestamp is not None

    def test_envelope_with_correlation_id(self):
        """Test envelope with correlation ID."""
        envelope = AGUIEnvelope(
            source="ui",
            target="agent",
            correlation_id="test-correlation-123",
        )
        assert envelope.correlation_id == "test-correlation-123"

    def test_envelope_invalid_source(self):
        """Test that envelope rejects invalid source."""
        with pytest.raises(ValidationError) as exc_info:
            AGUIEnvelope(source="invalid", target="ui")
        assert "source" in str(exc_info.value).lower()

    def test_envelope_invalid_target(self):
        """Test that envelope rejects invalid target."""
        with pytest.raises(ValidationError) as exc_info:
            AGUIEnvelope(source="agent", target="invalid")
        assert "target" in str(exc_info.value).lower()


class TestAgentToUIMessages:
    """Tests for agent -> UI message types."""

    def test_agent_status_message(self):
        """Test AgentStatusMessage validation."""
        msg = AgentStatusMessage(
            payload={
                "status": "working",
                "agent_id": "agent-123",
                "agent_name": "TestAgent",
                "message": "Processing request",
                "progress": 0.5,
            }
        )
        assert msg.type == "status"
        assert msg.source == "agent"
        assert msg.target == "ui"
        assert msg.payload.status == "working"
        assert msg.payload.progress == 0.5

    def test_agent_progress_message(self):
        """Test AgentProgressMessage validation."""
        msg = AgentProgressMessage(
            payload={
                "agent_id": "agent-123",
                "operation": "processing",
                "progress": 0.75,
                "message": "Almost done",
                "total": 100,
                "current": 75,
            }
        )
        assert msg.type == "progress"
        assert msg.payload.progress == 0.75
        assert msg.payload.total == 100

    def test_agent_result_message(self):
        """Test AgentResultMessage validation."""
        msg = AgentResultMessage(
            payload={
                "agent_id": "agent-123",
                "operation": "task",
                "result": {"output": "success"},
                "correlation_id": "corr-123",
            }
        )
        assert msg.type == "result"
        assert msg.payload.result == {"output": "success"}
        assert msg.payload.correlation_id == "corr-123"

    def test_agent_error_message(self):
        """Test AgentErrorMessage validation."""
        msg = AgentErrorMessage(
            payload={
                "agent_id": "agent-123",
                "error": "Something went wrong",
                "code": "ERR_001",
                "recoverable": True,
            }
        )
        assert msg.type == "error"
        assert msg.payload.error == "Something went wrong"
        assert msg.payload.code == "ERR_001"
        assert msg.payload.recoverable is True

    def test_agent_request_message(self):
        """Test AgentRequestMessage validation."""
        msg = AgentRequestMessage(
            payload={
                "agent_id": "agent-123",
                "request_id": "req-123",
                "request_type": "input",
                "prompt": "Please enter your name",
                "required": True,
            }
        )
        assert msg.type == "request"
        assert msg.payload.request_type == "input"
        assert msg.payload.required is True

    def test_agent_notification_message(self):
        """Test AgentNotificationMessage validation."""
        msg = AgentNotificationMessage(
            payload={
                "level": "info",
                "title": "Update",
                "message": "Operation complete",
                "duration": 5000,
            }
        )
        assert msg.type == "notification"
        assert msg.payload.level == "info"
        assert msg.payload.duration == 5000


class TestUIToAgentMessages:
    """Tests for UI -> agent message types."""

    def test_ui_command_message(self):
        """Test UICommandMessage validation."""
        msg = UICommandMessage(
            payload={
                "agent_id": "agent-123",
                "command": "process",
                "parameters": {"input": "test"},
            }
        )
        assert msg.type == "command"
        assert msg.source == "ui"
        assert msg.target == "agent"
        assert msg.payload.command == "process"

    def test_ui_response_message(self):
        """Test UIResponseMessage validation."""
        msg = UIResponseMessage(
            payload={
                "agent_id": "agent-123",
                "request_id": "req-123",
                "response": "User input",
                "cancelled": False,
            }
        )
        assert msg.type == "response"
        assert msg.payload.response == "User input"

    def test_ui_cancel_message(self):
        """Test UICancelMessage validation."""
        msg = UICancelMessage(
            payload={
                "agent_id": "agent-123",
                "operation_id": "op-123",
                "reason": "User cancelled",
            }
        )
        assert msg.type == "cancel"
        assert msg.payload.reason == "User cancelled"


class TestUIContext:
    """Tests for UI context models."""

    def test_ui_context_viewport(self):
        """Test UIContextViewport validation."""
        viewport = UIContextViewport(x=100.0, y=200.0, zoom=1.5)
        assert viewport.x == 100.0
        assert viewport.y == 200.0
        assert viewport.zoom == 1.5

    def test_ui_context_canvas(self):
        """Test UIContextCanvas validation."""
        canvas = UIContextCanvas(
            selected_nodes=["node1", "node2"],
            selected_edges=["edge1"],
            viewport={"x": 0, "y": 0, "zoom": 1},
        )
        assert len(canvas.selected_nodes) == 2
        assert canvas.viewport.zoom == 1

    def test_ui_context_workspace(self):
        """Test UIContextWorkspace validation."""
        workspace = UIContextWorkspace(
            workspace_id="ws-123",
            user_id="user-456",
        )
        assert workspace.workspace_id == "ws-123"
        assert workspace.user_id == "user-456"

    def test_ui_context_full(self):
        """Test full UIContext validation."""
        context = UIContext(
            canvas={
                "selected_nodes": [],
                "selected_edges": [],
                "viewport": {"x": 0, "y": 0, "zoom": 1},
            },
            workspace={
                "workspace_id": "ws-123",
            },
            user_input="test input",
        )
        assert context.user_input == "test input"


class TestAGUIEvent:
    """Tests for AGUIEvent model."""

    def test_event_creation(self):
        """Test event creation with valid type."""
        event = AGUIEvent(
            event_type="node.created",
            data={"node_id": "node-123", "type": "text"},
        )
        assert event.event_type == "node.created"
        assert event.data["node_id"] == "node-123"
        assert event.event_id is not None
        assert event.timestamp is not None

    def test_event_all_types(self):
        """Test all valid event types."""
        event_types: list[AGUIEventType] = [
            "node.created",
            "node.updated",
            "node.deleted",
            "edge.created",
            "edge.deleted",
            "canvas.cleared",
            "workspace.changed",
            "selection.changed",
            "viewport.changed",
        ]
        for event_type in event_types:
            event = AGUIEvent(event_type=event_type, data={})
            assert event.event_type == event_type


class TestSerialization:
    """Tests for JSON serialization/deserialization."""

    def test_agent_status_serialization(self):
        """Test AgentStatusMessage JSON serialization."""
        msg = AgentStatusMessage(
            payload={
                "status": "working",
                "agent_id": "agent-123",
                "agent_name": "TestAgent",
            }
        )
        # Serialize to JSON
        json_str = msg.model_dump_json()
        data = json.loads(json_str)

        # Verify fields
        assert data["type"] == "status"
        assert data["source"] == "agent"
        assert data["target"] == "ui"
        assert data["version"] == AGUI_PROTOCOL_VERSION
        assert "message_id" in data
        assert "timestamp" in data

    def test_ui_command_deserialization(self):
        """Test UICommandMessage JSON deserialization."""
        json_data = {
            "version": AGUI_PROTOCOL_VERSION,
            "message_id": "msg-123",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "ui",
            "target": "agent",
            "type": "command",
            "payload": {
                "command": "process",
                "parameters": {"input": "test"},
            },
        }

        msg = UICommandMessage(**json_data)
        assert msg.type == "command"
        assert msg.payload.command == "process"


class TestMessageDiscrimination:
    """Tests for message type discrimination."""

    def test_agent_to_ui_message_types(self):
        """Test that all agent -> UI messages have correct source/target."""
        messages: list[AgentToUIMessageType] = [
            AgentStatusMessage(payload={"status": "idle", "agent_id": "a", "agent_name": "A"}),
            AgentProgressMessage(payload={"agent_id": "a", "operation": "op", "progress": 0.5}),
            AgentResultMessage(payload={"agent_id": "a", "operation": "op", "result": {}}),
            AgentErrorMessage(payload={"agent_id": "a", "error": "err"}),
            AgentRequestMessage(payload={"agent_id": "a", "request_id": "r", "request_type": "input", "prompt": "p"}),
            AgentNotificationMessage(payload={"level": "info", "title": "T", "message": "M"}),
        ]
        for msg in messages:
            assert msg.source == "agent"
            assert msg.target == "ui"

    def test_ui_to_agent_message_types(self):
        """Test that all UI -> agent messages have correct source/target."""
        messages: list[UIToAgentMessageType] = [
            UICommandMessage(payload={"command": "test"}),
            UIResponseMessage(payload={"agent_id": "a", "request_id": "r", "response": {}}),
            UICancelMessage(payload={"agent_id": "a"}),
            UIContextMessage(payload={"context": {"canvas": {"selected_nodes": [], "selected_edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}, "workspace": {"workspace_id": "w"}}}),
        ]
        for msg in messages:
            assert msg.source == "ui"
            assert msg.target == "agent"
