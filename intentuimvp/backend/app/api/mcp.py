"""MCP API endpoints for server configuration and tool execution."""

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.mcp.calendar import GoogleCalendarMCP
from app.mcp.capability_registry import CapabilityRegistry, CapabilityType
from app.mcp.catalog import list_mcp_catalog
from app.mcp.client import MCPClient
from app.mcp.installer import MCPInstaller
from app.mcp.manager import ToolExecutionResult
from app.mcp.manifest import SecurityCategory, SecurityLevel
from app.mcp.registry import MCPServerRegistry
from app.models.dashboard_subscription import DashboardSubscriptionTarget
from app.repositories.node_repo import NodeRepository
from app.schemas.mcp import (
    CalendarSyncRequest,
    CalendarSyncResponse,
    CanPerformActionRequest,
    CanPerformActionResponse,
    CapabilityListResponse,
    CapabilityResponse,
    CapabilityStatsResponse,
    GoogleCalendarEventRequest,
    GoogleCalendarEventResponse,
    IntegrationStatusListResponse,
    MCPCatalogResponse,
    MCPInstallRequest,
    MCPInstallResponse,
    MCPSecurityCheckRequest,
    MCPSecurityCheckResponse,
    MCPServerListResponse,
    MCPServerRegisterRequest,
    MCPServerResponse,
    MCPServerUpdateRequest,
    MCPToolExecuteRequest,
    MCPToolExecuteResponse,
    MCPToolsListResponse,
    TaskDagExternalUpdateRequest,
    TaskDagExternalUpdateResponse,
    UnavailableCapabilitiesResponse,
    UsageStatsResponse,
)
from app.services.dashboard_updates import publish_dashboard_update
from app.services.mcp_sync import ExternalTaskUpdate, TaskDagSyncService

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


@router.get("/api/mcp/catalog", response_model=MCPCatalogResponse)
async def list_mcp_catalog_entries(
    user_id: str = Depends(get_current_user),
) -> dict:
    """List available MCP catalog entries for runtime installation."""
    return {"entries": list_mcp_catalog()}


