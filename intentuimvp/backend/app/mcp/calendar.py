"""Google Calendar MCP Integration.

Provides Google Calendar integration via MCP protocol.
Supports event reading, creation, and OAuth flow completion.
"""

import json
from datetime import datetime, timedelta
from typing import Any

import google.auth.transport.requests  # type: ignore[import-untyped]
import google.oauth2.credentials  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.manager import MCPManager
from app.mcp.registry import DEFAULT_SECURITY_RULES, MCPServerRegistry


def _normalize_text(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return str(value)
    return None


def _pick_text(suggestion: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in suggestion:
            value = _normalize_text(suggestion.get(key))
            if value:
                return value
    return None


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
                        "name": "calendar_list",
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
                        "name": "calendar_read",
                        "description": "Read a specific event from Google Calendar",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "calendar_id": {"type": "string"},
                                "event_id": {"type": "string"},
                            },
                            "required": ["event_id"],
                        },
                    },
                    {
                        "name": "calendar_create",
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
                    {
                        "name": "calendar_update",
                        "description": "Update an existing calendar event",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "calendar_id": {"type": "string"},
                                "event_id": {"type": "string"},
                                "summary": {"type": "string"},
                                "description": {"type": "string"},
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                            },
                            "required": ["event_id"],
                        },
                    },
                    {
                        "name": "calendar_query",
                        "description": "Query/search events from Google Calendar by text search",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "calendar_id": {
                                    "type": "string",
                                    "description": "Calendar ID (default: primary)",
                                },
                                "query": {
                                    "type": "string",
                                    "description": "Search query text to match against event titles and descriptions",
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
                            "required": ["query"],
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

    async def query_events(
        self,
        query: str,
        calendar_id: str = "primary",
        time_min: str | None = None,
        time_max: str | None = None,
    ) -> dict[str, Any]:
        """Query/search events from Google Calendar by text search.

        Args:
            query: Search query text to match against event titles and descriptions
            calendar_id: Calendar ID (default: 'primary')
            time_min: Start time in ISO format (optional)
            time_max: End time in ISO format (optional)

        Returns:
            Dict with matching events list or error
        """
        # Use MCP client to call the tool
        client = await self._manager.get_registry()
        server = await client.get_server("google-calendar")

        if not server or not server.enabled:
            return {"success": False, "error": "Google Calendar server not enabled"}

        # Set default time range if not provided
        if not time_min:
            time_min = datetime.utcnow().isoformat() + "Z"
        if not time_max:
            time_max = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"

        # This would call the actual MCP calendar_query tool
        # For now, return a placeholder
        return {
            "success": True,
            "events": [],
            "query": query,
            "message": "Google Calendar integration ready - awaiting MCP server connection",
        }

    async def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        description: str | None = None,
        calendar_id: str = "primary",
        user_confirmed: bool = False,
        initiated_by: str = "agent",
    ) -> dict[str, Any]:
        """Create a new calendar event via MCP.

        This is a write operation that requires user confirmation (REQUIRES_CONFIRM).
        Per FR-020: Given user requests calendar update, When processed, Then calendar
        is modified via MCP (REQUIRES_CONFIRM).

        Args:
            summary: Event title
            start: Start time in ISO format
            end: End time in ISO format
            description: Optional event description
            calendar_id: Calendar ID (default: 'primary')
            user_confirmed: Whether user has confirmed this write operation
            initiated_by: Agent or user ID that initiated this call

        Returns:
            Dict with created event or error. If confirmation is required,
            returns requires_confirmation=True with the pending action details.
        """
        # Validate server is registered and enabled
        server = await self._registry.get_server("google-calendar")
        if not server:
            return {
                "success": False,
                "error": "Google Calendar server not registered",
            }
        if not server.enabled:
            return {
                "success": False,
                "error": "Google Calendar server is disabled",
            }

        # Build arguments for the calendar_create tool
        arguments: dict[str, Any] = {
            "calendar_id": calendar_id,
            "summary": summary,
            "start": start,
            "end": end,
        }
        if description:
            arguments["description"] = description

        # Execute the tool through the MCP manager
        result = await self._manager.execute_tool(
            server_id="google-calendar",
            tool_name="calendar_create",
            arguments=arguments,
            initiated_by=initiated_by,
            user_confirmed=user_confirmed,
        )

        # Handle confirmation requirement (FR-020 HITL gate)
        if result.required_confirmation and not result.success:
            return {
                "success": False,
                "requires_confirmation": True,
                "pending_action": {
                    "tool": "calendar_create",
                    "summary": summary,
                    "start": start,
                    "end": end,
                    "description": description,
                    "calendar_id": calendar_id,
                },
                "message": "User confirmation required to create calendar event",
            }

        # Handle degraded mode (FR-019 graceful degradation)
        if result.degraded:
            return {
                "success": False,
                "degraded": True,
                "error": result.error,
                "degraded_reason": result.degraded_reason,
            }

        # Handle execution failure
        if not result.success:
            return {
                "success": False,
                "error": result.error,
            }

        # Parse the successful result
        event_data: dict[str, Any] = {}
        if result.result:
            # MCP tool results come as a list of content items
            if isinstance(result.result, list):
                for item in result.result:
                    if isinstance(item, dict):
                        # Extract text content which may contain the event data
                        if item.get("type") == "text" and item.get("text"):
                            try:
                                event_data = json.loads(item["text"])
                            except (json.JSONDecodeError, TypeError):
                                event_data = {"raw_response": item["text"]}
                        elif "text" in item:
                            event_data = {"raw_response": item["text"]}
            elif isinstance(result.result, dict):
                event_data = result.result

        return {
            "success": True,
            "event": event_data,
            "message": "Calendar event created successfully",
        }

    async def sync_with_task_dag(
        self,
        task_dag: dict[str, Any],
        calendar_id: str = "primary",
        user_confirmed: bool = False,
        initiated_by: str = "agent",
    ) -> dict[str, Any]:
        """Synchronize calendar events with Task DAG.

        Creates calendar events from task deadlines and syncs
        task completion back to calendar.

        Args:
            task_dag: Task DAG payload containing tasks
            calendar_id: Calendar ID to sync with
            user_confirmed: Whether user has confirmed calendar writes
            initiated_by: Agent or user ID that initiated this call

        Returns:
            Dict with sync status
        """
        tasks_payload = []
        raw_tasks: list[Any] | None = None
        if isinstance(task_dag, list):
            raw_tasks = task_dag
        elif isinstance(task_dag, dict):
            tasks_value = task_dag.get("tasks")
            if isinstance(tasks_value, list):
                raw_tasks = tasks_value

        if not raw_tasks:
            return {
                "success": False,
                "error": "No tasks provided for calendar sync.",
                "message": "Calendar sync requires at least one task.",
                "created_events": [],
                "failed_events": [],
            }

        failed_events: list[dict[str, Any]] = []
        for task in raw_tasks:
            if not isinstance(task, dict):
                failed_events.append({"task_id": None, "error": "Invalid task payload."})
                continue

            task_id = _normalize_text(task.get("id")) or None
            task_title = _normalize_text(task.get("title"))
            suggestion = task.get("calendar_suggestion") or task.get("calendarSuggestion")
            if not isinstance(suggestion, dict):
                failed_events.append(
                    {"task_id": task_id, "error": "Missing calendar suggestion."}
                )
                continue

            summary = (
                _pick_text(suggestion, ("summary", "title")) or task_title
            )
            start = _pick_text(suggestion, ("start", "start_time", "startTime"))
            end = _pick_text(suggestion, ("end", "end_time", "endTime"))
            description = _pick_text(suggestion, ("description", "details", "notes"))
            calendar_id_value = (
                _pick_text(suggestion, ("calendar_id", "calendarId")) or calendar_id
            )

            missing_fields = [
                name
                for name, value in (("summary", summary), ("start", start), ("end", end))
                if not value
            ]
            if missing_fields:
                failed_events.append(
                    {
                        "task_id": task_id,
                        "error": f"Missing calendar fields: {', '.join(missing_fields)}.",
                    }
                )
                continue

            # Type narrowing: required fields are guaranteed non-None after validation above
            assert summary is not None  # noqa: S101
            assert start is not None  # noqa: S101
            assert end is not None  # noqa: S101
            assert calendar_id_value is not None  # noqa: S101

            tasks_payload.append(
                {
                    "task_id": task_id,
                    "summary": summary,
                    "start": start,
                    "end": end,
                    "description": description,
                    "calendar_id": calendar_id_value,
                }
            )

        if not tasks_payload:
            return {
                "success": False,
                "error": "No valid calendar suggestions to sync.",
                "message": "Calendar sync skipped all tasks.",
                "created_events": [],
                "failed_events": failed_events,
            }

        if not user_confirmed:
            return {
                "success": False,
                "requires_confirmation": True,
                "message": f"User confirmation required to sync {len(tasks_payload)} calendar task(s).",
                "created_events": [],
                "failed_events": failed_events,
                "pending_actions": tasks_payload,
            }

        created_events: list[dict[str, Any]] = []
        for payload in tasks_payload:
            # Type narrowing: required fields are guaranteed non-None after validation above
            summary_val: str = payload["summary"]  # type: ignore[assignment]
            start_val: str = payload["start"]  # type: ignore[assignment]
            end_val: str = payload["end"]  # type: ignore[assignment]
            calendar_id_val: str = payload["calendar_id"]  # type: ignore[assignment]

            result = await self.create_event(
                summary=summary_val,
                start=start_val,
                end=end_val,
                description=payload.get("description"),
                calendar_id=calendar_id_val,
                user_confirmed=user_confirmed,
                initiated_by=initiated_by,
            )

            if result.get("requires_confirmation"):
                return {
                    "success": False,
                    "requires_confirmation": True,
                    "message": result.get("message")
                    or "User confirmation required to create calendar events.",
                    "created_events": created_events,
                    "failed_events": failed_events,
                    "pending_actions": [result.get("pending_action", payload)],
                }

            if not result.get("success"):
                failed_events.append(
                    {
                        "task_id": payload.get("task_id"),
                        "error": result.get("error") or result.get("message") or "Calendar event creation failed.",
                    }
                )
                continue

            event_payload = result.get("event")
            event_data = event_payload if isinstance(event_payload, dict) else None
            event_id = _normalize_text(event_data.get("id") if event_data else None)
            event_url = _normalize_text(
                event_data.get("htmlLink") if event_data else None
            )
            created_events.append(
                {
                    "task_id": payload.get("task_id"),
                    "event_id": event_id,
                    "event_url": event_url,
                    "event": event_data,
                }
            )

        success = len(failed_events) == 0
        message = (
            f"Calendar sync completed for {len(created_events)} task(s)."
            if success
            else f"Calendar sync completed with {len(failed_events)} failure(s)."
        )
        return {
            "success": success,
            "message": message,
            "created_events": created_events,
            "failed_events": failed_events,
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

    async def query_events(
        self,
        query: str,
        calendar_id: str = "primary",
        days_ahead: int = 30,
    ) -> dict[str, Any]:
        """Query/search events from Google Calendar by text search.

        Args:
            query: Search query text to match against event titles and descriptions
            calendar_id: Calendar ID (default: 'primary')
            days_ahead: Number of days ahead to search (default: 30)

        Returns:
            Dict with matching events list or error
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
                    q=query,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])

            return {
                "success": True,
                "query": query,
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
