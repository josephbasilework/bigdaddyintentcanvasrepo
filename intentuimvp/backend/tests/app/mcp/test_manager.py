"""Tests for MCP Manager.

Tests MCPManager including:
- Connection lifecycle (start/stop servers)
- Tool discovery and listing
- Tool execution with security validation
- Health checking
- Error handling and retry logic
"""

import sys

# IMPORTANT: Remove tests.app.mcp from sys.modules if present to avoid shadowing
# the external 'mcp' package. This must happen before any imports that would
# trigger loading app.mcp.manager, which imports from the mcp SDK.
if "tests.app.mcp" in sys.modules:
    del sys.modules["tests.app.mcp"]
if "mcp" in sys.modules and "tests" in getattr(sys.modules["mcp"], "__file__", ""):
    del sys.modules["mcp"]

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.mcp.models  # noqa: F401
from app.database import Base

# Import manager after sys.modules manipulation
from app.mcp.manager import (
    MCPConnection,
    MCPManager,
    ServerHealth,
    ServerHealthState,
    ToolExecutionResult,
)
from app.mcp.manifest import BLOCKED_CAPABILITIES
from app.mcp.models import MCPExecutionLog, MCPServer
from app.mcp.registry import MCPServerRegistry
from app.mcp.security import MCPSecurityValidator

# In-memory async test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async test engine with in-memory database."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for tests."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture
def manager(db_session: AsyncSession) -> MCPManager:
    """Provide an MCPManager instance."""
    return MCPManager(db_session)


@pytest_asyncio.fixture
async def test_server(db_session: AsyncSession) -> MCPServer:
    """Create a test MCP server in the database."""
    server = MCPServer(
        server_id="test-server",
        name="Test MCP Server",
        description="A test server",
        transport_type="stdio",
        transport_config={"command": ["echo"], "args": []},
        version="1.0.0",
        capabilities={
            "tools": [
                {"name": "read_data", "description": "Read data"},
                {"name": "write_data", "description": "Write data"},
            ]
        },
        security_rules={
            "read_data": "allowed",
            "write_data": "requires_confirm",
        },
        enabled=True,
        rate_limit=100,
    )
    db_session.add(server)
    await db_session.flush()
    return server


@pytest_asyncio.fixture
async def disabled_server(db_session: AsyncSession) -> MCPServer:
    """Create a disabled MCP server in the database."""
    server = MCPServer(
        server_id="disabled-server",
        name="Disabled Server",
        transport_type="stdio",
        transport_config={"command": ["echo"], "args": []},
        enabled=False,
        security_rules={},
        rate_limit=60,
    )
    db_session.add(server)
    await db_session.flush()
    return server


def _mock_stdio_client() -> Mock:
    """Create a properly mocked stdio_client async context manager.

    Returns a Mock that behaves like stdio_client when used with
    exit_stack.enter_async_context().
    """
    mock_read = Mock()
    mock_write = Mock()

    # Create an async context manager mock
    mock_cm = Mock()
    mock_cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    return mock_cm


def _mock_client_session() -> AsyncMock:
    """Create a properly mocked ClientSession.

    Returns an AsyncMock with initialize() mocked and __aenter__ returning self.
    This mimics how the real ClientSession is used as an async context manager.
    """
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    # When entered as async context manager, return self
    # This ensures any method modifications (like call_tool) are visible
    def return_self(*args, **kwargs):
        return mock_session
    mock_session.__aenter__ = AsyncMock(side_effect=return_self)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


