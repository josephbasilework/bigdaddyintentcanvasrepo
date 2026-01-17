"""Tests for Turn model and enums."""

import json
from datetime import datetime

from app.models.turn import Turn, TurnActor, TurnType


class TestTurnActorEnum:
    """Tests for TurnActor enum."""

    def test_actor_values(self) -> None:
        """Verify all actor values are defined."""
        assert TurnActor.USER == "user"
        assert TurnActor.SYSTEM == "system"
        assert TurnActor.AGENT == "agent"
        assert TurnActor.MCP == "mcp"

    def test_actor_is_string_enum(self) -> None:
        """Verify TurnActor is a string enum."""
        assert isinstance(TurnActor.USER, str)
        assert TurnActor.USER == "user"


class TestTurnTypeEnum:
    """Tests for TurnType enum."""

    def test_user_interaction_types(self) -> None:
        """Verify user interaction turn types."""
        assert TurnType.USER_INPUT == "user_input"
        assert TurnType.USER_CANVAS_ACTION == "user_canvas_action"

    def test_canvas_crud_types(self) -> None:
        """Verify canvas CRUD turn types."""
        assert TurnType.NODE_CREATED == "node_created"
        assert TurnType.NODE_UPDATED == "node_updated"
        assert TurnType.NODE_DELETED == "node_deleted"
        assert TurnType.EDGE_CREATED == "edge_created"
        assert TurnType.EDGE_UPDATED == "edge_updated"
        assert TurnType.EDGE_DELETED == "edge_deleted"

    def test_job_lifecycle_types(self) -> None:
        """Verify job lifecycle turn types."""
        assert TurnType.JOB_STARTED == "job_started"
        assert TurnType.JOB_PROGRESS == "job_progress"
        assert TurnType.JOB_COMPLETED == "job_completed"
        assert TurnType.JOB_FAILED == "job_failed"

    def test_response_types(self) -> None:
        """Verify response turn types."""
        assert TurnType.AGENT_RESPONSE == "agent_response"
        assert TurnType.SYSTEM_MESSAGE == "system_message"

    def test_assumption_types(self) -> None:
        """Verify assumption reconciliation turn types."""
        assert TurnType.ASSUMPTION_PRESENTED == "assumption_presented"
        assert TurnType.ASSUMPTION_CONFIRMED == "assumption_confirmed"
        assert TurnType.ASSUMPTION_REJECTED == "assumption_rejected"
        assert TurnType.ASSUMPTION_MODIFIED == "assumption_modified"

    def test_mcp_types(self) -> None:
        """Verify MCP operation turn types."""
        assert TurnType.MCP_TOOL_INVOKED == "mcp_tool_invoked"
        assert TurnType.MCP_TOOL_RESULT == "mcp_tool_result"


class TestTurnModel:
    """Tests for Turn model."""

    def test_turn_creation(self) -> None:
        """Test basic turn creation with required fields."""
        turn = Turn(
            id=1,
            session_id="session-123",
            sequence_number=1,
            timestamp=datetime(2026, 1, 17, 12, 0, 0),
            actor=TurnActor.USER,
            type=TurnType.USER_INPUT,
            summary="User asked a question",
        )

        assert turn.id == 1
        assert turn.session_id == "session-123"
        assert turn.sequence_number == 1
        assert turn.actor == TurnActor.USER
        assert turn.type == TurnType.USER_INPUT
        assert turn.summary == "User asked a question"
        assert turn.turn_payload is None
        assert turn.related_node_id is None
        assert turn.related_edge_id is None

    def test_turn_with_payload(self) -> None:
        """Test turn creation with JSON payload."""
        turn = Turn(
            id=2,
            session_id="session-456",
            sequence_number=2,
            timestamp=datetime(2026, 1, 17, 12, 1, 0),
            actor=TurnActor.AGENT,
            type=TurnType.AGENT_RESPONSE,
            summary="Agent responded with plan",
            turn_payload=json.dumps({"response": "Here is my plan", "confidence": 0.95}),
        )

        assert turn.get_payload() == {"response": "Here is my plan", "confidence": 0.95}

    def test_turn_payload_roundtrip(self) -> None:
        """Test payload get/set methods."""
        turn = Turn(
            id=3,
            session_id="session-789",
            sequence_number=1,
            timestamp=datetime(2026, 1, 17, 12, 0, 0),
            actor=TurnActor.SYSTEM,
            type=TurnType.NODE_CREATED,
            summary="Created new text node",
        )

        # Initially empty
        assert turn.get_payload() == {}

        # Set payload
        turn.set_payload({"node_type": "text", "label": "My Node"})
        assert turn.get_payload() == {"node_type": "text", "label": "My Node"}

        # Update payload
        turn.set_payload({"updated": True})
        assert turn.get_payload() == {"updated": True}

    def test_turn_empty_payload(self) -> None:
        """Test that empty payload returns empty dict."""
        turn = Turn(
            id=4,
            session_id="session-abc",
            sequence_number=1,
            timestamp=datetime(2026, 1, 17, 12, 0, 0),
            actor=TurnActor.USER,
            type=TurnType.USER_INPUT,
            summary="Test",
            turn_payload=None,
        )

        assert turn.get_payload() == {}

    def test_turn_with_related_entities(self) -> None:
        """Test turn with related node and edge IDs."""
        turn = Turn(
            id=5,
            session_id="session-def",
            sequence_number=3,
            timestamp=datetime(2026, 1, 17, 12, 2, 0),
            actor=TurnActor.SYSTEM,
            type=TurnType.EDGE_CREATED,
            summary="Created edge between nodes",
            related_node_id=100,
            related_edge_id=50,
        )

        assert turn.related_node_id == 100
        assert turn.related_edge_id == 50


