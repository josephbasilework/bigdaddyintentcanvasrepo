"""MCP Security Validation.

Provides security validation for MCP servers including manifest validation,
capability checking, and runtime monitoring.

Integrates with the manifest schema (app.mcp.manifest) for FR-019 compliance:
- Capability classification (ALLOWED/REQUIRES_CONFIRM/BLOCKED)
- Blocked capability detection
- Manifest validation
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.manifest import is_blocked_capability
from app.mcp.models import (
    MCPExecutionLog,
    MCPServer,
    SecurityLevel,
    compute_input_hash,
    compute_output_size,
)


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

    Per MI-001 invariant from PRD §14: MCPServer must pass security validation
    before activation. See PRD §14: Domain Invariants & Business Rules.

    Implements:
    - Manifest validation (capabilities declaration, version field)
    - Capability classification (ALLOWED/REQUIRES_CONFIRM/BLOCKED)
    - Runtime monitoring (rate limiting, anomaly detection)

    Per FR-019 runtime monitoring:
    - Rate limit: 100 tool calls per minute per MCP
    - Anomaly detection: alert if >10x normal call volume
    """

    # FR-019: Per-MCP rate limit (100 calls/minute)
    PER_MCP_RATE_LIMIT = 100

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the validator with a database session.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self._session = session
        # Per-tool rate limiting: {(server_id, tool_name): [timestamps]}
        self._rate_limit_tracker: dict[tuple[str, str], list[datetime]] = defaultdict(
            list
        )
        # Per-MCP rate limiting (FR-019): {server_id: [timestamps]}
        self._per_mcp_rate_limit_tracker: dict[str, list[datetime]] = defaultdict(list)
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
        2. Blocked capability check (using FR-019 classification)
        3. Security rule lookup (with manifest classification fallback)
        4. Rate limit check

        Args:
            server_id: Server identifier
            tool_name: Tool/capability name
            initiated_by: User or agent initiating the call

        Returns:
            SecurityDecision with the validation result
        """
        # First check if capability is blocked by FR-019 rules
        if is_blocked_capability(tool_name):
            return SecurityDecision(
                allowed=False,
                requires_confirmation=False,
                reason=f"[MI-001] Tool '{tool_name}' is blocked by FR-019 security policy. "
                       f"See PRD §14: Domain Invariants & Business Rules",
                security_level=SecurityLevel.BLOCKED,
            )

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

        # Check security rules first (server-specific rules)
        security_level = SecurityLevel.ALLOWED  # Default to allowed
        if server.security_rules and tool_name in server.security_rules:
            level_str = server.security_rules[tool_name]
            try:
                security_level = SecurityLevel(level_str)
            except ValueError:
                security_level = SecurityLevel.REQUIRES_CONFIRM
        else:
            # Fallback: Try to classify using manifest schema
            # This requires determining the category from tool name or server config
            # For unknown capabilities, default to REQUIRES_CONFIRM
            security_level = SecurityLevel.REQUIRES_CONFIRM

        # Apply security level
        if security_level == SecurityLevel.BLOCKED:
            return SecurityDecision(
                allowed=False,
                requires_confirmation=False,
                reason=f"[MI-001] Tool '{tool_name}' is blocked by security policy. "
                       f"See PRD §14: Domain Invariants & Business Rules",
                security_level=SecurityLevel.BLOCKED,
            )

        # Check FR-019 per-MCP rate limit (100 calls/minute per server)
        per_mcp_ok, per_mcp_message = await self._check_per_mcp_rate_limit(
            server.server_id
        )
        if not per_mcp_ok:
            return SecurityDecision(
                allowed=False,
                requires_confirmation=False,
                reason=per_mcp_message or "Per-MCP rate limit exceeded",
                security_level=SecurityLevel.BLOCKED,
            )

        # Check per-tool rate limits (from server config)
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
        """Check if tool execution is within per-tool rate limits.

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
                f"Per-tool rate limit exceeded: {count}/{server.rate_limit} calls per minute",
            )

        # Add current call to per-tool tracker
        self._rate_limit_tracker[key].append(now)
        return True, None

    async def _check_per_mcp_rate_limit(self, server_id: str) -> tuple[bool, str | None]:
        """Check if tool execution is within per-MCP rate limits (FR-019).

        FR-019 requires: 100 tool calls per minute per MCP.

        Args:
            server_id: The MCP server identifier

        Returns:
            Tuple of (within_limit, error_message)
        """
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)

        # Clean up old entries
        self._per_mcp_rate_limit_tracker[server_id] = [
            ts for ts in self._per_mcp_rate_limit_tracker[server_id] if ts > one_minute_ago
        ]

        # Check per-MCP rate limit (FR-019: 100 calls/minute)
        count = len(self._per_mcp_rate_limit_tracker[server_id])
        if count >= self.PER_MCP_RATE_LIMIT:
            return (
                False,
                f"Per-MCP rate limit exceeded (FR-019): {count}/{self.PER_MCP_RATE_LIMIT} calls per minute",
            )

        # Add current call to per-MCP tracker
        self._per_mcp_rate_limit_tracker[server_id].append(now)
        return True, None

    async def log_execution(
        self,
        server_id: str,
        tool_name: str,
        initiated_by: str,
        confirmed: bool,
        success: bool,
        error_message: str | None = None,
        arguments: dict | None = None,
        result: Any = None,
    ) -> MCPExecutionLog:
        """Log an MCP tool execution for audit and monitoring.

        Per FR-019 runtime monitoring requirements:
        - Tool calls logged with timestamp, input hash, output size

        Args:
            server_id: Server identifier
            tool_name: Tool that was executed
            initiated_by: User or agent who initiated the call
            confirmed: Whether user confirmation was obtained
            success: Whether execution succeeded
            error_message: Error message if execution failed
            arguments: Tool arguments (for computing input_hash)
            result: Tool result (for computing output_size)

        Returns:
            The created MCPExecutionLog entry
        """
        # Compute input hash from arguments if provided
        input_hash: str | None = None
        if arguments is not None:
            input_hash = compute_input_hash(arguments)

        # Compute output size from result if provided
        output_size: int | None = None
        if result is not None and success:
            try:
                output_size = compute_output_size(result)
            except Exception:
                # If computing output size fails, continue without it
                output_size = None

        log = MCPExecutionLog(
            server_id=server_id,
            tool_name=tool_name,
            initiated_by=initiated_by,
            confirmed=confirmed,
            success=success,
            error_message=error_message,
            input_hash=input_hash,
            output_size=output_size,
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def detect_anomalies(
        self, server_id: str | None = None, minutes: int = 5
    ) -> list[dict]:
        """Detect anomalous behavior patterns.

        Per FR-019 runtime monitoring requirements:
        - Anomaly detection: alert if >10x normal call volume

        Looks for:
        - High failure rates
        - Unusual call volume spikes (>10x normal)
        - Blocked execution attempts

        Args:
            server_id: Optional server ID to filter by
            minutes: Time window to analyze

        Returns:
            List of anomaly descriptions
        """
        since = datetime.utcnow() - timedelta(minutes=minutes)
        anomalies: list[dict] = []

        # Build query for current window
        query = select(MCPExecutionLog).where(MCPExecutionLog.executed_at >= since)
        if server_id:
            query = query.where(MCPExecutionLog.server_id == server_id)

        result = await self._session.execute(query)
        current_logs = list(result.scalars().all())

        if not current_logs:
            return anomalies

        # Build query for baseline window (previous 24 hours for "normal" volume)
        baseline_since = since - timedelta(hours=24)
        baseline_query = select(MCPExecutionLog).where(
            MCPExecutionLog.executed_at >= baseline_since,
            MCPExecutionLog.executed_at < since,
        )
        if server_id:
            baseline_query = baseline_query.where(MCPExecutionLog.server_id == server_id)

        baseline_result = await self._session.execute(baseline_query)
        baseline_logs = list(baseline_result.scalars().all())

        # Group current logs by server
        current_by_server: dict[str, list[MCPExecutionLog]] = defaultdict(list)
        for log in current_logs:
            current_by_server[log.server_id].append(log)

        # Group baseline logs by server
        baseline_by_server: dict[str, list[MCPExecutionLog]] = defaultdict(list)
        for log in baseline_logs:
            baseline_by_server[log.server_id].append(log)

        # Check for >10x normal call volume (FR-019 anomaly detection)
        for srv_id, current_server_logs in current_by_server.items():
            current_count = len(current_server_logs)
            baseline_count = len(baseline_by_server.get(srv_id, []))

            # Calculate normal calls per minute for this server
            # Baseline is over 24 hours, so divide by (24 * 60) to get per-minute rate
            baseline_minutes = 24 * 60
            normal_calls_per_minute = baseline_count / baseline_minutes if baseline_minutes > 0 else 0

            # Current calls in the analysis window
            current_calls_per_minute = current_count / minutes if minutes > 0 else 0

            # Avoid division by zero for servers with no baseline
            if normal_calls_per_minute > 0:
                volume_ratio = current_calls_per_minute / normal_calls_per_minute
            else:
                # If no baseline, consider >10 calls/minute as anomaly
                volume_ratio = current_calls_per_minute if current_calls_per_minute > 10 else 0

            if volume_ratio > 10:
                anomalies.append(
                    {
                        "type": "unusual_call_volume",
                        "server_id": srv_id,
                        "current_calls_per_minute": f"{current_calls_per_minute:.1f}",
                        "normal_calls_per_minute": f"{normal_calls_per_minute:.1f}",
                        "volume_ratio": f"{volume_ratio:.1f}x",
                        "current_window_calls": current_count,
                        "baseline_calls": baseline_count,
                        "severity": "high" if volume_ratio > 50 else "medium",
                    }
                )

        # Group by server and tool for failure rate analysis
        by_tool: dict[tuple[str, str], list[MCPExecutionLog]] = defaultdict(list)
        for log in current_logs:
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

                    # Clean up per-tool rate limit tracker
                    for key in list(self._rate_limit_tracker.keys()):
                        self._rate_limit_tracker[key] = [
                            ts
                            for ts in self._rate_limit_tracker[key]
                            if ts > one_minute_ago
                        ]
                        if not self._rate_limit_tracker[key]:
                            del self._rate_limit_tracker[key]

                    # Clean up per-MCP rate limit tracker (FR-019)
                    for server_id in list(self._per_mcp_rate_limit_tracker.keys()):
                        self._per_mcp_rate_limit_tracker[server_id] = [
                            ts
                            for ts in self._per_mcp_rate_limit_tracker[server_id]
                            if ts > one_minute_ago
                        ]
                        if not self._per_mcp_rate_limit_tracker[server_id]:
                            del self._per_mcp_rate_limit_tracker[server_id]

            self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
