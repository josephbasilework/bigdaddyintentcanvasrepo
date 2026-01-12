"""Tests for RunAgentInput handler and AG-UI run lifecycle."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agui import (
    RunEndMessage,
    RunStartMessage,
)
from app.api.runs import RunAgentInput, RunAgentResponse

# ============================================================================
# RunAgentInput Schema Tests
# ============================================================================


class TestRunAgentInput:
    """Tests for RunAgentInput schema validation."""

    def test_valid_run_agent_input(self):
        """Test creating a valid RunAgentInput."""
        input_data = RunAgentInput(
            messages=[{"role": "user", "content": "Hello"}],
            state={"canvas_id": 1},
            tools=["canvas.create_node"],
            agent_id="intent_decipherer",
            context={"user_input": "Hello"},
        )
        assert input_data.messages == [{"role": "user", "content": "Hello"}]
        assert input_data.state == {"canvas_id": 1}
        assert input_data.tools == ["canvas.create_node"]
        assert input_data.agent_id == "intent_decipherer"
        assert input_data.context == {"user_input": "Hello"}

    def test_run_agent_input_defaults(self):
        """Test RunAgentInput with default values."""
        input_data = RunAgentInput(messages=[{"role": "user", "content": "test"}])
        assert input_data.state == {}
        assert input_data.tools == []
        assert input_data.agent_id == "intent_decipherer"
        assert input_data.context is None

    def test_run_agent_input_serialization(self):
        """Test RunAgentInput JSON serialization."""
        input_data = RunAgentInput(
            messages=[{"role": "user", "content": "Create a node"}],
            state={"viewport": {"x": 0, "y": 0, "zoom": 1.0}},
        )
        json_str = input_data.model_dump_json()
        assert "Create a node" in json_str
        assert "viewport" in json_str


class TestRunAgentResponse:
    """Tests for RunAgentResponse schema."""

    def test_run_agent_response_creation(self):
        """Test creating a RunAgentResponse."""
        response = RunAgentResponse(
            run_id="run-123",
            status="running",
            message="Agent run started",
        )
        assert response.run_id == "run-123"
        assert response.status == "running"
        assert response.message == "Agent run started"


# ============================================================================
# Run Orchestrator Tests
# ============================================================================


class TestRunOrchestrator:
    """Tests for RunOrchestrator."""

    @pytest.fixture
    def mock_ws_manager(self):
        """Create a mock WebSocket connection manager."""
        manager = MagicMock()
        manager.broadcast_agui = AsyncMock()
        return manager

    @pytest.fixture
    def mock_agent(self):
        """Create a mock IntentDeciphererAgent."""
        agent = MagicMock()
        agent.run = AsyncMock(return_value={"result": "success"})
        return agent

    @pytest.fixture
    def orchestrator(self, mock_ws_manager):
        """Create a RunOrchestrator instance."""
        from app.api.runs import RunOrchestrator

        return RunOrchestrator(ws_manager=mock_ws_manager)

    @pytest.mark.asyncio
    async def test_send_run_start(self, orchestrator, mock_ws_manager):
        """Test sending run.start event."""
        input_data = RunAgentInput(
            messages=[{"role": "user", "content": "test"}],
        )

        await orchestrator._send_run_start("run-123", input_data, "intent_decipherer")

        # Verify broadcast was called
        assert mock_ws_manager.broadcast_agui.called
        call_args = mock_ws_manager.broadcast_agui.call_args[0][0]
        assert isinstance(call_args, RunStartMessage)
        assert call_args.payload.run_id == "run-123"
        assert call_args.payload.agent_id == "intent_decipherer"

    @pytest.mark.asyncio
    async def test_send_run_end_success(self, orchestrator, mock_ws_manager):
        """Test sending run.end event on success."""
        await orchestrator._send_run_end(
            "run-123",
            "intent_decipherer",
            "success",
            result={"output": "done"},
            start_time=1000.0,
        )

        assert mock_ws_manager.broadcast_agui.called
        call_args = mock_ws_manager.broadcast_agui.call_args[0][0]
        assert isinstance(call_args, RunEndMessage)
        assert call_args.payload.run_id == "run-123"
        assert call_args.payload.status == "success"
        assert call_args.payload.result == {"output": "done"}

    @pytest.mark.asyncio
    async def test_execute_with_streaming(self, orchestrator, mock_agent, mock_ws_manager):
        """Test agent execution with progress streaming."""
        input_data = RunAgentInput(
            messages=[{"role": "user", "content": "Create a chart"}],
        )

        result = await orchestrator._execute_with_streaming(
            "run-123",
            input_data,
            mock_agent,
            1000.0,
            "intent_decipherer",
        )

        # Verify agent was called
        assert mock_agent.run.called
        # Verify progress events were sent (at least 3: initial, processing, complete)
        assert mock_ws_manager.broadcast_agui.call_count >= 3
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_run_agent_success(self, orchestrator, mock_agent, mock_ws_manager):
        """Test complete agent run flow on success."""
        input_data = RunAgentInput(
            messages=[{"role": "user", "content": "test input"}],
        )

        run_id = await orchestrator.run_agent(input_data, mock_agent)

        # Verify run_id format
        assert run_id.startswith("run-")
        # Verify events: run.start, progress updates, run.end
        assert mock_ws_manager.broadcast_agui.call_count >= 4


# ============================================================================
# AG-UI Message Tests
# ============================================================================


class TestAGUIMessages:
    """Tests for AG-UI run lifecycle messages."""

    def test_run_start_message_creation(self):
        """Test creating RunStartMessage."""
        from app.agui import RunStartPayload

        payload = RunStartPayload(
            run_id="run-123",
            agent_id="intent_decipherer",
            agent_name="Intent Decipherer",
            input_data={"messages": [{"role": "user", "content": "test"}]},
            tools=["canvas.create_node"],
        )
        message = RunStartMessage(payload=payload)

        assert message.payload.run_id == "run-123"
        assert message.payload.agent_id == "intent_decipherer"
        assert message.payload.agent_name == "Intent Decipherer"
        assert message.type == "run.start"
        assert message.source == "agent"
        assert message.target == "ui"

    def test_run_end_message_creation(self):
        """Test creating RunEndMessage."""
        from app.agui import RunEndPayload

        payload = RunEndPayload(
            run_id="run-123",
            agent_id="intent_decipherer",
            status="success",
            result={"output": "done"},
            duration_ms=1234.56,
        )
        message = RunEndMessage(payload=payload)

        assert message.payload.run_id == "run-123"
        assert message.payload.status == "success"
        assert message.payload.result == {"output": "done"}
        assert message.payload.duration_ms == 1234.56
        assert message.type == "run.end"

    def test_tool_call_message_creation(self):
        """Test creating ToolCallMessage."""
        from app.agui import ToolCallMessage, ToolCallPayload

        payload = ToolCallPayload(
            run_id="run-123",
            tool_name="canvas.create_node",
            tool_args={"type": "text", "content": "test"},
        )
        message = ToolCallMessage(payload=payload)

        assert message.payload.run_id == "run-123"
        assert message.payload.tool_name == "canvas.create_node"
        assert message.payload.tool_args == {"type": "text", "content": "test"}
        assert message.payload.call_id.startswith("call-")
        assert message.type == "tool.call"

    def test_tool_result_message_creation(self):
        """Test creating ToolResultMessage."""
        from app.agui import ToolResultMessage, ToolResultPayload

        payload = ToolResultPayload(
            run_id="run-123",
            call_id="call-abc",
            tool_name="canvas.create_node",
            success=True,
            result={"node_id": 42},
            duration_ms=56.78,
        )
        message = ToolResultMessage(payload=payload)

        assert message.payload.run_id == "run-123"
        assert message.payload.call_id == "call-abc"
        assert message.payload.success is True
        assert message.payload.result == {"node_id": 42}
        assert message.payload.duration_ms == 56.78
        assert message.type == "tool.result"
