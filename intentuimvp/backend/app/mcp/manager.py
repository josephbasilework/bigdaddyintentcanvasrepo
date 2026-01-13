"""MCP Manager - Lifecycle management for MCP servers.

Manages connection lifecycle, tool discovery, and execution for MCP servers.
Integrates with the registry and security validator.

Implements graceful degradation (FR-019 VI-006):
- Retry logic with exponential backoff for failed connections
- Health tracking for servers (healthy/degraded/unhealthy)
- Automatic disabling of persistently failing servers
- Degraded mode notifications when servers are unavailable
"""

import asyncio
import logging
import sys
import time
from collections import defaultdict
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

# Import mcp SDK, avoiding shadowing by local app.mcp module
# Temporarily remove app.mcp from sys.modules if present
_app_mcp = sys.modules.pop("app.mcp", None)
try:
    from mcp import ClientSession, StdioServerParameters  # type: ignore[attr-defined]
    from mcp.client.stdio import stdio_client  # type: ignore[reportMissingImports]
finally:
    # Restore app.mcp to sys.modules
    if _app_mcp is not None:
        sys.modules["app.mcp"] = _app_mcp
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.logging_config import get_correlation_id  # noqa: E402
from app.mcp.registry import MCPServerRegistry  # noqa: E402
from app.mcp.security import MCPSecurityValidator  # noqa: E402

logger = logging.getLogger(__name__)


