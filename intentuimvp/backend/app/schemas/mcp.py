"""Pydantic schemas for MCP API."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MCPServerRegisterRequest(BaseModel):
    """Request body for registering an MCP server."""

    server_id: str = Field(..., description="Unique server identifier")
    name: str = Field(..., description="Human-readable name")
    transport_type: str = Field(default="stdio", description="Transport type (stdio or sse)")
    transport_config: dict = Field(..., description="Connection configuration")
    description: str | None = Field(None, description="Optional description")
    version: str | None = Field(None, description="Server version from manifest")
    capabilities: dict | None = Field(None, description="Server capabilities from manifest")
    security_rules: dict | None = Field(None, description="Security rules per capability")
    enabled: bool = Field(default=True, description="Whether server is enabled")
    rate_limit: int = Field(default=60, description="Rate limit: max calls per minute")


class MCPServerResponse(BaseModel):
    """Response for MCP server data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    server_id: str
    name: str
    description: str | None
    transport_type: str
    transport_config: dict
    version: str | None
    capabilities: dict
    security_rules: dict
    enabled: bool
    rate_limit: int
    created_at: str
    updated_at: str


class MCPServerListResponse(BaseModel):
    """Response for listing MCP servers."""

    servers: list[MCPServerResponse]


class MCPToolExecuteRequest(BaseModel):
    """Request body for executing an MCP tool."""

    tool_name: str = Field(..., description="Name of the tool to execute")
    arguments: dict = Field(default_factory=dict, description="Tool arguments")
    server_id: str | None = Field(None, description="Optional server ID")
    user_confirmed: bool = Field(default=False, description="Whether user confirmed execution")


class MCPToolExecuteResponse(BaseModel):
    """Response from tool execution."""

    success: bool = Field(..., description="Whether execution succeeded")
    result: dict | list | None = Field(None, description="Result data from tool")
    error: str | None = Field(None, description="Error message if failed")
    requires_confirmation: bool = Field(default=False, description="Whether confirmation was required")
    preview: dict | None = Field(default=None, description="Preview payload for confirmation")
    diff: str | None = Field(default=None, description="Diff preview for confirmation")
    security_level: str | None = Field(None, description="Security level applied")


class MCPToolsListResponse(BaseModel):
    """Response for listing available tools."""

    tools: dict = Field(..., description="Server ID to tools mapping")


class MCPSecurityCheckRequest(BaseModel):
    """Request body for checking tool security."""

    tool_name: str = Field(..., description="Name of the tool to check")


class MCPSecurityCheckResponse(BaseModel):
    """Response for security check."""

    found: bool = Field(..., description="Whether tool was found")
    server_id: str | None = Field(None, description="Server providing the tool")
    security_level: str = Field(..., description="Security level (allowed/requires_confirm/blocked)")
    requires_confirmation: bool = Field(..., description="Whether user confirmation is required")
    allowed: bool = Field(..., description="Whether execution is allowed")
    reason: str | None = Field(None, description="Reason for security decision")


class MCPServerUpdateRequest(BaseModel):
    """Request body for updating an MCP server."""

    name: str | None = Field(None, description="New name")
    description: str | None = Field(None, description="New description")
    transport_config: dict | None = Field(None, description="New transport config")
    enabled: bool | None = Field(None, description="New enabled status")
    rate_limit: int | None = Field(None, description="New rate limit")


class GoogleCalendarEventRequest(BaseModel):
    """Request body for creating a calendar event."""

    summary: str = Field(..., description="Event title")
    start: str = Field(..., description="Start time in ISO format")
    end: str = Field(..., description="End time in ISO format")
    description: str | None = Field(None, description="Optional event description")
    calendar_id: str = Field(default="primary", description="Calendar ID")


class GoogleCalendarEventResponse(BaseModel):
    """Response for calendar event creation."""

    success: bool
    event: dict | None = None
    error: str | None = None


