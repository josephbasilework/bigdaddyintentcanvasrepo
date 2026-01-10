"""MCP API endpoints for server configuration and tool execution."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.mcp.calendar import GoogleCalendarMCP
from app.mcp.client import MCPClient
from app.mcp.manager import ToolExecutionResult
from app.mcp.registry import MCPServerRegistry
from app.schemas.mcp import (
    GoogleCalendarEventRequest,
    GoogleCalendarEventResponse,
    MCPSecurityCheckRequest,
    MCPSecurityCheckResponse,
    MCPServerListResponse,
    MCPServerRegisterRequest,
    MCPServerResponse,
    MCPServerUpdateRequest,
    MCPToolExecuteRequest,
    MCPToolExecuteResponse,
    MCPToolsListResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user() -> str:
    """Get current user from authentication.

    Basic implementation using a simple header.
    TODO: Replace with proper JWT/OAuth authentication.

    Returns:
        User ID string
    """
    return "default_user"  # MVP: single user for now


@router.get("/api/mcp/servers", response_model=MCPServerListResponse)
async def list_mcp_servers(
    enabled_only: bool = True,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """List all registered MCP servers.

    Args:
        enabled_only: If True, only return enabled servers
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of MCP servers
    """
    registry = MCPServerRegistry(db)
    servers = await registry.list_servers(enabled_only=enabled_only)
    return {"servers": [s.to_dict() for s in servers]}


@router.post("/api/mcp/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def register_mcp_server(
    payload: MCPServerRegisterRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Register a new MCP server.

    Args:
        payload: Server registration data
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Registered server data
    """
    registry = MCPServerRegistry(db)
    server = await registry.register_server(
        server_id=payload.server_id,
        name=payload.name,
        transport_type=payload.transport_type,
        transport_config=payload.transport_config,
        description=payload.description,
        version=payload.version,
        capabilities=payload.capabilities,
        security_rules=payload.security_rules,
        enabled=payload.enabled,
        rate_limit=payload.rate_limit,
    )
    await db.commit()
    return server.to_dict()


@router.get("/api/mcp/servers/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get a specific MCP server by ID.

    Args:
        server_id: Server identifier
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Server data

    Raises:
        HTTPException: If server not found
    """
    registry = MCPServerRegistry(db)
    server = await registry.get_server(server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server_id}' not found",
        )
    return server.to_dict()


@router.put("/api/mcp/servers/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: str,
    payload: MCPServerUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Update an MCP server.

    Args:
        server_id: Server identifier
        payload: Update data
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Updated server data

    Raises:
        HTTPException: If server not found
    """
    registry = MCPServerRegistry(db)
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    server = await registry.update_server(server_id, **updates)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server_id}' not found",
        )
    await db.commit()
    return server.to_dict()


@router.delete("/api/mcp/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> None:
    """Unregister (delete) an MCP server.

    Args:
        server_id: Server identifier
        db: Database session
        user_id: Authenticated user ID

    Raises:
        HTTPException: If server not found
    """
    registry = MCPServerRegistry(db)
    deleted = await registry.unregister_server(server_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server_id}' not found",
        )
    await db.commit()


@router.get("/api/mcp/tools", response_model=MCPToolsListResponse)
async def list_mcp_tools(
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """List all available tools from all MCP servers.

    Returns tools in a format suitable for agent consumption.

    Args:
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Dictionary of server_id to tools
    """
    client = MCPClient(db)
    tools = await client.list_available_tools()
    return {"tools": tools}


@router.post("/api/mcp/tools/execute", response_model=MCPToolExecuteResponse)
async def execute_mcp_tool(
    payload: MCPToolExecuteRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Execute an MCP tool.

    Performs security validation and executes the tool.
    Returns result or prompts for confirmation if required.

    Args:
        payload: Tool execution request
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Tool execution result
    """
    client = MCPClient(db)
    await client.initialize()

    try:
        if payload.user_confirmed:
            result: ToolExecutionResult = await client.call_tool_with_confirmation(
                tool_name=payload.tool_name,
                arguments=payload.arguments,
                initiated_by=user_id,
                server_id=payload.server_id,
            )
        else:
            result = await client.call_tool(
                tool_name=payload.tool_name,
                arguments=payload.arguments,
                initiated_by=user_id,
                server_id=payload.server_id,
            )

        return {
            "success": result.success,
            "result": result.result,
            "error": result.error,
            "requires_confirmation": result.required_confirmation,
            "security_level": None,
        }
    finally:
        await client.shutdown()


@router.post("/api/mcp/tools/check-security", response_model=MCPSecurityCheckResponse)
async def check_tool_security(
    payload: MCPSecurityCheckRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Check the security level of a tool.

    Returns information about whether a tool requires confirmation
    or is blocked. Useful for presenting confirmation dialogs.

    Args:
        payload: Security check request
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Security information
    """
    client = MCPClient(db)
    security_info = await client.check_security(payload.tool_name)
    return security_info


@router.post("/api/mcp/calendar/events", response_model=GoogleCalendarEventResponse)
async def create_calendar_event(
    payload: GoogleCalendarEventRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Create a Google Calendar event.

    Args:
        payload: Event creation request
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Created event or error

    Raises:
        HTTPException: If Google Calendar is not configured
    """
    calendar = GoogleCalendarMCP(db)
    result = await calendar.create_event(
        summary=payload.summary,
        start=payload.start,
        end=payload.end,
        description=payload.description,
        calendar_id=payload.calendar_id,
    )
    return result


@router.get("/api/mcp/health")
async def mcp_health_check(
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Check MCP system health.

    Returns status of MCP servers and connections.

    Args:
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Health status information
    """
    registry = MCPServerRegistry(db)
    servers = await registry.list_servers(enabled_only=True)

    return {
        "status": "healthy",
        "enabled_servers": len(servers),
        "servers": [
            {
                "server_id": s.server_id,
                "name": s.name,
                "enabled": s.enabled,
            }
            for s in servers
        ],
    }
