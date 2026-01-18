"""Tests for Capability Registry.

Tests CapabilityRegistry including:
- Capability indexing and discovery
- Search and filtering
- Security level queries
- Introspection methods
- Statistics
"""

import sys

# IMPORTANT: Remove tests.app.mcp from sys.modules if present to avoid shadowing
# the external 'mcp' package.
if "tests.app.mcp" in sys.modules:
    del sys.modules["tests.app.mcp"]
if "mcp" in sys.modules and "tests" in getattr(sys.modules["mcp"], "__file__", ""):
    del sys.modules["mcp"]

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.mcp.models  # noqa: F401
from app.database import Base
from app.mcp.capability_registry import (
    Capability,
    CapabilityRegistry,
    CapabilityStats,
    CapabilityType,
    UnavailableCapability,
)
from app.mcp.manifest import SecurityCategory, SecurityLevel
from app.mcp.models import MCPExecutionLog, MCPServer

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
def registry(db_session: AsyncSession) -> CapabilityRegistry:
    """Provide a CapabilityRegistry instance."""
    return CapabilityRegistry(db_session)


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
                {"name": "read_data", "description": "Read data from source"},
                {"name": "write_data", "description": "Write data to target"},
                {"name": "calendar_create", "description": "Create calendar event"},
            ],
            "resources": [
                {"name": "data_file", "uri": "file://data.json", "description": "Data file"},
            ],
            "prompts": [
                {"name": "greeting", "description": "Greeting prompt", "arguments": []},
            ],
        },
        security_rules={
            "read_data": "allowed",
            "write_data": "requires_confirm",
            "calendar_create": "requires_confirm",
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
        capabilities={
            "tools": [
                {"name": "blocked_tool", "description": "A blocked tool"},
            ],
        },
        security_rules={
            "blocked_tool": "blocked",
        },
        enabled=False,
        rate_limit=60,
    )
    db_session.add(server)
    await db_session.flush()
    return server


@pytest_asyncio.fixture
async def server_with_blocked(db_session: AsyncSession) -> MCPServer:
    """Create a server with blocked tools."""
    server = MCPServer(
        server_id="blocked-server",
        name="Server with Blocked Tools",
        transport_type="stdio",
        transport_config={"command": ["echo"], "args": []},
        capabilities={
            "tools": [
                {"name": "safe_tool", "description": "A safe tool"},
                {"name": "dangerous_tool", "description": "A dangerous tool"},
            ],
        },
        security_rules={
            "safe_tool": "allowed",
            "dangerous_tool": "blocked",
        },
        enabled=True,
        rate_limit=60,
    )
    db_session.add(server)
    await db_session.flush()
    return server


class TestCapabilityDataclass:
    """Tests for Capability dataclass."""

    def test_capability_creation(self) -> None:
        """Test creating a Capability."""
        cap = Capability(
            id="test-server:tool:read_data",
            name="read_data",
            type=CapabilityType.TOOL,
            server_id="test-server",
            description="Read data",
            security_level=SecurityLevel.ALLOWED,
            server_name="Test Server",
            server_enabled=True,
        )
        assert cap.id == "test-server:tool:read_data"
        assert cap.name == "read_data"
        assert cap.type == CapabilityType.TOOL
        assert cap.security_level == SecurityLevel.ALLOWED

    def test_capability_to_dict(self) -> None:
        """Test Capability serialization."""
        cap = Capability(
            id="test-server:tool:read_data",
            name="read_data",
            type=CapabilityType.TOOL,
            server_id="test-server",
            description="Read data",
            category=SecurityCategory.FILE,
            security_level=SecurityLevel.ALLOWED,
            server_name="Test Server",
            server_enabled=True,
            input_schema={"type": "object"},
        )
        data = cap.to_dict()
        assert data["id"] == "test-server:tool:read_data"
        assert data["name"] == "read_data"
        assert data["type"] == "tool"
        assert data["security_level"] == "allowed"
        assert data["category"] == "file"
        assert data["input_schema"] == {"type": "object"}