class CalendarSyncTask(BaseModel):
    """Task payload for calendar sync."""

    id: str = Field(..., description="Task identifier")
    title: str | None = Field(default=None, description="Task title")
    calendar_suggestion: dict[str, Any] | None = Field(
        default=None, description="Calendar suggestion payload"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_calendar_suggestion(cls, values: dict) -> dict:
        if not isinstance(values, dict):
            return values
        if "calendar_suggestion" in values:
            return values
        if "calendarSuggestion" in values:
            return {**values, "calendar_suggestion": values.get("calendarSuggestion")}
        return values


class CalendarSyncDAG(BaseModel):
    """Task DAG payload for calendar sync."""

    tasks: list[CalendarSyncTask] = Field(default_factory=list, description="Tasks to sync")
    dependencies: list[dict[str, Any]] | None = Field(
        default=None, description="Optional dependency metadata"
    )


class CalendarSyncRequest(BaseModel):
    """Request body for syncing Task DAG to calendar."""

    task_dag: CalendarSyncDAG = Field(..., description="Task DAG payload")
    calendar_id: str = Field(default="primary", description="Calendar ID")
    user_confirmed: bool = Field(default=False, description="Whether user confirmed sync")


class CalendarSyncCreatedEvent(BaseModel):
    """Created calendar event mapping for a task."""

    task_id: str | None = None
    event_id: str | None = None
    event_url: str | None = None
    event: dict | None = None


class CalendarSyncFailedEvent(BaseModel):
    """Failed calendar event mapping for a task."""

    task_id: str | None = None
    error: str | None = None


class CalendarSyncResponse(BaseModel):
    """Response body for calendar sync operations."""

    success: bool
    requires_confirmation: bool = Field(default=False)
    message: str | None = None
    error: str | None = None
    created_events: list[CalendarSyncCreatedEvent] = Field(default_factory=list)
    failed_events: list[CalendarSyncFailedEvent] = Field(default_factory=list)
    pending_actions: list[dict[str, Any]] | None = None


class MCPCredentialField(BaseModel):
    """Credential field required for MCP installation."""

    key: str
    label: str
    type: Literal["text", "json", "secret"] = "text"
    description: str | None = None
    env_key: str
    required: bool = True


class MCPOAuthSpec(BaseModel):
    """OAuth configuration details for an MCP."""

    provider: str
    scopes: list[str] = Field(default_factory=list)
    authorization_url: str | None = None
    token_url: str | None = None
    documentation_url: str | None = None


class MCPCatalogEntry(BaseModel):
    """Catalog entry describing an installable MCP."""

    catalog_id: str
    server_id: str
    name: str
    description: str | None = None
    transport_type: str
    transport_config: dict = Field(default_factory=dict)
    manifest: dict = Field(default_factory=dict)
    credential_fields: list[MCPCredentialField] = Field(default_factory=list)
    oauth: MCPOAuthSpec | None = None


class MCPCatalogResponse(BaseModel):
    """Response body for MCP catalog listing."""

    entries: list[MCPCatalogEntry]


class MCPInstallRequest(BaseModel):
    """Request body for installing or configuring an MCP."""

    catalog_id: str | None = None
    server_id: str | None = None
    name: str | None = None
    description: str | None = None
    transport_type: str | None = None
    transport_config: dict | None = None
    manifest: dict | None = None
    credentials: dict[str, str] | None = None
    oauth: MCPOAuthSpec | None = None
    approved_tools: list[str] | None = None
    confirmed: bool = False
    rate_limit: int | None = None


class MCPInstallPreview(BaseModel):
    """Preview payload for MCP installation."""

    server_id: str
    name: str
    description: str | None = None
    transport_type: str
    transport_config: dict
    manifest: dict
    tools: list[dict[str, Any]] = Field(default_factory=list)
    security_rules: dict[str, str] = Field(default_factory=dict)
    oauth: MCPOAuthSpec | None = None
    credential_fields: list[MCPCredentialField] = Field(default_factory=list)
    missing_credentials: list[str] = Field(default_factory=list)
    sandbox_issues: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)


class MCPInstallResponse(BaseModel):
    """Response body for MCP installation."""

    success: bool
    requires_confirmation: bool = False
    review_required: bool = False
    server: MCPServerResponse | None = None
    preview: MCPInstallPreview | None = None
    diff: str | None = None
    error: str | None = None
