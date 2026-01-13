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
from unittest.mock import AsyncMock, patch

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
        assert "calendar_query" in registered_tools
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

    async def test_sync_with_task_dag_returns_error_when_server_not_registered(
        self, db_session: AsyncSession
    ) -> None:
        """Test sync_with_task_dag fails when server is not registered."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        task_dag = {
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Task 1",
                    "calendar_suggestion": {
                        "summary": "Task 1",
                        "start": "2026-01-13T10:00:00Z",
                        "end": "2026-01-13T11:00:00Z",
                    },
                }
            ]
        }

        result = await calendar_mcp.sync_with_task_dag(task_dag=task_dag)

        assert result["success"] is False
        assert result.get("requires_confirmation") is not True
        assert result.get("error") == "Google Calendar server not registered"

    async def test_list_events_returns_error_when_not_configured(
        self, db_session: AsyncSession
    ) -> None:
        """Test list_events returns error when server is not configured."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        result = await calendar_mcp.list_events()

        # Server is not registered/enabled, so should return error
        assert result["success"] is False
        assert "error" in result

    async def test_list_events_executes_tool_when_server_registered(
        self, db_session: AsyncSession
    ) -> None:
        """Test list_events executes the MCP tool when server is registered."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        # Register the server first
        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        events_payload = {"events": [{"id": "event-1", "summary": "Standup"}]}
        with patch.object(
            calendar_mcp._manager,
            "execute_tool",
            new_callable=AsyncMock,
        ) as execute_tool:
            execute_tool.return_value = ToolExecutionResult(
                success=True,
                result=[
                    {
                        "type": "text",
                        "text": json.dumps(events_payload),
                    }
                ],
            )

            result = await calendar_mcp.list_events()

            execute_tool.assert_awaited_once()
            called_args = execute_tool.call_args.kwargs
            assert called_args["server_id"] == "google-calendar"
            assert called_args["tool_name"] == "calendar_list"
            assert called_args["arguments"]["calendar_id"] == "primary"
            assert isinstance(called_args["arguments"]["time_min"], str)
            assert isinstance(called_args["arguments"]["time_max"], str)

            assert result["success"] is True
            assert result["events"] == events_payload["events"]

    async def test_create_event_requires_confirmation_without_user_confirmed(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event requires confirmation when user_confirmed=False."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        # Register the server first
        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        # Mock the execute_tool to simulate REQUIRES_CONFIRM behavior
        from app.mcp.manager import ToolExecutionResult
        with patch.object(
            calendar_mcp._manager,
            "execute_tool",
            return_value=ToolExecutionResult(
                success=False,
                error="User confirmation required",
                required_confirmation=True,
            )
        ):
            result = await calendar_mcp.create_event(
                summary="Test Event",
                start="2026-01-13T10:00:00Z",
                end="2026-01-13T11:00:00Z",
                user_confirmed=False,
            )

            assert result["success"] is False
            assert result.get("requires_confirmation") is True
            assert "pending_action" in result
            assert result["pending_action"]["summary"] == "Test Event"
            assert "confirmation required" in result["message"].lower()

    async def test_sync_with_task_dag_requires_confirmation(
        self, db_session: AsyncSession
    ) -> None:
        """Test sync_with_task_dag requires confirmation by default."""
        calendar_mcp = GoogleCalendarMCP(db_session)
        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        task_dag = {
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Task 1",
                    "calendar_suggestion": {
                        "summary": "Task 1",
                        "start": "2026-01-13T10:00:00Z",
                        "end": "2026-01-13T11:00:00Z",
                    },
                }
            ]
        }

        with patch.object(
            calendar_mcp._manager,
            "start_server",
            new_callable=AsyncMock,
        ) as mock_start:
            mock_start.return_value = True
            result = await calendar_mcp.sync_with_task_dag(task_dag=task_dag)

        assert result["success"] is False
        assert result.get("requires_confirmation") is True
        assert result.get("pending_actions")

    async def test_sync_with_task_dag_creates_events(
        self, db_session: AsyncSession
    ) -> None:
        """Test sync_with_task_dag creates calendar events when confirmed."""
        calendar_mcp = GoogleCalendarMCP(db_session)
        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        task_dag = {
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Task 1",
                    "calendar_suggestion": {
                        "summary": "Plan kickoff",
                        "start": "2026-01-14T09:00:00Z",
                        "end": "2026-01-14T10:00:00Z",
                        "description": "Prep the kickoff agenda.",
                        "calendar_id": "primary",
                    },
                },
                {
                    "id": "task-2",
                    "title": "Task 2",
                    "calendar_suggestion": {
                        "title": "Design review",
                        "start_time": "2026-01-15T14:00:00Z",
                        "end_time": "2026-01-15T15:00:00Z",
                        "calendarId": "work",
                    },
                },
            ]
        }

        with patch.object(
            calendar_mcp._manager,
            "start_server",
            new_callable=AsyncMock,
        ) as mock_start:
            mock_start.return_value = True
            with patch.object(
                calendar_mcp,
                "create_event",
                new_callable=AsyncMock,
            ) as mock_create:
                mock_create.side_effect = [
                    {
                        "success": True,
                        "event": {"id": "event-1", "htmlLink": "https://example.com/event-1"},
                    },
                    {"success": True, "event": {"id": "event-2"}},
                ]

                result = await calendar_mcp.sync_with_task_dag(
                    task_dag=task_dag,
                    calendar_id="primary",
                    user_confirmed=True,
                    initiated_by="tester",
                )

        assert result["success"] is True
        assert len(result["created_events"]) == 2
        assert result["failed_events"] == []
        assert result["created_events"][0]["event_id"] == "event-1"
        assert result["created_events"][0]["event_url"] == "https://example.com/event-1"
        assert result["created_events"][1]["event_id"] == "event-2"

        mock_create.assert_any_call(
            summary="Plan kickoff",
            start="2026-01-14T09:00:00Z",
            end="2026-01-14T10:00:00Z",
            description="Prep the kickoff agenda.",
            calendar_id="primary",
            user_confirmed=True,
            initiated_by="tester",
        )
        mock_create.assert_any_call(
            summary="Design review",
            start="2026-01-15T14:00:00Z",
            end="2026-01-15T15:00:00Z",
            description=None,
            calendar_id="work",
            user_confirmed=True,
            initiated_by="tester",
        )


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
        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        # Verify the method exists
        assert hasattr(calendar_mcp, "sync_with_task_dag")

        # Call it
        with patch.object(
            calendar_mcp._manager,
            "start_server",
            new_callable=AsyncMock,
        ) as mock_start:
            mock_start.return_value = True
            result = await calendar_mcp.sync_with_task_dag(
                task_dag={
                    "tasks": [
                        {
                            "id": "task-1",
                            "title": "Task 1",
                            "calendar_suggestion": {
                                "summary": "Task 1",
                                "start": "2026-01-20T10:00:00Z",
                                "end": "2026-01-20T11:00:00Z",
                            },
                        }
                    ]
                }
            )

        assert result["success"] is False
        assert result.get("requires_confirmation") is True


@pytest.mark.asyncio
class TestCalendarQuery:
    """Tests for calendar_query tool functionality."""

    async def test_calendar_query_tool_registered(
        self, db_session: AsyncSession
    ) -> None:
        """Test that calendar_query tool is registered with correct schema."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None

        tools_by_name = {
            tool["name"]: tool for tool in server.capabilities.get("tools", [])
        }

        # Verify calendar_query tool exists
        calendar_query = tools_by_name.get("calendar_query")
        assert calendar_query is not None
        assert "Query/search events" in calendar_query["description"]

        # Verify input schema
        schema = calendar_query["inputSchema"]
        assert "properties" in schema
        assert "query" in schema["properties"]
        assert "calendar_id" in schema["properties"]
        assert "time_min" in schema["properties"]
        assert "time_max" in schema["properties"]

        # Verify required parameters
        assert "required" in schema
        assert "query" in schema["required"]

    async def test_calendar_query_security_level_is_allowed(
        self, db_session: AsyncSession
    ) -> None:
        """Test that calendar_query has ALLOWED security level (read operation)."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        registry = MCPServerRegistry(db_session)
        server = await registry.get_server("google-calendar")

        assert server is not None
        assert server.security_rules.get("calendar_query") == SecurityLevel.ALLOWED.value

    async def test_query_events_method_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Test that query_events method exists on GoogleCalendarMCP."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        # Verify the method exists
        assert hasattr(calendar_mcp, "query_events")

    async def test_query_events_returns_error_when_not_configured(
        self, db_session: AsyncSession
    ) -> None:
        """Test query_events returns error when server is not configured."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        result = await calendar_mcp.query_events(query="meeting")

        # Server is not registered/enabled, so should return error
        assert result["success"] is False
        assert "error" in result

    async def test_query_events_executes_tool_when_server_registered(
        self, db_session: AsyncSession
    ) -> None:
        """Test query_events executes the MCP tool when server is registered."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        # Register the server first
        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        events_payload = {"events": [{"id": "event-1", "summary": "Team meeting"}]}
        with patch.object(
            calendar_mcp._manager,
            "execute_tool",
            new_callable=AsyncMock,
        ) as execute_tool:
            execute_tool.return_value = ToolExecutionResult(
                success=True,
                result=[
                    {
                        "type": "text",
                        "text": json.dumps(events_payload),
                    }
                ],
            )

            result = await calendar_mcp.query_events(query="team meeting")

            execute_tool.assert_awaited_once()
            called_args = execute_tool.call_args.kwargs
            assert called_args["server_id"] == "google-calendar"
            assert called_args["tool_name"] == "calendar_query"
            assert called_args["arguments"]["query"] == "team meeting"

            assert result["success"] is True
            assert result["events"] == events_payload["events"]
            assert result["query"] == "team meeting"

    async def test_query_events_with_custom_time_range(
        self, db_session: AsyncSession
    ) -> None:
        """Test query_events accepts custom time range parameters."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        with patch.object(
            calendar_mcp._manager,
            "execute_tool",
            new_callable=AsyncMock,
        ) as execute_tool:
            execute_tool.return_value = ToolExecutionResult(
                success=True,
                result=[{"type": "text", "text": json.dumps({"events": []})}],
            )

            result = await calendar_mcp.query_events(
                query="standup",
                time_min="2026-01-01T00:00:00Z",
                time_max="2026-01-31T23:59:59Z",
            )

            execute_tool.assert_awaited_once()
            called_args = execute_tool.call_args.kwargs
            assert called_args["arguments"]["time_min"] == "2026-01-01T00:00:00Z"
            assert called_args["arguments"]["time_max"] == "2026-01-31T23:59:59Z"

            assert result["success"] is True
            assert result["query"] == "standup"

    async def test_google_calendar_direct_query_events_method_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Test that query_events method exists on GoogleCalendarDirect."""
        credentials_dict = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        }

        with patch("app.mcp.calendar.google.oauth2.credentials.Credentials"):
            calendar_direct = GoogleCalendarDirect(credentials_dict)
            assert hasattr(calendar_direct, "query_events")

    async def test_google_calendar_direct_query_events_without_auth_fails_gracefully(
        self, db_session: AsyncSession
    ) -> None:
        """Test GoogleCalendarDirect query_events fails gracefully without valid credentials."""
        credentials_dict = {
            "token": "invalid_token",
            "refresh_token": "invalid_refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "invalid_client",
            "client_secret": "invalid_secret",
        }

        with patch("app.mcp.calendar.google.oauth2.credentials.Credentials"):
            calendar_direct = GoogleCalendarDirect(credentials_dict)

            # Mock failed authentication
            with patch.object(calendar_direct, "_ensure_authenticated", side_effect=Exception("Auth failed")):
                result = await calendar_direct.query_events(query="meeting")

                assert result["success"] is False
                assert "error" in result


@pytest.mark.asyncio
class TestCalendarCreateTool:
    """Tests for calendar_create tool implementation (T3-F6.2)."""

    async def test_create_event_server_not_registered(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event returns error when server is not registered."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        result = await calendar_mcp.create_event(
            summary="Test Event",
            start="2026-01-13T10:00:00Z",
            end="2026-01-13T11:00:00Z",
        )

        assert result["success"] is False
        assert "not registered" in result["error"]

    async def test_create_event_server_disabled(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event returns error when server is disabled."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        # Register and then disable the server
        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        # Disable the server
        registry = MCPServerRegistry(db_session)
        await registry.disable_server("google-calendar")

        result = await calendar_mcp.create_event(
            summary="Test Event",
            start="2026-01-13T10:00:00Z",
            end="2026-01-13T11:00:00Z",
        )

        assert result["success"] is False
        assert "disabled" in result["error"]

    async def test_create_event_with_user_confirmed_calls_mcp(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event with user_confirmed=True executes the MCP tool."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        # Mock successful execution
        mock_result = ToolExecutionResult(
            success=True,
            result=[{
                "type": "text",
                "text": '{"id": "event123", "summary": "Test Event", "start": "2026-01-13T10:00:00Z", "end": "2026-01-13T11:00:00Z"}'
            }],
            required_confirmation=True,
        )

        with patch.object(calendar_mcp._manager, "execute_tool", return_value=mock_result) as mock_execute:
            result = await calendar_mcp.create_event(
                summary="Test Event",
                start="2026-01-13T10:00:00Z",
                end="2026-01-13T11:00:00Z",
                description="A test event",
                user_confirmed=True,
                initiated_by="test_user",
            )

            # Verify execute_tool was called with correct arguments
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            assert call_args.kwargs["server_id"] == "google-calendar"
            assert call_args.kwargs["tool_name"] == "calendar_create"
            assert call_args.kwargs["user_confirmed"] is True
            assert call_args.kwargs["initiated_by"] == "test_user"
            assert call_args.kwargs["arguments"]["summary"] == "Test Event"
            assert call_args.kwargs["arguments"]["description"] == "A test event"

            # Verify successful result
            assert result["success"] is True
            assert result["event"]["id"] == "event123"
            assert "successfully" in result["message"].lower()

    async def test_create_event_handles_degraded_mode(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event handles server degraded mode (FR-019)."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        # Mock degraded execution
        mock_result = ToolExecutionResult(
            success=False,
            error="Server google-calendar is degraded",
            degraded=True,
            degraded_reason="MCP server is in degraded state after 3 consecutive failures",
        )

        with patch.object(calendar_mcp._manager, "execute_tool", return_value=mock_result):
            result = await calendar_mcp.create_event(
                summary="Test Event",
                start="2026-01-13T10:00:00Z",
                end="2026-01-13T11:00:00Z",
                user_confirmed=True,
            )

            assert result["success"] is False
            assert result.get("degraded") is True
            assert "degraded_reason" in result

    async def test_create_event_handles_execution_error(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event handles MCP tool execution errors."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        # Mock failed execution
        mock_result = ToolExecutionResult(
            success=False,
            error="Calendar API rate limit exceeded",
        )

        with patch.object(calendar_mcp._manager, "execute_tool", return_value=mock_result):
            result = await calendar_mcp.create_event(
                summary="Test Event",
                start="2026-01-13T10:00:00Z",
                end="2026-01-13T11:00:00Z",
                user_confirmed=True,
            )

            assert result["success"] is False
            assert "rate limit" in result["error"].lower()

    async def test_create_event_builds_correct_arguments(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event builds correct tool arguments."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        mock_result = ToolExecutionResult(success=True, result=[], required_confirmation=True)

        with patch.object(calendar_mcp._manager, "execute_tool", return_value=mock_result) as mock_execute:
            await calendar_mcp.create_event(
                summary="Team Meeting",
                start="2026-01-15T09:00:00Z",
                end="2026-01-15T10:00:00Z",
                description="Weekly standup",
                calendar_id="work@example.com",
                user_confirmed=True,
            )

            call_args = mock_execute.call_args.kwargs
            args = call_args["arguments"]

            assert args["summary"] == "Team Meeting"
            assert args["start"] == "2026-01-15T09:00:00Z"
            assert args["end"] == "2026-01-15T10:00:00Z"
            assert args["description"] == "Weekly standup"
            assert args["calendar_id"] == "work@example.com"

    async def test_create_event_omits_description_when_none(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event omits description from arguments when not provided."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        mock_result = ToolExecutionResult(success=True, result=[], required_confirmation=True)

        with patch.object(calendar_mcp._manager, "execute_tool", return_value=mock_result) as mock_execute:
            await calendar_mcp.create_event(
                summary="Quick Sync",
                start="2026-01-15T09:00:00Z",
                end="2026-01-15T09:30:00Z",
                user_confirmed=True,
            )

            args = mock_execute.call_args.kwargs["arguments"]
            assert "description" not in args

    async def test_create_event_pending_action_includes_all_fields(
        self, db_session: AsyncSession
    ) -> None:
        """Test pending_action in response includes all fields for frontend replay."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        mock_result = ToolExecutionResult(
            success=False,
            error="User confirmation required",
            required_confirmation=True,
        )

        with patch.object(calendar_mcp._manager, "execute_tool", return_value=mock_result):
            result = await calendar_mcp.create_event(
                summary="Important Meeting",
                start="2026-01-20T14:00:00Z",
                end="2026-01-20T15:00:00Z",
                description="Very important",
                calendar_id="work@example.com",
                user_confirmed=False,
            )

            pending = result["pending_action"]
            assert pending["tool"] == "calendar_create"
            assert pending["summary"] == "Important Meeting"
            assert pending["start"] == "2026-01-20T14:00:00Z"
            assert pending["end"] == "2026-01-20T15:00:00Z"
            assert pending["description"] == "Very important"
            assert pending["calendar_id"] == "work@example.com"

    async def test_create_event_parses_dict_result(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event parses dict result correctly."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        # Some MCP servers may return a dict directly
        mock_result = ToolExecutionResult(
            success=True,
            result={"id": "direct_dict_event", "summary": "Dict Result"},
            required_confirmation=True,
        )

        with patch.object(calendar_mcp._manager, "execute_tool", return_value=mock_result):
            result = await calendar_mcp.create_event(
                summary="Test",
                start="2026-01-13T10:00:00Z",
                end="2026-01-13T11:00:00Z",
                user_confirmed=True,
            )

            assert result["success"] is True
            assert result["event"]["id"] == "direct_dict_event"

    async def test_create_event_handles_malformed_json_response(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event handles malformed JSON in text response."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        # MCP server returns invalid JSON
        mock_result = ToolExecutionResult(
            success=True,
            result=[{"type": "text", "text": "Event created: abc123"}],
            required_confirmation=True,
        )

        with patch.object(calendar_mcp._manager, "execute_tool", return_value=mock_result):
            result = await calendar_mcp.create_event(
                summary="Test",
                start="2026-01-13T10:00:00Z",
                end="2026-01-13T11:00:00Z",
                user_confirmed=True,
            )

            assert result["success"] is True
            # Should preserve raw response when JSON parsing fails
            assert "raw_response" in result["event"]
            assert "Event created" in result["event"]["raw_response"]

    async def test_create_event_uses_default_calendar_id(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event uses 'primary' as default calendar_id."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        mock_result = ToolExecutionResult(success=True, result=[], required_confirmation=True)

        with patch.object(calendar_mcp._manager, "execute_tool", return_value=mock_result) as mock_execute:
            await calendar_mcp.create_event(
                summary="Test",
                start="2026-01-13T10:00:00Z",
                end="2026-01-13T11:00:00Z",
                user_confirmed=True,
            )

            args = mock_execute.call_args.kwargs["arguments"]
            assert args["calendar_id"] == "primary"

    async def test_create_event_uses_default_initiated_by(
        self, db_session: AsyncSession
    ) -> None:
        """Test create_event uses 'agent' as default initiated_by."""
        calendar_mcp = GoogleCalendarMCP(db_session)

        await calendar_mcp.register_calendar_server(
            token_json=json.dumps({"token": "test", "refresh_token": "test"})
        )

        from app.mcp.manager import ToolExecutionResult

        mock_result = ToolExecutionResult(success=True, result=[], required_confirmation=True)

        with patch.object(calendar_mcp._manager, "execute_tool", return_value=mock_result) as mock_execute:
            await calendar_mcp.create_event(
                summary="Test",
                start="2026-01-13T10:00:00Z",
                end="2026-01-13T11:00:00Z",
                user_confirmed=True,
            )

            assert mock_execute.call_args.kwargs["initiated_by"] == "agent"