@router.post("/api/mcp/install", response_model=MCPInstallResponse)
async def install_mcp(
    payload: MCPInstallRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Install or configure an MCP server from the catalog or custom manifest."""
    installer = MCPInstaller(db)
    result = await installer.install(payload)
    if result.get("server"):
        await db.commit()
    return result


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


@router.delete(
    "/api/mcp/servers/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
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
            "preview": result.preview,
            "diff": result.diff,
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


@router.post("/api/mcp/calendar/sync", response_model=CalendarSyncResponse)
async def sync_calendar_task_dag(
    payload: CalendarSyncRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Sync Task DAG tasks to Google Calendar events.

    Args:
        payload: Task DAG sync request
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Sync results including created and failed events
    """
    calendar = GoogleCalendarMCP(db)
    result = await calendar.sync_with_task_dag(
        task_dag=payload.task_dag.model_dump(),
        calendar_id=payload.calendar_id,
        user_confirmed=payload.user_confirmed,
        initiated_by=user_id,
    )
    return result


@router.post(
    "/api/mcp/task-dag/external",
    response_model=TaskDagExternalUpdateResponse,
)
async def reconcile_task_dag_external_update(
    payload: TaskDagExternalUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Reconcile Task DAG updates coming from external MCP sources."""
    repo = NodeRepository(db)
    node = await repo.get_by_id(payload.node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task DAG node not found",
        )

    def _parse_updated_at(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    updates = [
        ExternalTaskUpdate(
            task_id=update.task_id,
            status=update.status,
            updated_at=_parse_updated_at(update.updated_at),
            source=update.source or payload.source,
            title=update.title,
        )
        for update in payload.updates
    ]

    sync_service = TaskDagSyncService(db)
    outcome = await sync_service.apply_external_updates(
        node=node,
        metadata=node.get_metadata(),
        updates=updates,
        policy=payload.conflict_resolution,
        source=payload.source,
    )

    updated = None
    if outcome.updated_metadata is not None:
        updated = await repo.update(
            node.id,
            node_metadata=json.dumps(outcome.updated_metadata),
        )
        if updated:
            updated_payload = {
                "id": updated.id,
                "canvas_id": updated.canvas_id,
                "type": updated.type,
                "label": updated.label,
                "content": updated.content,
                "position": updated.get_position(),
                "metadata": updated.get_metadata(),
                "created_at": updated.created_at.isoformat(),
                "created_by_turn_id": updated.created_by_turn_id,
            }
            await publish_dashboard_update(
                canvas_id=updated.canvas_id,
                target=DashboardSubscriptionTarget.NODE,
                source_id=str(updated.id),
                change_type="updated",
                data=updated_payload,
            )
            await sync_service.log_sync_turn(
                node=updated,
                user_id=user_id,
                outcome=outcome,
                summary_prefix="External Task DAG update",
            )

    return {
        "success": True,
        "updated": updated is not None,
        "conflicts": outcome.conflicts,
        "next_task": outcome.next_task,
        "error": None,
    }


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


# -----------------------------------------------------------------------------
# Capability Registry & Introspection Endpoints
# -----------------------------------------------------------------------------


@router.get("/api/mcp/capabilities", response_model=CapabilityListResponse)
async def list_capabilities(
    query: str | None = Query(None, description="Search text in name/description"),
    type: str | None = Query(None, description="Filter by type (tool/resource/prompt)"),
    security_level: str | None = Query(None, description="Filter by security level"),
    category: str | None = Query(None, description="Filter by category"),
    server_id: str | None = Query(None, description="Filter by server"),
    include_disabled: bool = Query(False, description="Include disabled servers"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """List all capabilities with optional filters.

    Provides introspection for agents to discover what capabilities exist.

    Args:
        query: Optional text search in name/description
        type: Optional filter by capability type
        security_level: Optional filter by security level
        category: Optional filter by category
        server_id: Optional filter by server
        include_disabled: Include capabilities from disabled servers
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of matching capabilities
    """
    cap_registry = CapabilityRegistry(db)

    # Convert string filters to enums if provided
    cap_type = CapabilityType(type) if type else None
    sec_level = SecurityLevel(security_level) if security_level else None
    sec_category = SecurityCategory(category) if category else None

    capabilities = await cap_registry.search_capabilities(
        query=query,
        capability_type=cap_type,
        security_level=sec_level,
        category=sec_category,
        server_id=server_id,
        include_disabled=include_disabled,
    )

    return {
        "capabilities": [c.to_dict() for c in capabilities],
        "total": len(capabilities),
    }


@router.get("/api/mcp/capabilities/stats", response_model=CapabilityStatsResponse)
async def get_capability_stats(
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get aggregated statistics about all capabilities.

    Provides adoption metrics and capability distribution.

    Args:
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Capability statistics
    """
    cap_registry = CapabilityRegistry(db)
    stats = await cap_registry.get_stats()
    return stats.to_dict()


@router.get("/api/mcp/capabilities/unavailable", response_model=UnavailableCapabilitiesResponse)
async def list_unavailable_capabilities(
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """List capabilities that exist but cannot be used, with reasons.

    Enables agents and users to understand why certain capabilities are unavailable.

    Args:
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of unavailable capabilities with explanations
    """
    cap_registry = CapabilityRegistry(db)
    unavailable = await cap_registry.get_unavailable_capabilities()
    return {
        "unavailable": [u.to_dict() for u in unavailable],
    }


@router.post("/api/mcp/capabilities/can-perform", response_model=CanPerformActionResponse)
async def can_perform_action(
    payload: CanPerformActionRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Check if an action can be performed and which capabilities could do it.

    High-level introspection for agents to understand what's possible.

    Args:
        payload: Action description request
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Possibility check with matching capabilities
    """
    cap_registry = CapabilityRegistry(db)
    result = await cap_registry.can_perform_action(payload.action_description)

    # Convert capability dicts to response format
    capabilities = result.get("capabilities", [])
    blocked_capabilities = result.get("blocked_capabilities", [])

    return {
        "possible": result["possible"],
        "capabilities": capabilities,
        "blocked_reason": result.get("blocked_reason"),
        "blocked_capabilities": blocked_capabilities,
    }


@router.get("/api/mcp/capabilities/{capability_id}", response_model=CapabilityResponse)
async def get_capability(
    capability_id: str,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get a specific capability by ID.

    Args:
        capability_id: Unique capability ID (format: server:type:name)
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Capability details

    Raises:
        HTTPException: If capability not found
    """
    cap_registry = CapabilityRegistry(db)
    capability = await cap_registry.get_capability(capability_id)
    if not capability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability '{capability_id}' not found",
        )
    return capability.to_dict()


@router.get("/api/mcp/capabilities/server/{server_id}", response_model=CapabilityListResponse)
async def list_server_capabilities(
    server_id: str,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """List all capabilities from a specific server.

    Args:
        server_id: Server identifier
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of capabilities from that server
    """
    cap_registry = CapabilityRegistry(db)
    capabilities = await cap_registry.get_capabilities_by_server(server_id)
    return {
        "capabilities": [c.to_dict() for c in capabilities],
        "total": len(capabilities),
    }


@router.get("/api/mcp/capabilities/find-tool/{tool_name}")
async def find_tool_server(
    tool_name: str,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Find which server provides a specific tool.

    Reverse mapping from tool name to server.

    Args:
        tool_name: Name of the tool to find
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Server ID or not found message
    """
    cap_registry = CapabilityRegistry(db)
    server_id = await cap_registry.find_server_for_tool(tool_name)
    if server_id:
        return {"found": True, "server_id": server_id, "tool_name": tool_name}
    return {"found": False, "server_id": None, "tool_name": tool_name}


@router.get("/api/mcp/integrations", response_model=IntegrationStatusListResponse)
async def list_integrations(
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get status of all MCP integrations for user-facing display.

    Provides overview of available integrations, their status, and capability counts.

    Args:
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of integration statuses
    """
    cap_registry = CapabilityRegistry(db)
    integrations = await cap_registry.get_integration_status()
    return {"integrations": integrations}


@router.get("/api/mcp/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    server_id: str | None = Query(None, description="Filter by server"),
    tool_name: str | None = Query(None, description="Filter by tool"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get usage statistics from execution logs.

    Args:
        server_id: Optional server filter
        tool_name: Optional tool filter
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Usage statistics per server:tool
    """
    cap_registry = CapabilityRegistry(db)
    usage = await cap_registry.get_usage_stats(
        server_id=server_id, tool_name=tool_name
    )
    return {"usage": usage}
