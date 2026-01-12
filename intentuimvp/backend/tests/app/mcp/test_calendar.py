"""Tests for Google Calendar MCP Configuration.

Tests GoogleCalendarMCP including:
- Server registration with correct tool names
- Security rules alignment with DEFAULT_SECURITY_RULES
- Tool capabilities and input schemas
- Direct API fallback functionality
"""

import asyncio
import sys

# IMPORTANT: Remove tests.app.mcp from sys.modules if present to avoid shadowing
# the external 'mcp' package
if "tests.app.mcp" in sys.modules:
    del sys.modules["tests.app.mcp"]
if "mcp" in sys.modules and "tests" in getattr(sys.modules["mcp"], "__file__", ""):
    del sys.modules["mcp"]

import json
from collections.abc import AsyncGenerator, Generator
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.mcp.models  # noqa: F401
from app.database import Base
from app.mcp.calendar import GoogleCalendarDirect, GoogleCalendarMCP
from app.mcp.manifest import SecurityLevel
from app.mcp.registry import DEFAULT_SECURITY_RULES, MCPServerRegistry

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


@pytest.mark.asyncio
class TestGoogleCalendarMCPRegistration:
    """Tests for Google Calendar MCP server registration."""

    async def test_register_calendar_server_with_token(
        self, db_session: AsyncSession
    ) -> None:
        """Test registration with OAuth token JSON."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        token_json = json.dumps({
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        })

        result = await calendar_mcp.register_calendar_server(token_json=token_json)

        assert result is True

        # Verify server was registered
        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None
        assert server.server_id == "google-calendar"
        assert server.name == "Google Calendar"
        assert server.description == "Google Calendar integration for event management"
        assert server.transport_type == "stdio"
        assert server.enabled is True
        assert server.version == "1.0.0"

    async def test_register_calendar_server_with_credentials_path(
        self, db_session: AsyncSession, tmp_path
    ) -> None:
        """Test registration with credentials file path."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        # Create a temporary credentials file
        credentials_data = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        }
        credentials_path = tmp_path / "credentials.json"
        credentials_path.write_text(json.dumps(credentials_data))

        result = await calendar_mcp.register_calendar_server(
            credentials_path=str(credentials_path)
        )

        assert result is True

        # Verify server was registered
        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None
        assert server.server_id == "google-calendar"

    async def test_register_calendar_server_without_credentials_fails(
        self, db_session: AsyncSession
    ) -> None:
        """Test registration without credentials fails."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        result = await calendar_mcp.register_calendar_server()

        assert result is False

    async def test_registered_tools_match_default_security_rules(
        self, db_session: AsyncSession
    ) -> None:
        """Test that registered tool names match DEFAULT_SECURITY_RULES."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        token_json = json.dumps({
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        })

        await calendar_mcp.register_calendar_server(token_json=token_json)

        # Get the registered server
        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None

        # Get tool names from capabilities
        registered_tools = {
            tool["name"] for tool in server.capabilities.get("tools", [])
        }

        # Get tool names from DEFAULT_SECURITY_RULES
        default_rule_tools = set(DEFAULT_SECURITY_RULES.get("google-calendar", {}).keys())

        # They should match (except for calendar_delete which is blocked)
        # The registered tools should be a subset of the security rules
        assert registered_tools.issubset(default_rule_tools)

        # Verify specific expected tools are present
        assert "calendar_list" in registered_tools
        assert "calendar_read" in registered_tools
        assert "calendar_create" in registered_tools
        assert "calendar_update" in registered_tools

    async def test_security_rules_match_defaults(
        self, db_session: AsyncSession
    ) -> None:
        """Test that security rules match DEFAULT_SECURITY_RULES."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        token_json = json.dumps({
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        })

        await calendar_mcp.register_calendar_server(token_json=token_json)

        # Get the registered server
        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None

        # Verify security rules match defaults
        default_rules = DEFAULT_SECURITY_RULES.get("google-calendar", {})
        for tool_name, level in default_rules.items():
            assert server.security_rules.get(tool_name) == level.value

    async def test_tool_security_levels(
        self, db_session: AsyncSession
    ) -> None:
        """Test that tools have correct security levels per FR-019."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        token_json = json.dumps({
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        })

        await calendar_mcp.register_calendar_server(token_json=token_json)

        # Get the registered server
        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None

        # Per FR-019, calendar operations should be:
        # - calendar_list: ALLOWED (read operations are safe)
        # - calendar_read: ALLOWED (read operations are safe)
        # - calendar_create: REQUIRES_CONFIRM (write operations need confirmation)
        # - calendar_update: REQUIRES_CONFIRM (write operations need confirmation)
        # - calendar_delete: BLOCKED (dangerous - should not be registered)

        assert server.security_rules.get("calendar_list") == SecurityLevel.ALLOWED.value
        assert server.security_rules.get("calendar_read") == SecurityLevel.ALLOWED.value
        assert server.security_rules.get("calendar_create") == SecurityLevel.REQUIRES_CONFIRM.value
        assert server.security_rules.get("calendar_update") == SecurityLevel.REQUIRES_CONFIRM.value
        assert server.security_rules.get("calendar_delete") == SecurityLevel.BLOCKED.value

    async def test_tool_input_schemas(
        self, db_session: AsyncSession
    ) -> None:
        """Test that tool input schemas are properly defined."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        token_json = json.dumps({
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        })

        await calendar_mcp.register_calendar_server(token_json=token_json)

        # Get the registered server
        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None

        tools_by_name = {
            tool["name"]: tool for tool in server.capabilities.get("tools", [])
        }

        # Verify calendar_list schema
        calendar_list = tools_by_name.get("calendar_list")
        assert calendar_list is not None
        assert "properties" in calendar_list["inputSchema"]
        assert "calendar_id" in calendar_list["inputSchema"]["properties"]
        assert "time_min" in calendar_list["inputSchema"]["properties"]
        assert "time_max" in calendar_list["inputSchema"]["properties"]

        # Verify calendar_create schema
        calendar_create = tools_by_name.get("calendar_create")
        assert calendar_create is not None
        assert "required" in calendar_create["inputSchema"]
        assert "summary" in calendar_create["inputSchema"]["required"]
        assert "start" in calendar_create["inputSchema"]["required"]
        assert "end" in calendar_create["inputSchema"]["required"]


@pytest.mark.asyncio
class TestGoogleCalendarMCPOperations:
    """Tests for Google Calendar MCP operations."""

    async def test_list_events_returns_error_when_not_configured(
        self, db_session: AsyncSession
    ) -> None:
        """Test list_events returns error when server is not configured."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        result = await calendar_mcp.list_events()

        # Server is not registered/enabled, so should return error
        assert result["success"] is False
        assert "error" in result

    async def test_list_events_returns_placeholder_when_server_registered(
        self, db_session: AsyncSession
    ) -> None:
        """Test list_events returns placeholder when server is registered but not connected."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        # Register the server first
        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        result = await calendar_mcp.list_events()

        # Server is registered but not connected to MCP server
        assert result["success"] is True
        assert "events" in result
        assert "Google Calendar integration ready" in result["message"]

    async def test_create_event_returns_placeholder(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event returns placeholder when server is not connected."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        # Register the server first
        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        result = await calendar_mcp.create_event(
            summary="Test Event",
            start="2026-01-13T10:00:00Z",
            end="2026-01-13T11:00:00Z",
        )

        assert result["success"] is True
        assert "Google Calendar integration ready" in result["message"]

    async def test_sync_with_task_dag_returns_placeholder(
        self, db_session: AsyncSession
    ) -> None:
        """Test sync_with_task_dag returns placeholder."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        result = await calendar_mcp.sync_with_task_dag("task-dag-123")

        assert result["success"] is True
        assert "Task DAG sync ready" in result["message"]


