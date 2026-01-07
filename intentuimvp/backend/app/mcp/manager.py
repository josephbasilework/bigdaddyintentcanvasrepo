"""MCP Manager - Lifecycle management for MCP servers.

Manages connection lifecycle, tool discovery, and execution for MCP servers.
Integrates with the registry and security validator.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.registry import MCPServerRegistry
from app.mcp.security import MCPSecurityValidator


@dataclass
class ToolExecutionResult:
    """Result of an MCP tool execution.

    Attributes:
        success: Whether execution succeeded
        result: The result data from the tool
        error: Error message if execution failed
        required_confirmation: Whether user confirmation was required
    """

    success: bool
    result: Any | None = None
    error: str | None = None
    required_confirmation: bool = False


class MCPManager:
    """Manages MCP server connections and tool execution.

    Responsibilities:
    - Start/stop MCP server connections
    - Discover available tools from connected servers
    - Execute tools with security validation
    - Handle errors and retry logic
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the MCP manager.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self._session = session
        self._registry = MCPServerRegistry(session)
        self._validator = MCPSecurityValidator(session)
        # Active connections: server_id -> ClientSession
        self._connections: dict[str, ClientSession] = {}
        # Connection lock for thread safety
        self._connection_lock = asyncio.Lock()

    async def start_server(self, server_id: str) -> bool:
        """Start an MCP server connection.

        Args:
            server_id: Server identifier

        Returns:
            True if connection succeeded, False otherwise
        """
        async with self._connection_lock:
            # Check if already connected
            if server_id in self._connections:
                return True

            # Get server config from registry
            server = await self._registry.get_server(server_id)
            if not server:
                return False
            if not server.enabled:
                return False

            try:
                # Create connection based on transport type
                if server.transport_type == "stdio":
                    return await self._start_stdio_server(server)
                elif server.transport_type == "sse":
                    # SSE transport not implemented yet
                    return False
                else:
                    return False
            except Exception as e:
                print(f"Failed to start MCP server {server_id}: {e}")
                return False

    async def _start_stdio_server(self, server: Any) -> bool:
        """Start an stdio-based MCP server.

        Args:
            server: MCPServer instance

        Returns:
            True if connection succeeded
        """
        transport_config = server.transport_config
        command = transport_config.get("command", [])
        args = transport_config.get("args", [])
        env = transport_config.get("env", {})

        # Create server parameters
        server_params = StdioServerParameters(
            command=command[0] if command else "",
            args=command[1:] if len(command) > 1 else args,
            env=env,
        )

        # Connect to server
        stdio_transport = await stdio_client(server_params)
        stdio_read, stdio_write = stdio_transport

        # Create session
        session = ClientSession(stdio_read, stdio_write)
        await session.initialize()

        # Store connection
        self._connections[server.server_id] = session
        return True

    async def stop_server(self, server_id: str) -> bool:
        """Stop an MCP server connection.

        Args:
            server_id: Server identifier

        Returns:
            True if stopped successfully, False otherwise
        """
        async with self._connection_lock:
            if server_id not in self._connections:
                return False

            try:
                session = self._connections[server_id]
                await session.close()
                del self._connections[server_id]
                return True
            except Exception:
                return False

    async def stop_all(self) -> None:
        """Stop all active MCP server connections."""
        server_ids = list(self._connections.keys())
        for server_id in server_ids:
            await self.stop_server(server_id)

    async def list_tools(self, server_id: str) -> list[dict] | None:
        """List available tools from a connected server.

        Args:
            server_id: Server identifier

        Returns:
            List of tool descriptors or None if server not connected
        """
        if server_id not in self._connections:
            return None

        session = self._connections[server_id]
        try:
            response = await session.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }
                for tool in response.tools
            ]
        except Exception as e:
            print(f"Failed to list tools for {server_id}: {e}")
            return None

    async def execute_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict,
        initiated_by: str,
        user_confirmed: bool = False,
    ) -> ToolExecutionResult:
        """Execute a tool on an MCP server.

        Args:
            server_id: Server identifier
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            initiated_by: User or agent initiating the call
            user_confirmed: Whether user has confirmed the execution

        Returns:
            ToolExecutionResult with the execution outcome
        """
        # Security check
        decision = await self._validator.check_permission(
            server_id, tool_name, initiated_by
        )

        if not decision.allowed:
            await self._validator.log_execution(
                server_id=server_id,
                tool_name=tool_name,
                initiated_by=initiated_by,
                confirmed=False,
                success=False,
                error_message=decision.reason,
            )
            return ToolExecutionResult(
                success=False, error=decision.reason, required_confirmation=False
            )

        # Check if confirmation required
        if decision.requires_confirmation and not user_confirmed:
            return ToolExecutionResult(
                success=False,
                error="User confirmation required",
                required_confirmation=True,
            )

        # Execute the tool
        if server_id not in self._connections:
            return ToolExecutionResult(
                success=False, error=f"Server {server_id} not connected"
            )

        session = self._connections[server_id]
        try:
            result = await session.call_tool(tool_name, arguments=arguments)

            # Parse result content
            result_data = None
            if hasattr(result, "content"):
                result_data = [
                    {"type": item.type, "text": item.text}
                    for item in result.content
                ]
            else:
                result_data = result

            # Log successful execution
            await self._validator.log_execution(
                server_id=server_id,
                tool_name=tool_name,
                initiated_by=initiated_by,
                confirmed=user_confirmed,
                success=True,
            )

            return ToolExecutionResult(
                success=True,
                result=result_data,
                required_confirmation=decision.requires_confirmation,
            )

        except Exception as e:
            # Log failed execution
            await self._validator.log_execution(
                server_id=server_id,
                tool_name=tool_name,
                initiated_by=initiated_by,
                confirmed=user_confirmed,
                success=False,
                error_message=str(e),
            )

            return ToolExecutionResult(
                success=False,
                error=str(e),
                required_confirmation=decision.requires_confirmation,
            )

    async def get_all_available_tools(self) -> dict[str, list[dict]]:
        """Get all available tools from all connected servers.

        Returns:
            Dictionary mapping server_id to list of available tools
        """
        tools_by_server: dict[str, list[dict]] = {}

        for server_id in self._connections.keys():
            tools = await self.list_tools(server_id)
            if tools:
                tools_by_server[server_id] = tools

        return tools_by_server

    async def start_all_enabled(self) -> dict[str, bool]:
        """Start all enabled MCP servers.

        Returns:
            Dictionary mapping server_id to connection success status
        """
        servers = await self._registry.list_servers(enabled_only=True)
        results: dict[str, bool] = {}

        for server in servers:
            results[server.server_id] = await self.start_server(server.server_id)

        return results

    async def get_registry(self) -> MCPServerRegistry:
        """Get the MCP server registry."""
        return self._registry

    async def get_validator(self) -> MCPSecurityValidator:
        """Get the security validator."""
        return self._validator

    async def health_check(self, server_id: str) -> bool:
        """Check if a server connection is healthy.

        Args:
            server_id: Server identifier

        Returns:
            True if connection is healthy
        """
        if server_id not in self._connections:
            return False

        try:
            # Try to ping the server
            await self.list_tools(server_id)
            return True
        except Exception:
            return False
