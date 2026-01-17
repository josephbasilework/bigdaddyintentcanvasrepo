"""Catalog of supported MCP integrations for runtime installation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.mcp.calendar import GOOGLE_CALENDAR_TOOLS, GoogleCalendarMCP


def _manifest_tools_from_catalog(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert catalog tool schema to manifest-friendly schema."""
    manifest_tools: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        tool_copy = dict(tool)
        if "inputSchema" in tool_copy and "input_schema" not in tool_copy:
            tool_copy["input_schema"] = tool_copy.pop("inputSchema")
        manifest_tools.append(tool_copy)
    return manifest_tools


GOOGLE_CALENDAR_MANIFEST: dict[str, Any] = {
    "protocolVersion": "2024-11-05",
    "name": "Google Calendar MCP",
    "version": "1.0.0",
    "description": "Google Calendar integration for event management",
    "capabilities": {
        "tools": _manifest_tools_from_catalog(GOOGLE_CALENDAR_TOOLS),
    },
    "metadata": {
        "oauth": {
            "provider": "google",
            "scopes": GoogleCalendarMCP.SCOPES,
        },
        "required_env": ["GOOGLE_CALENDAR_CREDENTIALS"],
    },
}


MCP_CATALOG: dict[str, dict[str, Any]] = {
    "google-calendar": {
        "catalog_id": "google-calendar",
        "server_id": "google-calendar",
        "name": "Google Calendar",
        "description": "Google Calendar integration for event management",
        "transport_type": "stdio",
        "transport_config": {
            "command": ["npx", "-y", "@modelcontextprotocol/server-google-calendar"],
            "env": {},
        },
        "manifest": GOOGLE_CALENDAR_MANIFEST,
        "credential_fields": [
            {
                "key": "google_calendar_credentials",
                "label": "Google Calendar OAuth Credentials",
                "type": "json",
                "description": (
                    "Paste OAuth client+token JSON (service account or OAuth token). "
                    "Stored as GOOGLE_CALENDAR_CREDENTIALS for the MCP runtime."
                ),
                "env_key": "GOOGLE_CALENDAR_CREDENTIALS",
                "required": True,
            }
        ],
        "oauth": {
            "provider": "google",
            "scopes": GoogleCalendarMCP.SCOPES,
            "documentation_url": "https://developers.google.com/calendar/api/auth",
        },
    }
}


def list_mcp_catalog() -> list[dict[str, Any]]:
    """Return a list of available MCP catalog entries."""
    return [deepcopy(entry) for entry in MCP_CATALOG.values()]


def get_mcp_catalog_entry(catalog_id: str) -> dict[str, Any] | None:
    """Get a single MCP catalog entry by catalog ID."""
    entry = MCP_CATALOG.get(catalog_id)
    return deepcopy(entry) if entry else None
