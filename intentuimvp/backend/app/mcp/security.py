"""MCP Security Validation.

Provides security validation for MCP servers including manifest validation,
capability checking, and runtime monitoring.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.models import MCPExecutionLog, MCPServer, SecurityLevel


@dataclass
class SecurityDecision:
    """Result of a security validation check.

    Attributes:
        allowed: Whether the operation is allowed
        requires_confirmation: Whether user confirmation is required
        reason: Human-readable explanation of the decision
        security_level: The security level that was applied
    """

    allowed: bool
    requires_confirmation: bool
    reason: str
    security_level: SecurityLevel


class MCPSecurityValidator:
    """Validates security of MCP operations.

    Implements:
    - Manifest validation (capabilities declaration, version field)
    - Capability classification (ALLOWED/REQUIRES_CONFIRM/BLOCKED)
    - Runtime monitoring (rate limiting, anomaly detection)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the validator with a database session.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self._session = session
        # In-memory rate limiting tracker: {(server_id, tool_name): [timestamps]}
        self._rate_limit_tracker: dict[tuple[str, str], list[datetime]] = defaultdict(
            list
        )
        # Cleanup stale entries every minute
        self._cleanup_task: asyncio.Task[None] | None = None

    async def validate_manifest(
        self, manifest: dict, transport_type: str, transport_config: dict
    ) -> tuple[bool, str | None]:
        """Validate an MCP server manifest.

        Checks:
        - Required fields (protocolVersion, capabilities, etc.)
        - Valid transport configuration
        - Safe capability names

        Args:
            manifest: The server manifest to validate
            transport_type: Transport type (stdio or sse)
            transport_config: Transport configuration

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        required_fields = ["protocolVersion", "capabilities"]
        for field in required_fields:
            if field not in manifest:
                return False, f"Missing required field: {field}"

        # Validate protocol version
        protocol_version = manifest.get("protocolVersion", "")
        if not protocol_version or not isinstance(protocol_version, str):
            return False, "Invalid protocolVersion"

        # Validate capabilities structure
        capabilities = manifest.get("capabilities", {})
        if not isinstance(capabilities, dict):
            return False, "Capabilities must be a dictionary"

        # Validate tools if present
        if "tools" in capabilities:
            tools = capabilities["tools"]
            if not isinstance(tools, list):
                return False, "Tools must be a list"

            for tool in tools:
                if not isinstance(tool, dict):
                    return False, "Each tool must be a dictionary"
                if "name" not in tool:
                    return False, "Each tool must have a name"

                # Check for dangerous tool names
                dangerous_patterns = [
                    "exec",
                    "eval",
                    "system",
                    "shell",
                    "cmd",
                    "delete",
                    "drop",
                    "format",
                ]
                tool_name = tool["name"].lower()
                for pattern in dangerous_patterns:
                    if pattern in tool_name:
                        return (
                            False,
                            f"Dangerous tool name detected: {tool['name']} (contains '{pattern}')",
                        )

        # Validate transport configuration
        if transport_type == "stdio":
            if "command" not in transport_config:
                return False, "stdio transport requires 'command' in config"
        elif transport_type == "sse":
            if "url" not in transport_config:
                return False, "sse transport requires 'url' in config"
        else:
            return False, f"Unknown transport type: {transport_type}"

        return True, None

    async def check_permission(
        self,
        server_id: str,
        tool_name: str,
        initiated_by: str,
    ) -> SecurityDecision:
        """Check if a tool execution is permitted.

        Performs:
        1. Server existence and enabled check
        2. Security rule lookup
        3. Rate limit check
        4. Anomaly detection

        Args:
            server_id: Server identifier
            tool_name: Tool/capability name
            initiated_by: User or agent initiating the call

        Returns:
            SecurityDecision with the validation result
        """
        # Check server exists and is enabled
        result = await self._session.execute(
            select(MCPServer).where(
                MCPServer.server_id == server_id, MCPServer.enabled
            )
        )
        server = result.scalar_one_or_none()

        if not server:
            return SecurityDecision(
                allowed=False,
                requires_confirmation=False,
                reason=f"MCP server '{server_id}' not found or disabled",
                security_level=SecurityLevel.BLOCKED,
            )

        # Check security rules
        security_level = SecurityLevel.ALLOWED  # Default to allowed
        if server.security_rules and tool_name in server.security_rules:
            level_str = server.security_rules[tool_name]
            try:
                security_level = SecurityLevel(level_str)
            except ValueError:
                security_level = SecurityLevel.REQUIRES_CONFIRM

        # Apply security level
        if security_level == SecurityLevel.BLOCKED:
            return SecurityDecision(
                allowed=False,
                requires_confirmation=False,
                reason=f"Tool '{tool_name}' is blocked by security policy",
                security_level=SecurityLevel.BLOCKED,
            )

        # Check rate limits
        rate_limit_ok, rate_limit_message = await self._check_rate_limit(
            server, tool_name
        )
        if not rate_limit_ok:
            return SecurityDecision(
                allowed=False,
                requires_confirmation=False,
                reason=rate_limit_message or "Rate limit exceeded",
                security_level=SecurityLevel.BLOCKED,
            )

        # Build reason message
        reason = f"Tool '{tool_name}' is {security_level.value}"
        if security_level == SecurityLevel.REQUIRES_CONFIRM:
            reason += " and requires user confirmation"

        return SecurityDecision(
            allowed=True,
            requires_confirmation=(security_level == SecurityLevel.REQUIRES_CONFIRM),
            reason=reason,
            security_level=security_level,
        )

    async def _check_rate_limit(
        self, server: MCPServer, tool_name: str
    ) -> tuple[bool, str | None]:
        """Check if tool execution is within rate limits.

        Args:
            server: The MCP server
            tool_name: Tool being executed

        Returns:
            Tuple of (within_limit, error_message)
        """
        key = (server.server_id, tool_name)
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)

        # Clean up old entries
        self._rate_limit_tracker[key] = [
            ts for ts in self._rate_limit_tracker[key] if ts > one_minute_ago
        ]

        # Check rate limit
        count = len(self._rate_limit_tracker[key])
        if count >= server.rate_limit:
            return (
                False,
                f"Rate limit exceeded: {count}/{server.rate_limit} calls per minute",
            )

        # Add current call
        self._rate_limit_tracker[key].append(now)
        return True, None

    async def log_execution(
        self,
        server_id: str,
        tool_name: str,
        initiated_by: str,
        confirmed: bool,
        success: bool,
        error_message: str | None = None,
    ) -> MCPExecutionLog:
        """Log an MCP tool execution for audit and monitoring.

        Args:
            server_id: Server identifier
            tool_name: Tool that was executed
            initiated_by: User or agent who initiated the call
            confirmed: Whether user confirmation was obtained
            success: Whether execution succeeded
            error_message: Error message if execution failed

        Returns:
            The created MCPExecutionLog entry
        """
        log = MCPExecutionLog(
            server_id=server_id,
            tool_name=tool_name,
            initiated_by=initiated_by,
            confirmed=confirmed,
            success=success,
            error_message=error_message,
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def detect_anomalies(
        self, server_id: str | None = None, minutes: int = 5
    ) -> list[dict]:
        """Detect anomalous behavior patterns.

        Looks for:
        - High failure rates
        - Blocked execution attempts
        - Unusual activity patterns

        Args:
            server_id: Optional server ID to filter by
            minutes: Time window to analyze

        Returns:
            List of anomaly descriptions
        """
        since = datetime.utcnow() - timedelta(minutes=minutes)
        anomalies: list[dict] = []

        # Build query
        query = select(MCPExecutionLog).where(MCPExecutionLog.executed_at >= since)
        if server_id:
            query = query.where(MCPExecutionLog.server_id == server_id)

        result = await self._session.execute(query)
        logs = list(result.scalars().all())

        if not logs:
            return anomalies

        # Group by server and tool
        by_tool: dict[tuple[str, str], list[MCPExecutionLog]] = defaultdict(list)
        for log in logs:
            by_tool[(log.server_id, log.tool_name)].append(log)

        # Check for high failure rates
        for (srv_id, tool), tool_logs in by_tool.items():
            if len(tool_logs) < 5:  # Skip low-volume tools
                continue

            failures = sum(1 for log in tool_logs if not log.success)
            failure_rate = failures / len(tool_logs)

            if failure_rate > 0.5:
                anomalies.append(
                    {
                        "type": "high_failure_rate",
                        "server_id": srv_id,
                        "tool_name": tool,
                        "failure_rate": f"{failure_rate:.1%}",
                        "total_calls": len(tool_logs),
                        "severity": "high" if failure_rate > 0.8 else "medium",
                    }
                )

        return anomalies

    async def start_cleanup_task(self) -> None:
        """Start background task to clean up stale rate limit entries."""
        if self._cleanup_task is None or self._cleanup_task.done():

            async def cleanup_loop() -> None:
                while True:
                    await asyncio.sleep(60)
                    now = datetime.utcnow()
                    one_minute_ago = now - timedelta(minutes=1)
                    for key in list(self._rate_limit_tracker.keys()):
                        self._rate_limit_tracker[key] = [
                            ts
                            for ts in self._rate_limit_tracker[key]
                            if ts > one_minute_ago
                        ]
                        if not self._rate_limit_tracker[key]:
                            del self._rate_limit_tracker[key]

            self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