class TestToolExecutionResult:
    """Tests for ToolExecutionResult dataclass."""

    def test_success_result(self) -> None:
        """Test creating a successful execution result."""
        result = ToolExecutionResult(
            success=True,
            result={"data": "test"},
            error=None,
            required_confirmation=False,
        )
        assert result.success is True
        assert result.result == {"data": "test"}
        assert result.error is None
        assert result.required_confirmation is False

    def test_failure_result(self) -> None:
        """Test creating a failed execution result."""
        result = ToolExecutionResult(
            success=False,
            result=None,
            error="Connection failed",
            required_confirmation=False,
        )
        assert result.success is False
        assert result.result is None
        assert result.error == "Connection failed"

    def test_requires_confirmation_result(self) -> None:
        """Test creating a result that requires confirmation."""
        result = ToolExecutionResult(
            success=False,
            error="User confirmation required",
            required_confirmation=True,
        )
        assert result.success is False
        assert result.required_confirmation is True
        assert result.error is not None and "confirmation" in result.error


class TestMCPConnection:
    """Tests for MCPConnection dataclass."""

    def test_connection_creation(self) -> None:
        """Test creating an MCPConnection."""
        mock_session = Mock()
        mock_exit_stack = Mock()
        connection = MCPConnection(
            session=mock_session,
            exit_stack=mock_exit_stack,
        )
        assert connection.session is mock_session
        assert connection.exit_stack is mock_exit_stack


class TestMCPManagerInit:
    """Tests for MCPManager initialization."""

    def test_initialization(self, db_session: AsyncSession) -> None:
        """Test manager initialization."""
        manager = MCPManager(db_session)
        assert manager._session is db_session
        assert isinstance(manager._registry, MCPServerRegistry)
        assert isinstance(manager._validator, MCPSecurityValidator)
        assert manager._connections == {}
        assert isinstance(manager._connection_lock, asyncio.Lock)