class TestTurnToDict:
    """Tests for Turn.to_dict() serialization."""

    def test_to_dict_basic(self) -> None:
        """Test basic to_dict serialization."""
        turn = Turn(
            id=10,
            session_id="session-xyz",
            sequence_number=5,
            timestamp=datetime(2026, 1, 17, 14, 30, 0),
            actor=TurnActor.USER,
            type=TurnType.USER_INPUT,
            summary="User typed a command",
        )

        result = turn.to_dict()

        assert result["id"] == 10
        assert result["sessionId"] == "session-xyz"
        assert result["sequenceNumber"] == 5
        assert result["timestamp"] == "2026-01-17T14:30:00"
        assert result["actor"] == TurnActor.USER
        assert result["type"] == TurnType.USER_INPUT
        assert result["summary"] == "User typed a command"
        assert result["payload"] == {}
        assert result["relatedNodeId"] is None
        assert result["relatedEdgeId"] is None

    def test_to_dict_with_payload(self) -> None:
        """Test to_dict with payload."""
        turn = Turn(
            id=11,
            session_id="session-ghi",
            sequence_number=1,
            timestamp=datetime(2026, 1, 17, 15, 0, 0),
            actor=TurnActor.AGENT,
            type=TurnType.AGENT_RESPONSE,
            summary="Agent response",
            turn_payload=json.dumps({"data": [1, 2, 3]}),
        )

        result = turn.to_dict()

        assert result["payload"] == {"data": [1, 2, 3]}

    def test_to_dict_uses_camel_case(self) -> None:
        """Verify to_dict uses camelCase for API compatibility."""
        turn = Turn(
            id=12,
            session_id="s1",
            sequence_number=1,
            timestamp=datetime(2026, 1, 17, 0, 0, 0),
            actor=TurnActor.USER,
            type=TurnType.USER_INPUT,
            summary="Test",
            related_node_id=42,
            related_edge_id=99,
        )

        result = turn.to_dict()

        # Verify camelCase keys
        assert "sessionId" in result
        assert "sequenceNumber" in result
        assert "relatedNodeId" in result
        assert "relatedEdgeId" in result

        # Verify snake_case keys are NOT present
        assert "session_id" not in result
        assert "sequence_number" not in result
        assert "related_node_id" not in result
        assert "related_edge_id" not in result


class TestTurnRepr:
    """Tests for Turn.__repr__()."""

    def test_repr(self) -> None:
        """Test string representation."""
        turn = Turn(
            id=20,
            session_id="session-repr",
            sequence_number=7,
            timestamp=datetime(2026, 1, 17, 12, 0, 0),
            actor=TurnActor.MCP,
            type=TurnType.MCP_TOOL_INVOKED,
            summary="Invoked calendar tool",
        )

        repr_str = repr(turn)

        assert "Turn" in repr_str
        assert "id=20" in repr_str
        assert "session=session-repr" in repr_str
        assert "seq=7" in repr_str
        # Enum repr includes the enum class name
        assert "MCP" in repr_str
        assert "MCP_TOOL_INVOKED" in repr_str


class TestTurnTypeCompleteness:
    """Tests to ensure all required turn types exist per PRD."""

    def test_all_required_types_defined(self) -> None:
        """Verify all turn types from task description are defined."""
        # User input
        assert TurnType.USER_INPUT

        # Canvas CRUD
        assert TurnType.NODE_CREATED
        assert TurnType.NODE_UPDATED
        assert TurnType.NODE_DELETED
        assert TurnType.EDGE_CREATED
        assert TurnType.EDGE_UPDATED
        assert TurnType.EDGE_DELETED

        # Job lifecycle
        assert TurnType.JOB_STARTED
        assert TurnType.JOB_PROGRESS
        assert TurnType.JOB_COMPLETED
        assert TurnType.JOB_FAILED

        # System responses
        assert TurnType.AGENT_RESPONSE
        assert TurnType.SYSTEM_MESSAGE

        # Assumption reconciliation
        assert TurnType.ASSUMPTION_PRESENTED
        assert TurnType.ASSUMPTION_CONFIRMED
        assert TurnType.ASSUMPTION_REJECTED
        assert TurnType.ASSUMPTION_MODIFIED

    def test_all_required_actors_defined(self) -> None:
        """Verify all actor types exist."""
        # Per task: user, system, agent
        assert TurnActor.USER
        assert TurnActor.SYSTEM
        assert TurnActor.AGENT
        # Also MCP for tool invocations
        assert TurnActor.MCP