class ServerHealth(Enum):
    """Health state of an MCP server connection."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ServerHealthState:
    """Tracks the health state of an MCP server.

    Attributes:
        state: Current health state
        consecutive_failures: Number of consecutive failures
        last_failure_time: Timestamp of the last failure
        last_success_time: Timestamp of the last successful operation
    """

    state: ServerHealth = ServerHealth.HEALTHY
    consecutive_failures: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None

    # Graceful degradation thresholds (FR-019)
    FAILURE_THRESHOLD_DEGRADED = 3  # After 3 consecutive failures, mark as degraded
    FAILURE_THRESHOLD_UNHEALTHY = 5  # After 5 consecutive failures, mark as unhealthy
    DEGRADED_RECOVERY_TIME = timedelta(minutes=5)  # Time before attempting degraded recovery
    UNHEALTHY_DISABLE_TIME = timedelta(minutes=15)  # Time before disabling unhealthy server

    def record_failure(self) -> bool:
        """Record a failure and return True if server should be disabled.

        Returns:
            True if server should be automatically disabled
        """
        self.consecutive_failures += 1
        self.last_failure_time = datetime.utcnow()

        # Update health state based on consecutive failures
        if self.consecutive_failures >= self.FAILURE_THRESHOLD_UNHEALTHY:
            self.state = ServerHealth.UNHEALTHY
            # Check if server should be disabled (failed for too long)
            if self.last_failure_time:
                time_since_first_failure = datetime.utcnow() - (
                    self.last_failure_time - timedelta(minutes=self.consecutive_failures)
                )
                if time_since_first_failure > self.UNHEALTHY_DISABLE_TIME:
                    return True
        elif self.consecutive_failures >= self.FAILURE_THRESHOLD_DEGRADED:
            self.state = ServerHealth.DEGRADED

        return False

    def record_success(self) -> None:
        """Record a successful operation and reset failure count."""
        self.consecutive_failures = 0
        self.last_success_time = datetime.utcnow()
        self.state = ServerHealth.HEALTHY

    def should_attempt_retry(self) -> bool:
        """Check if retry should be attempted based on health state."""
        if self.state == ServerHealth.HEALTHY:
            return True

        if self.state == ServerHealth.DEGRADED:
            # Retry degraded servers after recovery time
            if self.last_failure_time:
                return datetime.utcnow() - self.last_failure_time > self.DEGRADED_RECOVERY_TIME
            return True

        # Unhealthy servers are not retried automatically
        return False

    def get_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay for retry.

        Args:
            attempt: The retry attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Base exponential backoff: 2^attempt seconds, capped at 60 seconds
        delay = min(2**attempt, 60)

        # Add jitter to avoid thundering herd
        import random
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter


@dataclass
class ToolExecutionResult:
    """Result of an MCP tool execution.

    Attributes:
        success: Whether execution succeeded
        result: The result data from the tool
        error: Error message if execution failed
        required_confirmation: Whether user confirmation was required
        degraded: Whether the operation completed in degraded mode
        degraded_reason: Reason for degraded mode (e.g., "server unavailable")
    """

    success: bool
    result: Any | None = None
    error: str | None = None
    required_confirmation: bool = False
    degraded: bool = False
    degraded_reason: str | None = None


@dataclass
class MCPConnection:
    """Tracks an MCP client session with its managed cleanup stack."""

    session: ClientSession
    exit_stack: AsyncExitStack


class MCPManager:
    """Manages MCP server connections and tool execution.

    Responsibilities:
    - Start/stop MCP server connections
    - Discover available tools from connected servers
    - Execute tools with security validation
    - Handle errors and retry logic with exponential backoff (FR-019)
    - Track server health and gracefully degrade failing servers (VI-006)
    """

    # Retry configuration (FR-019 NFR-REL-001)
    MAX_RETRY_ATTEMPTS = 3
    INITIAL_RETRY_DELAY = 1.0  # seconds

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the MCP manager.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self._session = session
        self._registry = MCPServerRegistry(session)
        self._validator = MCPSecurityValidator(session)
        # Active connections: server_id -> MCPConnection
        self._connections: dict[str, MCPConnection] = {}
        # Health tracking: server_id -> ServerHealthState
        self._health_states: dict[str, ServerHealthState] = defaultdict(
            ServerHealthState
        )
        # Connection lock for thread safety
        self._connection_lock = asyncio.Lock()

    async def start_server(self, server_id: str) -> bool:
        """Start an MCP server connection with retry logic and exponential backoff.

        Per FR-019 NFR-REL-001: Retry with exponential backoff; graceful degradation.

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

            # Check health state before attempting connection
            health = self._health_states[server_id]
            if not health.should_attempt_retry():
                # Server is unhealthy and not ready for retry
                return False

            # Attempt connection with exponential backoff retry
            last_error = None
            for attempt in range(self.MAX_RETRY_ATTEMPTS):
                # Calculate delay for exponential backoff
                if attempt > 0:
                    delay = health.get_retry_delay(attempt)
                    await asyncio.sleep(delay)

                try:
                    # Create connection based on transport type
                    if server.transport_type == "stdio":
                        result = await self._start_stdio_server(server)
                        if result:
                            # Connection successful - record success
                            health.record_success()
                            return True
                        return False
                    elif server.transport_type == "sse":
                        # SSE transport not implemented yet
                        return False
                    else:
                        return False
                except Exception as e:
                    last_error = e
                    # Continue to next attempt

            # All retries failed - record failure and check if server should be disabled
            print(f"Failed to start MCP server {server_id} after {self.MAX_RETRY_ATTEMPTS} attempts: {last_error}")

            should_disable = health.record_failure()
            if should_disable:
                # Automatically disable persistently failing server (FR-019 VI-006)
                await self._registry.disable_server(server_id)
                print(f"Automatically disabled MCP server {server_id} due to persistent failures")

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

        exit_stack = AsyncExitStack()
        try:
            stdio_read, stdio_write = await exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            session = await exit_stack.enter_async_context(
                ClientSession(stdio_read, stdio_write)
            )
            await session.initialize()
        except Exception:
            await exit_stack.aclose()
            raise

        # Store connection
        self._connections[server.server_id] = MCPConnection(
            session=session, exit_stack=exit_stack
        )
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
                connection = self._connections[server_id]
                await connection.exit_stack.aclose()
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

        session = self._connections[server_id].session
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
        start_time = time.time()
        correlation_id = get_correlation_id()

        # Security check
        decision = await self._validator.check_permission(
            server_id, tool_name, initiated_by
        )

        base_extra: dict[str, Any] = {
            "event": "tool_call",
            "tool_type": "mcp",
            "server_id": server_id,
            "tool_name": tool_name,
            "initiated_by": initiated_by,
            "correlation_id": correlation_id,
            "security_level": decision.security_level.value,
        }

        def build_extra(**overrides: Any) -> dict[str, Any]:
            execution_time_ms = (time.time() - start_time) * 1000
            extra = dict(base_extra)
            extra["execution_time_ms"] = round(execution_time_ms, 2)
            extra.update(overrides)
            return extra

        if not decision.allowed:
            logger.warning(
                "MCP tool execution blocked",
                extra=build_extra(
                    success=False,
                    error=decision.reason,
                    requires_confirmation=decision.requires_confirmation,
                ),
            )
            await self._validator.log_execution(
                server_id=server_id,
                tool_name=tool_name,
                initiated_by=initiated_by,
                confirmed=False,
                success=False,
                error_message=decision.reason,
                arguments=arguments,
                result=None,
            )
            return ToolExecutionResult(
                success=False, error=decision.reason, required_confirmation=False
            )

        # Check if confirmation required
        if decision.requires_confirmation and not user_confirmed:
            logger.warning(
                "MCP tool execution requires confirmation",
                extra=build_extra(
                    success=False,
                    error="User confirmation required",
                    confirmed=user_confirmed,
                    requires_confirmation=True,
                ),
            )
            return ToolExecutionResult(
                success=False,
                error="User confirmation required",
                required_confirmation=True,
            )

        # Execute the tool
        health = self._health_states[server_id]

        # Check if server is in degraded/unhealthy state
        if health.state != ServerHealth.HEALTHY:
            logger.warning(
                "MCP tool execution skipped due to server health",
                extra=build_extra(
                    success=False,
                    error=f"Server {server_id} is {health.state.value}",
                    health_state=health.state.value,
                    consecutive_failures=health.consecutive_failures,
                ),
            )
            # Return degraded mode result (FR-019 VI-006)
            return ToolExecutionResult(
                success=False,
                error=f"Server {server_id} is {health.state.value}",
                degraded=True,
                degraded_reason=f"MCP server is in {health.state.value} state after {health.consecutive_failures} consecutive failures",
                required_confirmation=False,
            )

        if server_id not in self._connections:
            # Try to reconnect if server is not connected but healthy
            reconnect_success = await self.start_server(server_id)
            if not reconnect_success or server_id not in self._connections:
                logger.warning(
                    "MCP tool execution failed due to missing connection",
                    extra=build_extra(
                        success=False,
                        error=f"Server {server_id} not connected",
                        degraded=health.state != ServerHealth.HEALTHY,
                        health_state=health.state.value,
                    ),
                )
                return ToolExecutionResult(
                    success=False,
                    error=f"Server {server_id} not connected",
                    degraded=health.state != ServerHealth.HEALTHY,
                    degraded_reason=None if health.state == ServerHealth.HEALTHY else f"Server in {health.state.value} state",
                    required_confirmation=False,
                )

        session = self._connections[server_id].session
        try:
            result = await session.call_tool(tool_name, arguments=arguments)

            # Parse result content
            result_data: Any = None
            if hasattr(result, "content"):
                result_data = []
                for item in result.content:
                    if hasattr(item, "model_dump"):
                        result_data.append(item.model_dump())
                    else:
                        result_data.append(
                            {
                                "type": getattr(item, "type", "unknown"),
                                "text": getattr(item, "text", None),
                            }
                        )
            else:
                result_data = result

            # Record successful execution in health state
            health.record_success()

            # Log successful execution with arguments and result
            await self._validator.log_execution(
                server_id=server_id,
                tool_name=tool_name,
                initiated_by=initiated_by,
                confirmed=user_confirmed,
                success=True,
                arguments=arguments,
                result=result_data,
            )

            logger.info(
                "MCP tool executed successfully",
                extra=build_extra(
                    success=True,
                    confirmed=user_confirmed,
                    requires_confirmation=decision.requires_confirmation,
                ),
            )

            return ToolExecutionResult(
                success=True,
                result=result_data,
                required_confirmation=decision.requires_confirmation,
                degraded=False,
                degraded_reason=None,
            )

        except Exception as e:
            # Record failure in health state
            should_disable = health.record_failure()

            # Log failed execution with arguments
            await self._validator.log_execution(
                server_id=server_id,
                tool_name=tool_name,
                initiated_by=initiated_by,
                confirmed=user_confirmed,
                success=False,
                error_message=str(e),
                arguments=arguments,
                result=None,
            )

            logger.error(
                "MCP tool execution failed",
                extra=build_extra(
                    success=False,
                    error=str(e),
                    confirmed=user_confirmed,
                    requires_confirmation=decision.requires_confirmation,
                ),
                exc_info=True,
            )

            # Check if server should be auto-disabled
            if should_disable:
                await self._registry.disable_server(server_id)
                # Disconnect the server
                if server_id in self._connections:
                    await self.stop_server(server_id)

            return ToolExecutionResult(
                success=False,
                error=str(e),
                required_confirmation=decision.requires_confirmation,
                degraded=health.state != ServerHealth.HEALTHY,
                degraded_reason=None if health.state == ServerHealth.HEALTHY else f"Server in {health.state.value} state after {health.consecutive_failures} failures",
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
            tools = await self.list_tools(server_id)
            if tools is None:
                return False
            return True
        except Exception:
            return False

    def get_server_health(self, server_id: str) -> ServerHealthState:
        """Get the health state of an MCP server.

        Args:
            server_id: Server identifier

        Returns:
            ServerHealthState for the server
        """
        return self._health_states[server_id]

    def get_all_server_health(self) -> dict[str, ServerHealthState]:
        """Get health states for all tracked servers.

        Returns:
            Dictionary mapping server_id to ServerHealthState
        """
        return dict(self._health_states)

    async def reset_server_health(self, server_id: str) -> bool:
        """Reset the health state of a server (for recovery/retry).

        Args:
            server_id: Server identifier

        Returns:
            True if server was found and health reset
        """
        if server_id not in self._health_states:
            return False

        # Reset to healthy state
        self._health_states[server_id] = ServerHealthState()
        return True