class TestCapabilityStats:
    """Tests for CapabilityStats dataclass."""

    def test_stats_creation(self) -> None:
        """Test creating CapabilityStats."""
        stats = CapabilityStats(
            total_capabilities=10,
            total_tools=5,
            total_resources=3,
            total_prompts=2,
            total_servers=2,
            enabled_servers=1,
        )
        assert stats.total_capabilities == 10
        assert stats.total_tools == 5
        assert stats.enabled_servers == 1

    def test_stats_to_dict(self) -> None:
        """Test CapabilityStats serialization."""
        stats = CapabilityStats(
            total_capabilities=10,
            total_tools=5,
            total_resources=3,
            total_prompts=2,
            total_servers=2,
            enabled_servers=1,
            by_security_level={"allowed": 5, "requires_confirm": 4, "blocked": 1},
            by_server={"test-server": 6, "other-server": 4},
        )
        data = stats.to_dict()
        assert data["total_capabilities"] == 10
        assert data["by_security_level"]["allowed"] == 5
        assert data["by_server"]["test-server"] == 6


@pytest.mark.asyncio
class TestCapabilityRegistryInit:
    """Tests for CapabilityRegistry initialization."""

    async def test_initialization(self, db_session: AsyncSession) -> None:
        """Test registry initialization."""
        registry = CapabilityRegistry(db_session)
        assert registry._session is db_session
        assert registry._capability_cache is None
        assert registry._cache_valid is False

    async def test_cache_invalidation(self, registry: CapabilityRegistry) -> None:
        """Test cache invalidation."""
        registry._cache_valid = True
        registry._capability_cache = {"test": Capability(
            id="test", name="test", type=CapabilityType.TOOL, server_id="s1"
        )}

        registry.invalidate_cache()

        assert registry._cache_valid is False
        assert registry._capability_cache is None


