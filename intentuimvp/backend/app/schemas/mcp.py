"""Pydantic schemas for MCP API."""

from pydantic import BaseModel, ConfigDict, Field


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
