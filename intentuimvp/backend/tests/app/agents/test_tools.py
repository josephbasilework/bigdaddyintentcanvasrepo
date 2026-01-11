"""Tests for Tool Manager and tool calling."""

import asyncio
import uuid

import pytest
import pytest_asyncio
from pydantic import BaseModel, Field

from app.agents.tools import (
    ToolExecutionResult,
    ToolManager,
    ToolMetadata,
    ToolRecommendation,
    ToolValidationError,
    call_tool,
    get_tool_manager,
)
from app.api.assumption_store import get_assumption_store
from app.database import async_engine


class SearchParams(BaseModel):
    """Test parameters model."""

    query: str
    num_results: int = Field(default=5, ge=1, le=20)


class TestToolManager:
    """Tests for ToolManager."""

    def test_init(self):
        """Test initialization registers built-in tools."""
        manager = ToolManager()

        # Should have built-in tools
        assert manager.get_tool("web_search") is not None
        assert manager.get_tool("read_file") is not None
        assert manager.get_tool("write_file") is not None
        assert manager.get_tool("get_current_time") is not None
        assert manager.get_tool("calculate") is not None
        assert manager.get_tool("hitl.request_approval") is not None

    def test_register_function(self):
        """Test registering a function as a tool."""
        manager = ToolManager()

        def test_func(arg1: str) -> str:
            return arg1

        manager.register_function(
            name="test_tool",
            description="Test tool",
            func=test_func,
            is_async=False,
        )

        tool = manager.get_tool("test_tool")

        assert tool is not None
        assert tool.name == "test_tool"
        assert tool.description == "Test tool"
        assert not tool.is_async

    def test_register_function_with_parameters(self):
        """Test registering function with parameter validation."""
        manager = ToolManager()

        async def test_func(query: str, num_results: int = 5) -> dict:
            return {"results": []}

        manager.register_function(
            name="search_tool",
            description="Search tool",
            func=test_func,
            parameters=SearchParams,
            is_async=True,
        )

        tool = manager.get_tool("search_tool")

        assert tool.parameters == SearchParams

    def test_register_mcp_tool(self):
        """Test registering an MCP tool."""
        manager = ToolManager()

        manager.register_mcp_tool(
            name="mcp_calendar",
            server_name="calendar_server",
            tool_name="list_events",
            description="List calendar events",
        )

        tool = manager.get_tool("mcp_calendar")

        assert tool is not None
        assert tool.mcp_server == "calendar_server"
        assert tool.mcp_tool_name == "list_events"
        assert tool.requires_confirmation

    def test_get_tool_not_found(self):
        """Test getting non-existent tool."""
        manager = ToolManager()

        tool = manager.get_tool("nonexistent_tool")

        assert tool is None

    def test_list_tools_all(self):
        """Test listing all tools."""
        manager = ToolManager()

        tools = manager.list_tools()

        assert len(tools) >= 5  # At least built-in tools

    def test_list_tools_exclude_mcp(self):
        """Test listing tools excluding MCP."""
        manager = ToolManager()

        # Register an MCP tool
        manager.register_mcp_tool(
            name="mcp_test",
            server_name="test_server",
            tool_name="test_tool",
            description="Test",
        )

        all_tools = manager.list_tools(include_mcp=True)
        non_mcp_tools = manager.list_tools(include_mcp=False)

        assert len(all_tools) > len(non_mcp_tools)

    def test_list_tools_exclude_dangerous(self):
        """Test listing tools excluding dangerous."""
        manager = ToolManager()

        all_tools = manager.list_tools(include_dangerous=True)
        safe_tools = manager.list_tools(include_dangerous=False)

        # read_file and write_file are marked dangerous
        assert len(all_tools) >= len(safe_tools)

    def test_validate_arguments_no_schema(self):
        """Test validation when no schema exists."""
        manager = ToolManager()

        def test_func() -> str:
            return "ok"

        manager.register_function(
            name="test_tool",
            description="Test",
            func=test_func,
        )

        is_valid, errors = manager.validate_arguments("test_tool", {"any": "args"})

        assert is_valid
        assert len(errors) == 0

    def test_validate_arguments_with_schema_valid(self):
        """Test validation with valid arguments."""
        manager = ToolManager()

        async def search_func(query: str, num_results: int = 5) -> dict:
            return {}

        manager.register_function(
            name="search",
            description="Search",
            func=search_func,
            parameters=SearchParams,
            is_async=True,
        )

        is_valid, errors = manager.validate_arguments(
            "search", {"query": "test", "num_results": 10}
        )

        assert is_valid
        assert len(errors) == 0

    def test_validate_arguments_with_schema_invalid(self):
        """Test validation with invalid arguments."""
        manager = ToolManager()

        async def search_func(query: str, num_results: int = 5) -> dict:
            return {}

        manager.register_function(
            name="search",
            description="Search",
            func=search_func,
            parameters=SearchParams,
            is_async=True,
        )

        # Missing required field
        is_valid, errors = manager.validate_arguments("search", {"num_results": 10})

        assert not is_valid
        assert len(errors) > 0

    def test_validate_arguments_tool_not_found(self):
        """Test validation for non-existent tool."""
        manager = ToolManager()

        is_valid, errors = manager.validate_arguments("nonexistent", {})

        assert not is_valid
        assert "not found" in errors[0]

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test successful tool execution."""
        manager = ToolManager()

        async def test_func(value: str) -> str:
            return f"processed: {value}"

        manager.register_function(
            name="test_tool",
            description="Test",
            func=test_func,
            is_async=True,
        )

        result = await manager.execute_tool("test_tool", {"value": "hello"})

        assert result.success
        assert result.output == "processed: hello"
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """Test executing non-existent tool."""
        manager = ToolManager()

        result = await manager.execute_tool("nonexistent", {})

        assert not result.success
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_validation_error(self):
        """Test tool execution with validation error."""
        manager = ToolManager()

        async def search_func(query: str, num_results: int = 5) -> dict:
            return {}

        manager.register_function(
            name="search",
            description="Search",
            func=search_func,
            parameters=SearchParams,
            is_async=True,
        )

        with pytest.raises(ToolValidationError) as exc_info:
            await manager.execute_tool("search", {"num_results": 10})

        assert exc_info.value.tool_name == "search"
        assert len(exc_info.value.errors) > 0

    @pytest.mark.asyncio
    async def test_execute_tool_function_error(self):
        """Test tool execution with function error."""
        manager = ToolManager()

        async def failing_func() -> str:
            raise ValueError("Tool failed")

        manager.register_function(
            name="failing_tool",
            description="Failing",
            func=failing_func,
            is_async=True,
        )

        result = await manager.execute_tool("failing_tool", {})

        assert not result.success
        assert "Tool failed" in result.error

    @pytest.mark.asyncio
    async def test_execute_sync_tool(self):
        """Test executing synchronous tool."""
        manager = ToolManager()

        def sync_func(value: str) -> str:
            return f"sync: {value}"

        manager.register_function(
            name="sync_tool",
            description="Sync",
            func=sync_func,
            is_async=False,
        )

        result = await manager.execute_tool("sync_tool", {"value": "test"})

        assert result.success
        assert result.output == "sync: test"

    @pytest.mark.asyncio
    async def test_recommend_tools(self):
        """Test tool recommendation."""
        manager = ToolManager()

        recommendations = await manager.recommend_tools("Search for information about AI")

        assert len(recommendations) > 0
        # Should recommend web_search
        assert any(r.tool_name == "web_search" for r in recommendations)

    @pytest.mark.asyncio
    async def test_recommend_tools_no_match(self):
        """Test tool recommendation with no matches."""
        manager = ToolManager()

        recommendations = await manager.recommend_tools("xyzabc")

        # May return empty or low-confidence recommendations
        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_recommend_tools_sorted_by_confidence(self):
        """Test that recommendations are sorted by confidence."""
        manager = ToolManager()

        recommendations = await manager.recommend_tools(
            "Search the web and read the file"
        )

        # Check sorted in descending order
        confidences = [r.confidence for r in recommendations]
        assert confidences == sorted(confidences, reverse=True)

    @pytest.mark.asyncio
    async def test_hitl_request_approval_waits_for_resolution(self):
        """HITL tool should wait for approvals and return resolutions."""
        manager = get_tool_manager()
        store = get_assumption_store()
        session_id = f"hitl-session-{uuid.uuid4().hex}"
        assumptions = [
            {
                "id": "assumption-a",
                "text": "Assume dataset A is current.",
                "confidence": 0.42,
                "category": "context",
                "explanation": "No timeframe provided.",
            },
            {
                "id": "assumption-b",
                "text": "Deliver summary output.",
                "confidence": 0.55,
                "category": "intent",
            },
        ]

        task = asyncio.create_task(
            manager.execute_tool(
                "hitl.request_approval",
                {"session_id": session_id, "assumptions": assumptions},
            )
        )

        store.resolve_assumption(
            session_id=session_id,
            assumption_id="assumption-a",
            action="accept",
            original_text=assumptions[0]["text"],
            category=assumptions[0]["category"],
        )
        store.resolve_assumption(
            session_id=session_id,
            assumption_id="assumption-b",
            action="edit",
            original_text=assumptions[1]["text"],
            category=assumptions[1]["category"],
            edited_text="Deliver a detailed report.",
        )

        result = await asyncio.wait_for(task, timeout=2)

        assert result.success
        assert result.output["session_id"] == session_id
        assert result.output["status"] == "resolved"
        assert len(result.output["resolved_assumptions"]) == 2

        store.delete_session(session_id)


class TestGlobalToolManager:
    """Tests for global tool manager functions."""

    def test_get_tool_manager_singleton(self):
        """Test that get_tool_manager returns singleton."""
        tm1 = get_tool_manager()
        tm2 = get_tool_manager()

        assert tm1 is tm2

    @pytest.mark.asyncio
    async def test_call_tool_convenience(self):
        """Test the call_tool convenience function."""
        # Note: This uses the real tool manager, so we test with a built-in tool
        result = await call_tool("get_current_time")

        assert result is not None
        assert "timezone" in result

    @pytest.mark.asyncio
    async def test_call_tool_with_validation_error(self):
        """Test call_tool raises on validation error."""
        from pydantic import BaseModel

        manager = get_tool_manager()

        # Create a proper parameter model
        class TestParams(BaseModel):
            value: int

        # Register a tool with validation
        async def test_func(value: int) -> int:
            return value * 2

        manager.register_function(
            name="test_tool_validation",
            description="Test",
            func=test_func,
            parameters=TestParams,
            is_async=True,
        )

        # Should raise RuntimeError (wrapping ToolValidationError)
        with pytest.raises(RuntimeError):
            await call_tool("test_tool_validation", value="not an int")


class TestToolModels:
    """Tests for tool-related data models."""

    def test_tool_metadata(self):
        """Test ToolMetadata dataclass."""
        metadata = ToolMetadata(
            name="test",
            description="Test tool",
            dangerous=False,
        )

        assert metadata.name == "test"
        assert not metadata.dangerous

    def test_tool_execution_result(self):
        """Test ToolExecutionResult model."""
        result = ToolExecutionResult(
            tool_name="test",
            success=True,
            output={"result": "ok"},
            error=None,
            execution_time_ms=42.0,
        )

        assert result.tool_name == "test"
        assert result.success
        assert result.output == {"result": "ok"}

    def test_tool_recommendation(self):
        """Test ToolRecommendation model."""
        rec = ToolRecommendation(
            tool_name="web_search",
            confidence=0.9,
            reason="Keyword match",
            suggested_arguments={},
        )

        assert rec.tool_name == "web_search"
        assert rec.confidence == 0.9
        assert rec.reason == "Keyword match"
        assert rec.suggested_arguments == {}


class TestToolValidationError:
    """Tests for ToolValidationError."""

    def test_initialization(self):
        """Test ToolValidationError initialization."""
        error = ToolValidationError(
            tool_name="test_tool",
            errors=["Field 'query' is required"],
        )

        assert error.tool_name == "test_tool"
        assert error.errors == ["Field 'query' is required"]
        assert "test_tool" in str(error)
        assert "Field 'query' is required" in str(error)

    def test_initialization_with_validation_error(self):
        """Test ToolValidationError with Pydantic ValidationError."""
        from pydantic import ValidationError as PydanticValidationError

        try:
            SearchParams()  # Missing required field
            assert False, "Should have raised ValidationError"
        except PydanticValidationError as e:
            tool_error = ToolValidationError(
                tool_name="search",
                errors=["Validation failed"],
                validation_errors=e,
            )

            assert tool_error.validation_errors is not None


@pytest_asyncio.fixture(autouse=True)
async def _dispose_async_engine():
    """Dispose the async engine to avoid lingering background threads."""
    yield
    await async_engine.dispose()
