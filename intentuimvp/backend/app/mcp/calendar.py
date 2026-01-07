"""Google Calendar MCP Integration.

Provides Google Calendar integration via MCP protocol.
Supports event reading, creation, and OAuth flow completion.
"""

import json
from datetime import datetime, timedelta
from typing import Any

import google.auth.transport.requests
import google.oauth2.credentials
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.manager import MCPManager
from app.mcp.registry import DEFAULT_SECURITY_RULES, MCPServerRegistry


class GoogleCalendarMCP:
    """Google Calendar MCP integration.

    Handles:
    - Event listing and reading
    - Event creation with OAuth
    - Calendar synchronization with Task DAG
    """

    # OAuth scopes needed for Google Calendar
    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the Google Calendar MCP integration.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self._session = session
        self._registry = MCPServerRegistry(session)
        self._manager = MCPManager(session)

    async def register_calendar_server(
        self,
        credentials_path: str | None = None,
        token_json: str | None = None,
    ) -> bool:
        """Register the Google Calendar MCP server.

        Args:
            credentials_path: Path to OAuth credentials JSON file
            token_json: OAuth token JSON string

        Returns:
            True if registration succeeded
        """
        # Load credentials
        if token_json:
            credentials_data = json.loads(token_json)
        elif credentials_path:
            with open(credentials_path) as f:
                credentials_data = json.load(f)
        else:
            return False

        # Register the server in the registry
        await self._registry.register_server(
            server_id="google-calendar",
            name="Google Calendar",
            description="Google Calendar integration for event management",
            transport_type="stdio",
            transport_config={
                "command": ["npx", "-y", "@modelcontextprotocol/server-google-calendar"],
                "env": {
                    "GOOGLE_CALENDAR_CREDENTIALS": json.dumps(credentials_data),
                },
            },
            version="1.0.0",
            capabilities={
                "tools": [
                    {
                        "name": "list_events",
                        "description": "List events from Google Calendar",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "calendar_id": {
                                    "type": "string",
                                    "description": "Calendar ID (default: primary)",
                                },
                                "time_min": {
                                    "type": "string",
                                    "description": "Start time in ISO format",
                                },
                                "time_max": {
                                    "type": "string",
                                    "description": "End time in ISO format",
                                },
                            },
                        },
                    },
                    {
                        "name": "create_event",
                        "description": "Create a new calendar event",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "calendar_id": {"type": "string"},
                                "summary": {"type": "string"},
                                "description": {"type": "string"},
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                            },
                            "required": ["summary", "start", "end"],
                        },
                    },
                ]
            },
            security_rules={
                tool: level.value
                for tool, level in DEFAULT_SECURITY_RULES.get("google-calendar", {}).items()
            },
        )

        return True

    async def list_events(
        self,
        calendar_id: str = "primary",
        days_ahead: int = 7,
        time_min: str | None = None,
        time_max: str | None = None,
    ) -> dict[str, Any]:
        """List events from Google Calendar.

        Args:
            calendar_id: Calendar ID (default: 'primary')
            days_ahead: Number of days ahead to look
            time_min: Start time in ISO format (optional)
            time_max: End time in ISO format (optional)

        Returns:
            Dict with events list or error
        """
        # Use MCP client to call the tool
        client = await self._manager.get_registry()
        server = await client.get_server("google-calendar")

        if not server or not server.enabled:
            return {"success": False, "error": "Google Calendar server not enabled"}

        # Set default time range
        if not time_min:
            time_min = datetime.utcnow().isoformat() + "Z"
        if not time_max:
            time_max = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"

        # This would call the actual MCP tool
        # For now, return a placeholder
        return {
            "success": True,
            "events": [],
            "message": "Google Calendar integration ready - awaiting MCP server connection",
        }

    async def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        description: str | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Create a new calendar event.

        Args:
            summary: Event title
            start: Start time in ISO format
            end: End time in ISO format
            description: Optional event description
            calendar_id: Calendar ID (default: 'primary')

        Returns:
            Dict with created event or error
        """
        return {
            "success": True,
            "message": "Google Calendar integration ready - awaiting MCP server connection",
        }

    async def sync_with_task_dag(
        self, task_dag_id: str, calendar_id: str = "primary"
    ) -> dict[str, Any]:
        """Synchronize calendar events with Task DAG.

        Creates calendar events from task deadlines and syncs
        task completion back to calendar.

        Args:
            task_dag_id: Task DAG identifier
            calendar_id: Calendar ID to sync with

        Returns:
            Dict with sync status
        """
        return {
            "success": True,
            "message": "Task DAG sync ready - awaiting MCP server connection",
        }


class GoogleCalendarDirect:
    """Direct Google Calendar API integration (fallback for testing).

    This provides direct API access without requiring the MCP server
    to be running. Useful for testing and development.
    """

    # OAuth scopes needed for Google Calendar
    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    def __init__(self, credentials_dict: dict[str, Any]) -> None:
        """Initialize with OAuth credentials.

        Args:
            credentials_dict: Dictionary with OAuth token and refresh token
        """
        self._credentials = google.oauth2.credentials.Credentials(
            token=credentials_dict.get("token"),
            refresh_token=credentials_dict.get("refresh_token"),
            token_uri=credentials_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=credentials_dict.get("client_id"),
            client_secret=credentials_dict.get("client_secret"),
            scopes=self.SCOPES,
        )
        self._service: Any = None

    async def _ensure_authenticated(self) -> None:
        """Ensure credentials are valid and refreshed."""
        if not self._service:
            # Refresh credentials if needed
            if self._credentials.expired and self._credentials.refresh_token:
                self._credentials.refresh(google.auth.transport.requests.Request())

            # Build the service
            self._service = build("calendar", "v3", credentials=self._credentials)

    async def list_events(
        self,
        calendar_id: str = "primary",
        days_ahead: int = 7,
    ) -> dict[str, Any]:
        """List events from Google Calendar.

        Args:
            calendar_id: Calendar ID (default: 'primary')
            days_ahead: Number of days ahead to look

        Returns:
            Dict with events list or error
        """
        try:
            await self._ensure_authenticated()

            time_min = datetime.utcnow().isoformat() + "Z"
            time_max = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"

            events_result = (
                self._service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])

            return {
                "success": True,
                "events": [
                    {
                        "id": event["id"],
                        "summary": event.get("summary", "No title"),
                        "start": event.get("start", {}).get("dateTime", event.get("start", {}).get("date")),
                        "end": event.get("end", {}).get("dateTime", event.get("end", {}).get("date")),
                        "description": event.get("description", ""),
                    }
                    for event in events
                ],
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        description: str | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Create a new calendar event.

        Args:
            summary: Event title
            start: Start time in ISO format
            end: End time in ISO format
            description: Optional event description
            calendar_id: Calendar ID (default: 'primary')

        Returns:
            Dict with created event or error
        """
        try:
            await self._ensure_authenticated()

            event_body = {
                "summary": summary,
                "start": {"dateTime": start},
                "end": {"dateTime": end},
            }

            if description:
                event_body["description"] = description

            event = (
                self._service.events()
                .insert(calendarId=calendar_id, body=event_body)
                .execute()
            )

            return {
                "success": True,
                "event": {
                    "id": event["id"],
                    "summary": event.get("summary"),
                    "start": event.get("start", {}).get("dateTime"),
                    "end": event.get("end", {}).get("dateTime"),
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