@pytest.mark.asyncio
class TestGetAllCapabilities:
    """Tests for getting all capabilities."""

    async def test_get_all_empty(self, registry: CapabilityRegistry) -> None:
        """Test getting capabilities when no servers exist."""
        capabilities = await registry.get_all_capabilities()
        assert capabilities == []

    async def test_get_all_with_servers(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test getting all capabilities from servers."""
        capabilities = await registry.get_all_capabilities()

        # Should have 3 tools + 1 resource + 1 prompt = 5 capabilities
        assert len(capabilities) == 5

        # Check tool extraction
        tool_names = [c.name for c in capabilities if c.type == CapabilityType.TOOL]
        assert "read_data" in tool_names
        assert "write_data" in tool_names
        assert "calendar_create" in tool_names

        # Check resource extraction
        resource_names = [c.name for c in capabilities if c.type == CapabilityType.RESOURCE]
        assert "data_file" in resource_names

        # Check prompt extraction
        prompt_names = [c.name for c in capabilities if c.type == CapabilityType.PROMPT]
        assert "greeting" in prompt_names

    async def test_get_all_excludes_disabled_by_default(
        self, registry: CapabilityRegistry, test_server: MCPServer, disabled_server: MCPServer
    ) -> None:
        """Test that disabled servers are excluded by default."""
        capabilities = await registry.get_all_capabilities(include_disabled=False)

        server_ids = {c.server_id for c in capabilities}
        assert "test-server" in server_ids
        assert "disabled-server" not in server_ids

    async def test_get_all_includes_disabled_when_requested(
        self, registry: CapabilityRegistry, test_server: MCPServer, disabled_server: MCPServer
    ) -> None:
        """Test that disabled servers can be included."""
        capabilities = await registry.get_all_capabilities(include_disabled=True)

        server_ids = {c.server_id for c in capabilities}
        assert "test-server" in server_ids
        assert "disabled-server" in server_ids


@pytest.mark.asyncio
class TestGetCapability:
    """Tests for getting a specific capability."""

    async def test_get_existing_capability(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test getting an existing capability by ID."""
        capability = await registry.get_capability("test-server:tool:read_data")

        assert capability is not None
        assert capability.name == "read_data"
        assert capability.type == CapabilityType.TOOL
        assert capability.server_id == "test-server"

    async def test_get_nonexistent_capability(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test getting a capability that doesn't exist."""
        capability = await registry.get_capability("nonexistent:tool:fake")
        assert capability is None


@pytest.mark.asyncio
class TestFindCapabilityByName:
    """Tests for finding capabilities by name."""

    async def test_find_exact_match(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test finding capability with exact name match."""
        results = await registry.find_capability_by_name("read_data")

        assert len(results) == 1
        assert results[0].name == "read_data"

    async def test_find_partial_match(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test finding capabilities with partial name match."""
        results = await registry.find_capability_by_name("data")

        # Should match read_data, write_data, data_file
        assert len(results) == 3
        names = [r.name for r in results]
        assert "read_data" in names
        assert "write_data" in names
        assert "data_file" in names

    async def test_find_by_type_filter(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test finding capabilities filtered by type."""
        results = await registry.find_capability_by_name("data", CapabilityType.TOOL)

        # Should only match tools: read_data, write_data
        assert len(results) == 2
        for r in results:
            assert r.type == CapabilityType.TOOL


@pytest.mark.asyncio
class TestGetCapabilitiesByFilters:
    """Tests for filtering capabilities."""

    async def test_by_server(
        self, registry: CapabilityRegistry, test_server: MCPServer, server_with_blocked: MCPServer
    ) -> None:
        """Test getting capabilities by server."""
        results = await registry.get_capabilities_by_server("test-server")

        assert all(c.server_id == "test-server" for c in results)
        assert len(results) == 5  # 3 tools + 1 resource + 1 prompt

    async def test_by_type(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test getting capabilities by type."""
        tools = await registry.get_capabilities_by_type(CapabilityType.TOOL)
        resources = await registry.get_capabilities_by_type(CapabilityType.RESOURCE)
        prompts = await registry.get_capabilities_by_type(CapabilityType.PROMPT)

        assert all(c.type == CapabilityType.TOOL for c in tools)
        assert all(c.type == CapabilityType.RESOURCE for c in resources)
        assert all(c.type == CapabilityType.PROMPT for c in prompts)

    async def test_by_security_level(
        self, registry: CapabilityRegistry, test_server: MCPServer, server_with_blocked: MCPServer
    ) -> None:
        """Test getting capabilities by security level."""
        allowed = await registry.get_capabilities_by_security_level(SecurityLevel.ALLOWED)
        blocked = await registry.get_capabilities_by_security_level(SecurityLevel.BLOCKED)

        assert all(c.security_level == SecurityLevel.ALLOWED for c in allowed)
        assert all(c.security_level == SecurityLevel.BLOCKED for c in blocked)


@pytest.mark.asyncio
class TestSearchCapabilities:
    """Tests for capability search."""

    async def test_search_by_query(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test searching capabilities by text query."""
        results = await registry.search_capabilities(query="calendar")

        assert len(results) == 1
        assert results[0].name == "calendar_create"

    async def test_search_multiple_filters(
        self, registry: CapabilityRegistry, test_server: MCPServer, server_with_blocked: MCPServer
    ) -> None:
        """Test searching with multiple filters."""
        results = await registry.search_capabilities(
            capability_type=CapabilityType.TOOL,
            security_level=SecurityLevel.ALLOWED,
        )

        for r in results:
            assert r.type == CapabilityType.TOOL
            assert r.security_level == SecurityLevel.ALLOWED

    async def test_search_includes_description(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test that search includes description text."""
        results = await registry.search_capabilities(query="source")

        # Should match "Read data from source"
        assert len(results) == 1
        assert results[0].name == "read_data"


@pytest.mark.asyncio
class TestFindServerForTool:
    """Tests for finding server by tool name."""

    async def test_find_existing_tool(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test finding server for existing tool."""
        server_id = await registry.find_server_for_tool("read_data")
        assert server_id == "test-server"

    async def test_find_nonexistent_tool(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test finding server for non-existent tool."""
        server_id = await registry.find_server_for_tool("fake_tool")
        assert server_id is None


@pytest.mark.asyncio
class TestGetUnavailableCapabilities:
    """Tests for unavailable capabilities."""

    async def test_disabled_server_unavailable(
        self, registry: CapabilityRegistry, test_server: MCPServer, disabled_server: MCPServer
    ) -> None:
        """Test that capabilities from disabled servers are reported as unavailable."""
        unavailable = await registry.get_unavailable_capabilities()

        disabled_caps = [u for u in unavailable if u.capability.server_id == "disabled-server"]
        assert len(disabled_caps) > 0
        for u in disabled_caps:
            assert "disabled" in u.reason.lower()
            assert u.can_be_enabled is True

    async def test_blocked_capability_unavailable(
        self, registry: CapabilityRegistry, server_with_blocked: MCPServer
    ) -> None:
        """Test that blocked capabilities are reported as unavailable."""
        unavailable = await registry.get_unavailable_capabilities()

        blocked_caps = [u for u in unavailable if u.capability.security_level == SecurityLevel.BLOCKED]
        assert len(blocked_caps) > 0
        for u in blocked_caps:
            assert "blocked" in u.reason.lower()
            assert u.can_be_enabled is False


@pytest.mark.asyncio
class TestCanPerformAction:
    """Tests for action possibility checking."""

    async def test_action_possible(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test checking a possible action."""
        result = await registry.can_perform_action("read some data")

        assert result["possible"] is True
        assert len(result["capabilities"]) > 0

    async def test_action_not_possible(
        self, registry: CapabilityRegistry, test_server: MCPServer
    ) -> None:
        """Test checking an impossible action."""
        result = await registry.can_perform_action("quantum teleportation experiment")

        assert result["possible"] is False
        assert result["blocked_reason"] is not None


@pytest.mark.asyncio
class TestGetStats:
    """Tests for capability statistics."""

    async def test_stats_empty(self, registry: CapabilityRegistry) -> None:
        """Test stats with no servers."""
        stats = await registry.get_stats()

        assert stats.total_capabilities == 0
        assert stats.total_servers == 0

    async def test_stats_with_servers(
        self, registry: CapabilityRegistry, test_server: MCPServer, disabled_server: MCPServer
    ) -> None:
        """Test stats with servers."""
        stats = await registry.get_stats()

        assert stats.total_capabilities > 0
        assert stats.total_servers == 2
        assert stats.enabled_servers == 1
        assert stats.total_tools >= 3  # At least from test_server
        assert stats.total_resources >= 1
        assert stats.total_prompts >= 1

    async def test_stats_by_security_level(
        self, registry: CapabilityRegistry, test_server: MCPServer, server_with_blocked: MCPServer
    ) -> None:
        """Test stats breakdown by security level."""
        stats = await registry.get_stats()

        assert "allowed" in stats.by_security_level
        assert "requires_confirm" in stats.by_security_level or "blocked" in stats.by_security_level


@pytest.mark.asyncio
class TestGetIntegrationStatus:
    """Tests for integration status."""

    async def test_integration_status(
        self, registry: CapabilityRegistry, test_server: MCPServer, disabled_server: MCPServer
    ) -> None:
        """Test getting integration status."""
        integrations = await registry.get_integration_status()

        assert len(integrations) == 2

        # Find test-server
        test_integration = next(i for i in integrations if i["server_id"] == "test-server")
        assert test_integration["enabled"] is True
        assert test_integration["capabilities"]["tools"] == 3
        assert test_integration["capabilities"]["resources"] == 1
        assert test_integration["capabilities"]["prompts"] == 1

        # Find disabled-server
        disabled_integration = next(i for i in integrations if i["server_id"] == "disabled-server")
        assert disabled_integration["enabled"] is False


@pytest.mark.asyncio
class TestCategoryInference:
    """Tests for category inference from capability names."""

    async def test_infer_calendar(self, registry: CapabilityRegistry) -> None:
        """Test inferring calendar category."""
        category = registry._infer_category("calendar_create")
        assert category == SecurityCategory.CALENDAR

    async def test_infer_file(self, registry: CapabilityRegistry) -> None:
        """Test inferring file category."""
        category = registry._infer_category("file_read")
        assert category == SecurityCategory.FILE

    async def test_infer_network(self, registry: CapabilityRegistry) -> None:
        """Test inferring network category."""
        category = registry._infer_category("http_fetch")
        assert category == SecurityCategory.NETWORK

    async def test_infer_unknown(self, registry: CapabilityRegistry) -> None:
        """Test unknown category inference."""
        category = registry._infer_category("some_random_tool")
        assert category == SecurityCategory.UNKNOWN


@pytest.mark.asyncio
class TestUsageStats:
    """Tests for usage statistics."""

    async def test_usage_stats_empty(self, registry: CapabilityRegistry) -> None:
        """Test usage stats with no execution logs."""
        usage = await registry.get_usage_stats()
        assert usage == {}

    async def test_usage_stats_with_logs(
        self, registry: CapabilityRegistry, db_session: AsyncSession, test_server: MCPServer
    ) -> None:
        """Test usage stats with execution logs."""
        # Add some execution logs
        log1 = MCPExecutionLog(
            server_id="test-server",
            tool_name="read_data",
            initiated_by="test_user",
            confirmed=False,
            success=True,
        )
        log2 = MCPExecutionLog(
            server_id="test-server",
            tool_name="read_data",
            initiated_by="test_user",
            confirmed=False,
            success=True,
        )
        log3 = MCPExecutionLog(
            server_id="test-server",
            tool_name="read_data",
            initiated_by="test_user",
            confirmed=False,
            success=False,
            error_message="Failed",
        )
        db_session.add_all([log1, log2, log3])
        await db_session.flush()

        usage = await registry.get_usage_stats()

        assert "test-server:read_data" in usage
        assert usage["test-server:read_data"]["total_calls"] == 3
        assert usage["test-server:read_data"]["success_count"] == 2