@pytest.mark.asyncio
class TestGoogleCalendarDirect:
    """Tests for GoogleCalendarDirect fallback integration."""

    def test_initialization_with_credentials_dict(self) -> None:
        """Test initialization with OAuth credentials dictionary."""
        credentials_dict = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        }

        with patch("app.mcp.calendar.google.oauth2.credentials.Credentials"):
            calendar_direct = GoogleCalendarDirect(credentials_dict)

            assert calendar_direct._credentials is not None
            assert calendar_direct._service is None

    def test_scopes_defined(self) -> None:
        """Test that OAuth scopes are properly defined."""
        assert GoogleCalendarDirect.SCOPES == [
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events",
        ]

    async def test_list_events_without_authentication_fails_gracefully(
        self, db_session: AsyncSession
    ) -> None:
        """Test list_events fails gracefully without valid credentials."""
        credentials_dict = {
            "token": "invalid_token",
            "refresh_token": "invalid_refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "invalid_client",
            "client_secret": "invalid_secret",
        }

        # Patch to avoid actual Google API calls
        with patch("app.mcp.calendar.google.oauth2.credentials.Credentials"):
            calendar_direct = GoogleCalendarDirect(credentials_dict)

            # Mock failed authentication
            with patch.object(calendar_direct, "_ensure_authenticated", side_effect=Exception("Auth failed")):
                result = await calendar_direct.list_events()

                assert result["success"] is False
                assert "error" in result


@pytest.mark.asyncio
class TestFR020Compliance:
    """Tests for FR-020 Google Calendar MCP Integration compliance."""

    async def test_google_calendar_mcp_configured(
        self, db_session: AsyncSession
    ) -> None:
        """Test that Google Calendar MCP can be configured (FR-020 AC1)."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        token_json = json.dumps({
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
        })

        result = await calendar_mcp.register_calendar_server(token_json=token_json)

        assert result is True

        # Verify server is registered and enabled
        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None
        assert server.enabled is True

    async def test_calendar_list_tool_is_allowed(
        self, db_session: AsyncSession
    ) -> None:
        """Test that calendar list queries are allowed (FR-020 AC1)."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None
        assert server.security_rules.get("calendar_list") == SecurityLevel.ALLOWED.value

    async def test_calendar_create_requires_confirmation(
        self, db_session: AsyncSession
    ) -> None:
        """Test that calendar updates require confirmation (FR-020 AC2)."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None
        assert server.security_rules.get("calendar_create") == SecurityLevel.REQUIRES_CONFIRM.value
        assert server.security_rules.get("calendar_update") == SecurityLevel.REQUIRES_CONFIRM.value

    async def test_task_dag_sync_method_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Test that Task DAG sync method exists (FR-020 AC3)."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        # Verify the method exists
        assert hasattr(calendar_mcp, "sync_with_task_dag")

        # Call it
        result = await calendar_mcp.sync_with_task_dag("test-task-dag")

        # Should return success (even if placeholder)
        assert result["success"] is True
