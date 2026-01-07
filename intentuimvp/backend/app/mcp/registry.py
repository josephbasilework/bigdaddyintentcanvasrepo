"""MCP Server Registry.

Manages registration, configuration, and discovery of MCP servers.
Provides the interface for dynamically adding/removing MCP integrations.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.models import MCPServer, SecurityLevel


class MCPServerRegistry:
    """Registry for managing MCP server configurations.

    Handles CRUD operations for MCP servers, including capability
    registration and security rule management.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the registry with a database session.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self._session = session

    async def register_server(
        self,
        server_id: str,
        name: str,
        transport_type: str,
        transport_config: dict,
        description: str | None = None,
        version: str | None = None,
        capabilities: dict | None = None,
        security_rules: dict | None = None,
        enabled: bool = True,
        rate_limit: int = 60,
    ) -> MCPServer:
        """Register a new MCP server or update existing one.

        Args:
            server_id: Unique identifier for the server
            name: Human-readable name
            transport_type: Transport type ('stdio' or 'sse')
            transport_config: Connection configuration
            description: Optional description
            version: Server version from manifest
            capabilities: Server capabilities from manifest
            security_rules: Security classification per capability
            enabled: Whether server is enabled
            rate_limit: Max calls per minute

        Returns:
            The created or updated MCPServer instance
        """
        # Check if server already exists
        result = await self._session.execute(
            select(MCPServer).where(MCPServer.server_id == server_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing server
            existing.name = name
            existing.description = description
            existing.transport_type = transport_type
            existing.transport_config = transport_config
            existing.version = version
            existing.capabilities = capabilities or {}
            existing.security_rules = security_rules or {}
            existing.enabled = enabled
            existing.rate_limit = rate_limit
            return existing
        else:
            # Create new server
            server = MCPServer(
                server_id=server_id,
                name=name,
                description=description,
                transport_type=transport_type,
                transport_config=transport_config,
                version=version,
                capabilities=capabilities or {},
                security_rules=security_rules or {},
                enabled=enabled,
                rate_limit=rate_limit,
            )
            self._session.add(server)
            await self._session.flush()
            return server

    async def get_server(self, server_id: str) -> MCPServer | None:
        """Get a registered MCP server by ID.

        Args:
            server_id: Unique server identifier

        Returns:
            MCPServer instance or None if not found
        """
        result = await self._session.execute(
            select(MCPServer).where(MCPServer.server_id == server_id)
        )
        return result.scalar_one_or_none()

    async def list_servers(
        self, enabled_only: bool = True
    ) -> list[MCPServer]:
        """List all registered MCP servers.

        Args:
            enabled_only: If True, only return enabled servers

        Returns:
            List of MCPServer instances
        """
        query = select(MCPServer)
        if enabled_only:
            query = query.where(MCPServer.enabled)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def unregister_server(self, server_id: str) -> bool:
        """Unregister (delete) an MCP server.

        Args:
            server_id: Unique server identifier

        Returns:
            True if server was deleted, False if not found
        """
        server = await self.get_server(server_id)
        if not server:
            return False
        await self._session.delete(server)
        return True

    async def update_server(
        self,
        server_id: str,
        **updates: Any,
    ) -> MCPServer | None:
        """Update specific fields of an MCP server.

        Args:
            server_id: Unique server identifier
            **updates: Fields to update (name, description, enabled, etc.)

        Returns:
            Updated MCPServer instance or None if not found
        """
        server = await self.get_server(server_id)
        if not server:
            return None

        for key, value in updates.items():
            if hasattr(server, key):
                setattr(server, key, value)

        return server

    async def set_security_rule(
        self,
        server_id: str,
        tool_name: str,
        security_level: SecurityLevel,
    ) -> bool:
        """Set security classification for a specific tool.

        Args:
            server_id: Server identifier
            tool_name: Name of the tool/capability
            security_level: Security classification (ALLOWED, REQUIRES_CONFIRM, BLOCKED)

        Returns:
            True if updated, False if server not found
        """
        server = await self.get_server(server_id)
        if not server:
            return False

        if server.security_rules is None:
            server.security_rules = {}
        server.security_rules[tool_name] = security_level.value
        return True

    async def get_security_rule(
        self,
        server_id: str,
        tool_name: str,
    ) -> SecurityLevel | None:
        """Get security classification for a specific tool.

        Args:
            server_id: Server identifier
            tool_name: Name of the tool/capability

        Returns:
            SecurityLevel or None if not found
        """
        server = await self.get_server(server_id)
        if not server or not server.security_rules:
            return None

        level_str = server.security_rules.get(tool_name)
        if not level_str:
            return None

        try:
            return SecurityLevel(level_str)
        except ValueError:
            return None

    async def get_all_tools(self) -> dict[str, dict[str, Any]]:
        """Get all available tools from all enabled servers.

        Returns:
            Dictionary mapping server_id to their available tools
        """
        servers = await self.list_servers(enabled_only=True)
        tools_by_server: dict[str, dict[str, Any]] = {}

        for server in servers:
            if server.capabilities and "tools" in server.capabilities:
                tools_by_server[server.server_id] = {
                    "name": server.name,
                    "description": server.description,
                    "tools": server.capabilities["tools"],
                }

        return tools_by_server


# Predefined security rules for common MCP capabilities
DEFAULT_SECURITY_RULES: dict[str, dict[str, SecurityLevel]] = {
    # Google Calendar - read operations are safe, writes need confirmation
    "google-calendar": {
        "calendar_list": SecurityLevel.ALLOWED,
        "calendar_read": SecurityLevel.ALLOWED,
        "calendar_create": SecurityLevel.REQUIRES_CONFIRM,
        "calendar_update": SecurityLevel.REQUIRES_CONFIRM,
        "calendar_delete": SecurityLevel.BLOCKED,
    },
    # Filesystem - very dangerous, most operations blocked
    "filesystem": {
        "file_read": SecurityLevel.REQUIRES_CONFIRM,
        "file_write": SecurityLevel.REQUIRES_CONFIRM,
        "file_delete": SecurityLevel.BLOCKED,
        "file_list": SecurityLevel.ALLOWED,
    },
}
