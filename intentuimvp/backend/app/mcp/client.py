"""MCP Client Adapter.

Provides a simplified interface for agents to interact with MCP tools.
Handles the complexity of server management, security validation, and execution.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.manager import MCPManager, ToolExecutionResult


class MCPClient:
    """High-level client for agents to interact with MCP tools.

    Provides a simple, agent-friendly interface that abstracts away
    the complexity of MCP server connections and security validation.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the MCP client.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self._manager = MCPManager(session)

    async def initialize(self) -> None:
        """Initialize the client and start all enabled MCP servers.

        Should be called when the application starts.
        """
        await self._manager.start_all_enabled()

    async def shutdown(self) -> None:
        """Shutdown the client and stop all MCP connections.

        Should be called when the application shuts down.
        """
        await self._manager.stop_all()

    async def list_available_tools(self) -> dict[str, Any]:
        """List all available tools from all connected servers.

        Returns a structured format suitable for agent consumption:
        {
            "google-calendar": {
                "tools": [
                    {"name": "create_event", "description": "..."},
                    ...
                ]
            },
            ...
        }

        Returns:
            Dictionary of server_id to tools
        """
        return await self._manager.get_all_available_tools()

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        initiated_by: str = "agent",
        server_id: str | None = None,
    ) -> ToolExecutionResult:
        """Call an MCP tool by name.

        This is the main method agents will use. It handles:
        - Finding the server that provides the tool
        - Security validation
        - Execution with confirmation handling

        Args:
            tool_name: Name of the tool to call (e.g., "create_event")
            arguments: Tool arguments
            initiated_by: Agent or user ID
            server_id: Optional server ID (if None, will search all servers)

        Returns:
            ToolExecutionResult with the outcome
        """
        # If server_id not provided, find the server that has this tool
        if server_id is None:
            server_id = await self._find_server_for_tool(tool_name)
            if server_id is None:
                return ToolExecutionResult(
                    success=False, error=f"Tool '{tool_name}' not found on any server"
                )

        return await self._manager.execute_tool(
            server_id=server_id,
            tool_name=tool_name,
            arguments=arguments,
            initiated_by=initiated_by,
            user_confirmed=False,
        )

    async def call_tool_with_confirmation(
        self,
        tool_name: str,
        arguments: dict,
        initiated_by: str = "agent",
        server_id: str | None = None,
    ) -> ToolExecutionResult:
        """Call an MCP tool with user confirmation.

        Use this method when the user has already confirmed the action.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            initiated_by: Agent or user ID
            server_id: Optional server ID

        Returns:
            ToolExecutionResult with the outcome
        """
        if server_id is None:
            server_id = await self._find_server_for_tool(tool_name)
            if server_id is None:
                return ToolExecutionResult(
                    success=False, error=f"Tool '{tool_name}' not found"
                )

        return await self._manager.execute_tool(
            server_id=server_id,
            tool_name=tool_name,
            arguments=arguments,
            initiated_by=initiated_by,
            user_confirmed=True,
        )

    async def get_tool_info(self, tool_name: str) -> dict[str, Any] | None:
        """Get information about a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool information dict or None if not found
        """
        all_tools = await self.list_available_tools()

        for server_id, tools_data in all_tools.items():
            for tool in tools_data.get("tools", []):
                if tool["name"] == tool_name:
                    return {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "server_id": server_id,
                        "input_schema": tool.get("inputSchema", {}),
                    }

        return None

    async def check_security(self, tool_name: str) -> dict[str, Any]:
        """Check the security level of a tool.

        Returns information about whether a tool requires confirmation
        or is blocked. Useful for presenting confirmation dialogs to users.

        Args:
            tool_name: Name of the tool

        Returns:
            Dict with security information
        """
        server_id = await self._find_server_for_tool(tool_name)
        if server_id is None:
            return {
                "found": False,
                "security_level": "unknown",
            }

        validator = await self._manager.get_validator()
        decision = await validator.check_permission(server_id, tool_name, "check")

        return {
            "found": True,
            "server_id": server_id,
            "security_level": decision.security_level.value,
            "requires_confirmation": decision.requires_confirmation,
            "allowed": decision.allowed,
            "reason": decision.reason,
        }

    async def _find_server_for_tool(self, tool_name: str) -> str | None:
        """Find which server provides a given tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Server ID or None if not found
        """
        all_tools = await self.list_available_tools()

        for server_id, tools_data in all_tools.items():
            for tool in tools_data.get("tools", []):
                if tool["name"] == tool_name:
                    return server_id

        return None

    async def get_manager(self) -> MCPManager:
        """Get the underlying MCP manager.

        Useful for advanced operations not exposed by the client.
        """
        return self._manager


class AgentMCPAdapter:
    """Adapter specifically designed for agent integration.

    Provides a minimal, agent-friendly interface that fits naturally
    into agent workflows.
    """

    def __init__(self, client: MCPClient) -> None:
        """Initialize the adapter.

        Args:
            client: MCPClient instance
        """
        self._client = client

    async def get_tools(self) -> list[dict]:
        """Get list of available tools in agent-friendly format.

        Returns:
            List of tool descriptors suitable for agent tool selection
        """
        all_tools = await self._client.list_available_tools()
        agent_tools: list[dict] = []

        for server_id, tools_data in all_tools.items():
            for tool in tools_data.get("tools", []):
                agent_tools.append(
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "server": server_id,
                        "input_schema": tool.get("inputSchema", {}),
                    }
                )

        return agent_tools

    async def run_tool(
        self,
        tool_name: str,
        args: dict,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """Execute a tool and return a simple result dict.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            confirmed: Whether user has confirmed this action

        Returns:
            Dict with success, result, and error fields
        """
        if confirmed:
            result = await self._client.call_tool_with_confirmation(
                tool_name=tool_name, arguments=args, initiated_by="agent"
            )
        else:
            result = await self._client.call_tool(
                tool_name=tool_name, arguments=args, initiated_by="agent"
            )

        return {
            "success": result.success,
            "result": result.result,
            "error": result.error,
            "requires_confirmation": result.required_confirmation,
        }