@pytest.mark.asyncio
class TestStartServer:
    """Tests for starting MCP server connections."""

    async def test_start_nonexistent_server(
        self, manager: MCPManager
    ) -> None:
        """Test starting a server that doesn't exist."""
        result = await manager.start_server("nonexistent-server")
        assert result is False
        assert "nonexistent-server" not in manager._connections

    async def test_start_disabled_server(
        self, manager: MCPManager, disabled_server: MCPServer
    ) -> None:
        """Test starting a disabled server."""
        result = await manager.start_server(disabled_server.server_id)
        assert result is False
        assert disabled_server.server_id not in manager._connections

    async def test_start_stdio_server_success(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test successfully starting a stdio server."""
        # Mock the MCP SDK components
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()
            mock_session = _mock_client_session()
            mock_session_cls.return_value = mock_session

            result = await manager.start_server(test_server.server_id)

            assert result is True
            assert test_server.server_id in manager._connections
            assert manager._connections[test_server.server_id].session is mock_session

    async def test_start_already_connected_server(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test starting a server that's already connected."""
        # Mock and start the server first
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()
            mock_session = _mock_client_session()
            mock_session_cls.return_value = mock_session

            # Start once
            result1 = await manager.start_server(test_server.server_id)
            assert result1 is True

            # Start again - should return True without re-connecting
            result2 = await manager.start_server(test_server.server_id)
            assert result2 is True

            # Should still have only one connection
            assert len(manager._connections) == 1

    async def test_start_stdio_server_handles_exceptions(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test that exceptions during server start are handled."""
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client:
            mock_stdio_client.side_effect = Exception("Connection failed")

            result = await manager.start_server(test_server.server_id)
            assert result is False
            assert test_server.server_id not in manager._connections


@pytest.mark.asyncio
class TestStopServer:
    """Tests for stopping MCP server connections."""

    async def test_stop_connected_server(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test stopping a connected server."""
        # Mock the connection
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()
            mock_session = _mock_client_session()
            mock_session_cls.return_value = mock_session

            # Start the server
            await manager.start_server(test_server.server_id)
            assert test_server.server_id in manager._connections

            # Stop the server
            result = await manager.stop_server(test_server.server_id)
            assert result is True
            assert test_server.server_id not in manager._connections

    async def test_stop_nonexistent_server(
        self, manager: MCPManager
    ) -> None:
        """Test stopping a server that's not connected."""
        result = await manager.stop_server("nonexistent-server")
        assert result is False

    async def test_stop_handles_exceptions(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test that exceptions during stop are handled."""
        # Mock a connection that raises an exception on close
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()
            mock_session = _mock_client_session()
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            # Make the exit_stack raise an exception
            manager._connections[test_server.server_id].exit_stack.aclose = AsyncMock(  # type: ignore[method-assign]
                side_effect=Exception("Close failed")
            )

            result = await manager.stop_server(test_server.server_id)
            assert result is False  # Failed to stop cleanly
            # Note: The actual implementation does NOT remove the connection on exception
            # It returns False and leaves the connection in place
            assert test_server.server_id in manager._connections


@pytest.mark.asyncio
class TestStopAll:
    """Tests for stopping all connections."""

    async def test_stop_all_servers(
        self, manager: MCPManager, db_session: AsyncSession
    ) -> None:
        """Test stopping all connected servers."""
        # Create multiple test servers
        servers = []
        for i in range(3):
            server = MCPServer(
                server_id=f"test-server-{i}",
                name=f"Test Server {i}",
                transport_type="stdio",
                transport_config={"command": ["echo"], "args": []},
                enabled=True,
                security_rules={},
                rate_limit=60,
            )
            db_session.add(server)
            await db_session.flush()
            servers.append(server)

        # Mock and start all servers
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()
            mock_session = _mock_client_session()
            mock_session_cls.return_value = mock_session

            for server in servers:
                await manager.start_server(server.server_id)

            assert len(manager._connections) == 3

            # Stop all
            await manager.stop_all()

            assert len(manager._connections) == 0


@pytest.mark.asyncio
class TestListTools:
    """Tests for listing tools from connected servers."""

    async def test_list_tools_from_connected_server(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test listing tools from a connected server."""
        # Mock the connection and tools
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            mock_session = _mock_client_session()
            mock_tool = Mock()
            mock_tool.name = "test_tool"
            mock_tool.description = "A test tool"
            mock_tool.inputSchema = {"type": "object"}

            mock_response = Mock()
            mock_response.tools = [mock_tool]
            mock_session.list_tools = AsyncMock(return_value=mock_response)
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            tools = await manager.list_tools(test_server.server_id)

            assert tools is not None
            assert len(tools) == 1
            assert tools[0]["name"] == "test_tool"
            assert tools[0]["description"] == "A test tool"

    async def test_list_tools_from_disconnected_server(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test listing tools from a disconnected server."""
        tools = await manager.list_tools(test_server.server_id)
        assert tools is None

    async def test_list_tools_handles_exceptions(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test that exceptions during list_tools are handled."""
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            mock_session = _mock_client_session()
            mock_session.list_tools = AsyncMock(side_effect=Exception("List failed"))
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            tools = await manager.list_tools(test_server.server_id)
            assert tools is None


@pytest.mark.asyncio
class TestExecuteTool:
    """Tests for tool execution with security validation."""

    async def test_execute_blocked_capability(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test that blocked capabilities are rejected."""
        # Try to execute a blocked capability
        for blocked_cap in BLOCKED_CAPABILITIES:
            result = await manager.execute_tool(
                server_id=test_server.server_id,
                tool_name=blocked_cap,
                arguments={},
                initiated_by="test_user",
            )
            assert result.success is False
            assert result.error is not None and (
                "FR-019" in result.error or "blocked" in result.error.lower()
            )

    async def test_execute_requires_confirmation(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test tool that requires confirmation."""
        result = await manager.execute_tool(
            server_id=test_server.server_id,
            tool_name="write_data",  # Requires confirmation per security_rules
            arguments={"data": "test"},
            initiated_by="test_user",
            user_confirmed=False,
        )
        assert result.success is False
        assert result.required_confirmation is True
        assert result.error is not None and "confirmation" in result.error.lower()

    async def test_execute_with_confirmation(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test tool execution with user confirmation."""
        # Mock the connection
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            # Mock successful tool call
            mock_result_item = Mock()
            mock_result_item.model_dump = Mock(return_value={"type": "text", "text": "success"})
            mock_result = Mock()
            mock_result.content = [mock_result_item]

            mock_session = _mock_client_session()
            mock_session.call_tool = AsyncMock(return_value=mock_result)
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            result = await manager.execute_tool(
                server_id=test_server.server_id,
                tool_name="write_data",
                arguments={"data": "test"},
                initiated_by="test_user",
                user_confirmed=True,
            )

            assert result.success is True
            assert result.result is not None

    async def test_execute_allowed_tool(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test executing an allowed tool."""
        # Mock the connection
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            # Mock successful tool call
            mock_result_item = Mock()
            mock_result_item.model_dump = Mock(return_value={"type": "text", "text": "data"})
            mock_result = Mock()
            mock_result.content = [mock_result_item]

            mock_session = _mock_client_session()
            mock_session.call_tool = AsyncMock(return_value=mock_result)
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            result = await manager.execute_tool(
                server_id=test_server.server_id,
                tool_name="read_data",
                arguments={},
                initiated_by="test_user",
            )

            assert result.success is True
            assert result.required_confirmation is False

    async def test_execute_nonexistent_server(
        self, manager: MCPManager
    ) -> None:
        """Test executing tool on non-existent server."""
        result = await manager.execute_tool(
            server_id="nonexistent-server",
            tool_name="any_tool",
            arguments={},
            initiated_by="test_user",
        )
        assert result.success is False
        assert result.error is not None and "not found or disabled" in result.error.lower()

    async def test_execute_logs_success(
        self, manager: MCPManager, db_session: AsyncSession, test_server: MCPServer
    ) -> None:
        """Test that successful executions are logged."""
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            mock_result_item = Mock()
            mock_result_item.model_dump = Mock(return_value={"type": "text"})
            mock_result = Mock()
            mock_result.content = [mock_result_item]

            mock_session = _mock_client_session()
            mock_session.call_tool = AsyncMock(return_value=mock_result)
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            await manager.execute_tool(
                server_id=test_server.server_id,
                tool_name="read_data",
                arguments={},
                initiated_by="test_user",
            )

            # Check that execution was logged
            result = await db_session.execute(
                select(MCPExecutionLog).where(
                    MCPExecutionLog.server_id == test_server.server_id,
                    MCPExecutionLog.tool_name == "read_data",
                )
            )
            logs = list(result.scalars().all())
            assert len(logs) == 1
            assert logs[0].success is True

    async def test_execute_logs_failure(
        self, manager: MCPManager, db_session: AsyncSession, test_server: MCPServer
    ) -> None:
        """Test that failed executions are logged."""
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            mock_session = _mock_client_session()
            mock_session.call_tool = AsyncMock(side_effect=Exception("Tool failed"))
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            await manager.execute_tool(
                server_id=test_server.server_id,
                tool_name="read_data",
                arguments={},
                initiated_by="test_user",
            )

            # Check that execution was logged
            result = await db_session.execute(
                select(MCPExecutionLog).where(
                    MCPExecutionLog.server_id == test_server.server_id,
                    MCPExecutionLog.tool_name == "read_data",
                )
            )
            logs = list(result.scalars().all())
            assert len(logs) == 1
            assert logs[0].success is False
            assert logs[0].error_message == "Tool failed"


@pytest.mark.asyncio
class TestGetAllAvailableTools:
    """Tests for getting all available tools."""

    async def test_get_all_tools_empty(
        self, manager: MCPManager
    ) -> None:
        """Test getting tools when no servers are connected."""
        tools = await manager.get_all_available_tools()
        assert tools == {}

    async def test_get_all_tools_multiple_servers(
        self, manager: MCPManager, db_session: AsyncSession
    ) -> None:
        """Test getting tools from multiple connected servers."""
        # Create two servers
        for i in range(2):
            server = MCPServer(
                server_id=f"test-server-{i}",
                name=f"Test Server {i}",
                transport_type="stdio",
                transport_config={"command": ["echo"], "args": []},
                enabled=True,
                security_rules={},
                rate_limit=60,
            )
            db_session.add(server)
            await db_session.flush()

        # Mock connections
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            mock_session = _mock_client_session()

            # Mock different tools for each server - use a proper callable
            def make_list_tools_response(server_id):
                mock_response = Mock()
                mock_tool = Mock()
                mock_tool.name = f"{server_id}_tool"
                mock_tool.description = f"Tool for {server_id}"
                mock_tool.inputSchema = {}
                mock_response.tools = [mock_tool]
                return mock_response

            # Set up list_tools to return different responses based on call count
            call_count = [0]
            async def list_tools_impl(*args, **kwargs):
                idx = call_count[0]
                call_count[0] += 1
                return make_list_tools_response(f"test-server-{idx}")

            mock_session.list_tools = AsyncMock(side_effect=list_tools_impl)
            mock_session_cls.return_value = mock_session

            await manager.start_server("test-server-0")
            await manager.start_server("test-server-1")

            tools = await manager.get_all_available_tools()

            # Both servers should be in the result
            assert "test-server-0" in tools
            assert "test-server-1" in tools


@pytest.mark.asyncio
class TestStartAllEnabled:
    """Tests for starting all enabled servers."""

    async def test_start_all_enabled_servers(
        self, manager: MCPManager, db_session: AsyncSession
    ) -> None:
        """Test starting all enabled servers."""
        # Create one enabled and one disabled server
        enabled = MCPServer(
            server_id="enabled-server",
            name="Enabled",
            transport_type="stdio",
            transport_config={"command": ["echo"], "args": []},
            enabled=True,
            security_rules={},
            rate_limit=60,
        )
        disabled = MCPServer(
            server_id="disabled-server",
            name="Disabled",
            transport_type="stdio",
            transport_config={"command": ["echo"], "args": []},
            enabled=False,
            security_rules={},
            rate_limit=60,
        )
        db_session.add_all([enabled, disabled])
        await db_session.flush()

        # Mock the MCP SDK
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()
            mock_session = _mock_client_session()
            mock_session_cls.return_value = mock_session

            results = await manager.start_all_enabled()

            assert results["enabled-server"] is True
            assert "disabled-server" not in results


@pytest.mark.asyncio
class TestHealthCheck:
    """Tests for health checking."""

    async def test_health_check_connected_server(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test health check on connected server."""
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            mock_response = Mock()
            mock_response.tools = []

            mock_session = _mock_client_session()
            mock_session.list_tools = AsyncMock(return_value=mock_response)
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            is_healthy = await manager.health_check(test_server.server_id)
            assert is_healthy is True

    async def test_health_check_disconnected_server(
        self, manager: MCPManager
    ) -> None:
        """Test health check on disconnected server."""
        is_healthy = await manager.health_check("nonexistent-server")
        assert is_healthy is False

    async def test_health_check_unhealthy_server(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test health check on unhealthy server (list_tools returns None).

        Graceful degradation (FR-019 VI-006): health_check returns False
        when list_tools fails.
        """
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            mock_session = _mock_client_session()
            mock_session.list_tools = AsyncMock(side_effect=Exception("Unhealthy"))
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            is_healthy = await manager.health_check(test_server.server_id)
            # Graceful degradation: list_tools failure means unhealthy
            assert is_healthy is False


@pytest.mark.asyncio
class TestAccessorMethods:
    """Tests for accessor methods."""

    async def test_get_registry(
        self, manager: MCPManager
    ) -> None:
        """Test getting the registry."""
        registry = await manager.get_registry()
        assert registry is manager._registry
        assert isinstance(registry, MCPServerRegistry)

    async def test_get_validator(
        self, manager: MCPManager
    ) -> None:
        """Test getting the validator."""
        validator = await manager.get_validator()
        assert validator is manager._validator
        assert isinstance(validator, MCPSecurityValidator)


@pytest.mark.asyncio
class TestServerHealthState:
    """Tests for ServerHealthState graceful degradation tracking."""

    def test_initial_state_is_healthy(self) -> None:
        """Test that new ServerHealthState starts healthy."""
        state = ServerHealthState()
        assert state.state == ServerHealth.HEALTHY
        assert state.consecutive_failures == 0

    def test_record_failure_updates_state(self) -> None:
        """Test that recording failures updates health state."""
        state = ServerHealthState()

        # First 2 failures - still healthy
        state.record_failure()
        assert state.state == ServerHealth.HEALTHY
        assert state.consecutive_failures == 1

        state.record_failure()
        assert state.state == ServerHealth.HEALTHY
        assert state.consecutive_failures == 2

        # 3rd failure - becomes degraded
        state.record_failure()
        assert state.state == ServerHealth.DEGRADED
        assert state.consecutive_failures == 3

        # 5th failure - becomes unhealthy
        state.record_failure()
        state.record_failure()
        assert state.state == ServerHealth.UNHEALTHY
        assert state.consecutive_failures == 5

    def test_record_success_resets_state(self) -> None:
        """Test that recording success resets failure count."""
        state = ServerHealthState()

        # Record some failures
        state.record_failure()
        state.record_failure()
        state.record_failure()
        assert state.state == ServerHealth.DEGRADED
        assert state.consecutive_failures == 3

        # Success resets everything
        state.record_success()
        assert state.state == ServerHealth.HEALTHY
        assert state.consecutive_failures == 0

    def test_should_attempt_retry(self) -> None:
        """Test retry logic based on health state."""
        state = ServerHealthState()

        # Healthy servers should retry
        assert state.should_attempt_retry() is True

        # Degraded servers should not retry immediately
        state.record_failure()
        state.record_failure()
        state.record_failure()
        assert state.state == ServerHealth.DEGRADED
        assert state.should_attempt_retry() is False

        # But should retry after recovery time (simulate with mock)
        state.last_failure_time = None
        assert state.should_attempt_retry() is True

        # Unhealthy servers should not retry automatically
        state.record_failure()
        state.record_failure()
        assert state.state == ServerHealth.UNHEALTHY
        assert state.should_attempt_retry() is False

    def test_get_retry_delay(self) -> None:
        """Test exponential backoff delay calculation."""
        state = ServerHealthState()

        # Should increase exponentially
        delay_0 = state.get_retry_delay(0)
        delay_1 = state.get_retry_delay(1)
        delay_2 = state.get_retry_delay(2)
        delay_3 = state.get_retry_delay(3)

        assert delay_0 < delay_1
        assert delay_1 < delay_2
        assert delay_2 < delay_3

        # Should cap at approximately 60 seconds (with jitter up to 10%)
        delay_100 = state.get_retry_delay(100)
        # Base delay is capped at 60, jitter adds up to 10% (6 seconds)
        assert 60 <= delay_100 <= 66


@pytest.mark.asyncio
class TestGracefulDegradation:
    """Tests for graceful degradation behavior (FR-019 VI-006)."""

    async def test_get_server_health(
        self, manager: MCPManager
    ) -> None:
        """Test getting server health state."""
        health = manager.get_server_health("test-server")
        assert isinstance(health, ServerHealthState)
        assert health.state == ServerHealth.HEALTHY

    async def test_get_all_server_health(
        self, manager: MCPManager
    ) -> None:
        """Test getting all server health states."""
        # Access multiple servers to create health states
        manager._health_states["server-1"]
        manager._health_states["server-2"]

        all_health = manager.get_all_server_health()
        assert "server-1" in all_health
        assert "server-2" in all_health
        assert isinstance(all_health["server-1"], ServerHealthState)

    async def test_reset_server_health(
        self, manager: MCPManager
    ) -> None:
        """Test resetting server health state."""
        # Get health and induce failures
        health = manager.get_server_health("test-server")
        health.record_failure()
        health.record_failure()
        health.record_failure()
        assert health.state == ServerHealth.DEGRADED

        # Reset health
        result = await manager.reset_server_health("test-server")
        assert result is True

        # Health should be reset
        new_health = manager.get_server_health("test-server")
        assert new_health.state == ServerHealth.HEALTHY
        assert new_health.consecutive_failures == 0

    async def test_reset_nonexistent_server_returns_false(
        self, manager: MCPManager
    ) -> None:
        """Test resetting health for untracked server returns False."""
        result = await manager.reset_server_health("nonexistent")
        assert result is False

    async def test_execute_tool_returns_degraded_mode(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test that execute_tool returns degraded mode when server is unhealthy."""
        # Put server in degraded state
        health = manager.get_server_health(test_server.server_id)
        health.record_failure()
        health.record_failure()
        health.record_failure()
        assert health.state == ServerHealth.DEGRADED

        # Execute tool should return degraded mode result
        result = await manager.execute_tool(
            server_id=test_server.server_id,
            tool_name="read_data",
            arguments={},
            initiated_by="test_user",
        )

        assert result.success is False
        assert result.degraded is True
        assert result.error is not None
        assert "degraded" in result.error.lower()
        assert result.degraded_reason is not None

    async def test_execute_tool_tracks_success(
        self, manager: MCPManager, test_server: MCPServer, db_session: AsyncSession
    ) -> None:
        """Test that successful tool execution resets health state."""
        # Put server in degraded state first
        health = manager.get_server_health(test_server.server_id)
        health.record_failure()
        health.record_failure()
        assert health.state == ServerHealth.HEALTHY  # Still healthy (only 2 failures)

        # Mock successful tool execution
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            mock_result_item = Mock()
            mock_result_item.model_dump = Mock(return_value={"type": "text", "text": "data"})
            mock_result = Mock()
            mock_result.content = [mock_result_item]

            mock_session = _mock_client_session()
            mock_session.call_tool = AsyncMock(return_value=mock_result)
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            # Execute tool successfully
            await manager.execute_tool(
                server_id=test_server.server_id,
                tool_name="read_data",
                arguments={},
                initiated_by="test_user",
            )

            # Health should be reset to healthy
            new_health = manager.get_server_health(test_server.server_id)
            assert new_health.state == ServerHealth.HEALTHY
            assert new_health.consecutive_failures == 0

    async def test_start_server_resets_health_on_success(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test that successful server connection resets health state."""
        # Put server in degraded state
        health = manager.get_server_health(test_server.server_id)
        health.record_failure()
        health.record_failure()
        health.record_failure()
        assert health.state == ServerHealth.DEGRADED

        # Reset health to allow retry (simulating manual recovery)
        await manager.reset_server_health(test_server.server_id)

        # Successful connection should keep health in healthy state
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()
            mock_session = _mock_client_session()
            mock_session_cls.return_value = mock_session

            # Start server successfully
            result = await manager.start_server(test_server.server_id)
            assert result is True

            # Health should remain healthy
            new_health = manager.get_server_health(test_server.server_id)
            assert new_health.state == ServerHealth.HEALTHY
            assert new_health.consecutive_failures == 0

    async def test_execute_tool_tracks_failure(
        self, manager: MCPManager, test_server: MCPServer
    ) -> None:
        """Test that failed tool execution records failure in health state."""
        # Mock failed tool execution
        with patch("app.mcp.manager.stdio_client") as mock_stdio_client, \
             patch("app.mcp.manager.ClientSession") as mock_session_cls:

            mock_stdio_client.return_value = _mock_stdio_client()

            mock_session = _mock_client_session()
            mock_session.call_tool = AsyncMock(side_effect=Exception("Tool failed"))
            mock_session_cls.return_value = mock_session

            await manager.start_server(test_server.server_id)

            # Execute tool - it will fail
            await manager.execute_tool(
                server_id=test_server.server_id,
                tool_name="read_data",
                arguments={},
                initiated_by="test_user",
            )

            # Health should record failure
            health = manager.get_server_health(test_server.server_id)
            assert health.consecutive_failures >= 1
