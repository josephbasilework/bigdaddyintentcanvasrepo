"""Capability Registry for MCP Introspection.

Provides capability-level indexing, search, and discovery for all registered MCPs.
Enables agents to query what capabilities exist, what's possible, and what's unavailable.

Per FR-019 requirements:
- Catalog of installed MCPs, their capabilities, permissions, status
- Agent can query what capabilities exist, what's possible, what's unavailable and why
- User-facing view of available integrations and capability status
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.manifest import SecurityCategory, SecurityLevel
from app.mcp.models import MCPExecutionLog, MCPServer


class CapabilityType(str, Enum):
    """Types of capabilities that can be registered."""

    TOOL = "tool"
    RESOURCE = "resource"
    PROMPT = "prompt"


@dataclass
class Capability:
    """Normalized representation of a capability from any MCP server.

    Provides a unified view of tools, resources, and prompts across all servers.
    """

    # Identity
    id: str  # Unique: "{server_id}:{capability_type}:{name}"
    name: str
    type: CapabilityType
    server_id: str

    # Metadata
    description: str | None = None
    category: SecurityCategory | None = None
    security_level: SecurityLevel = SecurityLevel.REQUIRES_CONFIRM

    # Server context
    server_name: str | None = None
    server_enabled: bool = True

    # For tools: input schema
    input_schema: dict | None = None

    # For resources: URI and MIME type
    uri: str | None = None
    mime_type: str | None = None

    # For prompts: arguments
    arguments: list[dict] = field(default_factory=list)

    # Analytics (optional, populated from execution logs)
    usage_count: int = 0
    last_used: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "server_id": self.server_id,
            "description": self.description,
            "category": self.category.value if self.category else None,
            "security_level": self.security_level.value,
            "server_name": self.server_name,
            "server_enabled": self.server_enabled,
            "input_schema": self.input_schema,
            "uri": self.uri,
            "mime_type": self.mime_type,
            "arguments": self.arguments,
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }


@dataclass
class CapabilityStats:
    """Aggregated statistics about capabilities across all MCPs."""

    total_capabilities: int = 0
    total_tools: int = 0
    total_resources: int = 0
    total_prompts: int = 0
    total_servers: int = 0
    enabled_servers: int = 0
    by_security_level: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    by_server: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "total_capabilities": self.total_capabilities,
            "total_tools": self.total_tools,
            "total_resources": self.total_resources,
            "total_prompts": self.total_prompts,
            "total_servers": self.total_servers,
            "enabled_servers": self.enabled_servers,
            "by_security_level": self.by_security_level,
            "by_category": self.by_category,
            "by_server": self.by_server,
        }


@dataclass
class UnavailableCapability:
    """Represents a capability that exists but cannot be used, with the reason why."""

    capability: Capability
    reason: str
    can_be_enabled: bool = False
    how_to_enable: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "capability": self.capability.to_dict(),
            "reason": self.reason,
            "can_be_enabled": self.can_be_enabled,
            "how_to_enable": self.how_to_enable,
        }


class CapabilityRegistry:
    """Registry for capability-level introspection across all MCP servers.

    Provides:
    - Capability indexing and normalization
    - Search and filtering
    - Security level queries
    - Usage analytics
    - Unavailability explanations
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the registry with a database session.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self._session = session
        self._capability_cache: dict[str, Capability] | None = None
        self._cache_valid = False

    async def _build_cache(self) -> dict[str, Capability]:
        """Build the capability index from all registered servers.

        Returns:
            Dictionary mapping capability ID to Capability objects
        """
        if self._cache_valid and self._capability_cache is not None:
            return self._capability_cache

        result = await self._session.execute(select(MCPServer))
        servers = list(result.scalars().all())

        capabilities: dict[str, Capability] = {}

        for server in servers:
            # Extract tools
            if server.capabilities and "tools" in server.capabilities:
                for tool in server.capabilities["tools"]:
                    cap_id = f"{server.server_id}:tool:{tool.get('name', '')}"
                    security_level = self._get_security_level(
                        server.security_rules, tool.get("name", "")
                    )
                    category = self._infer_category(tool.get("name", ""))

                    capabilities[cap_id] = Capability(
                        id=cap_id,
                        name=tool.get("name", ""),
                        type=CapabilityType.TOOL,
                        server_id=server.server_id,
                        description=tool.get("description"),
                        category=category,
                        security_level=security_level,
                        server_name=server.name,
                        server_enabled=server.enabled,
                        input_schema=tool.get("input_schema") or tool.get("inputSchema"),
                    )

            # Extract resources
            if server.capabilities and "resources" in server.capabilities:
                for resource in server.capabilities["resources"]:
                    cap_id = f"{server.server_id}:resource:{resource.get('name', '')}"
                    capabilities[cap_id] = Capability(
                        id=cap_id,
                        name=resource.get("name", ""),
                        type=CapabilityType.RESOURCE,
                        server_id=server.server_id,
                        description=resource.get("description"),
                        category=self._infer_category(resource.get("name", "")),
                        security_level=SecurityLevel.ALLOWED,  # Resources are read-only
                        server_name=server.name,
                        server_enabled=server.enabled,
                        uri=resource.get("uri"),
                        mime_type=resource.get("mime_type") or resource.get("mimeType"),
                    )

            # Extract prompts
            if server.capabilities and "prompts" in server.capabilities:
                for prompt in server.capabilities["prompts"]:
                    cap_id = f"{server.server_id}:prompt:{prompt.get('name', '')}"
                    capabilities[cap_id] = Capability(
                        id=cap_id,
                        name=prompt.get("name", ""),
                        type=CapabilityType.PROMPT,
                        server_id=server.server_id,
                        description=prompt.get("description"),
                        category=SecurityCategory.UNKNOWN,
                        security_level=SecurityLevel.ALLOWED,  # Prompts are safe
                        server_name=server.name,
                        server_enabled=server.enabled,
                        arguments=prompt.get("arguments", []),
                    )

        self._capability_cache = capabilities
        self._cache_valid = True
        return capabilities

    def invalidate_cache(self) -> None:
        """Invalidate the capability cache (call after server changes)."""
        self._cache_valid = False
        self._capability_cache = None

    def _get_security_level(
        self, security_rules: dict | None, tool_name: str
    ) -> SecurityLevel:
        """Get security level for a tool from server's security rules.

        Args:
            security_rules: Server's security rules dict
            tool_name: Name of the tool

        Returns:
            SecurityLevel for the tool
        """
        if not security_rules:
            return SecurityLevel.REQUIRES_CONFIRM

        level_str = security_rules.get(tool_name)
        if not level_str:
            return SecurityLevel.REQUIRES_CONFIRM

        try:
            return SecurityLevel(level_str)
        except ValueError:
            return SecurityLevel.REQUIRES_CONFIRM

    def _infer_category(self, name: str) -> SecurityCategory:
        """Infer security category from capability name.

        Args:
            name: Capability name

        Returns:
            Inferred SecurityCategory
        """
        name_lower = name.lower()

        if any(kw in name_lower for kw in ["calendar", "event", "schedule"]):
            return SecurityCategory.CALENDAR
        if any(kw in name_lower for kw in ["document", "doc", "page", "text"]):
            return SecurityCategory.DOCUMENT
        if any(kw in name_lower for kw in ["file", "read", "write", "path"]):
            return SecurityCategory.FILE
        if any(kw in name_lower for kw in ["http", "api", "fetch", "network", "url"]):
            return SecurityCategory.NETWORK
        if any(kw in name_lower for kw in ["system", "exec", "shell", "command"]):
            return SecurityCategory.SYSTEM

        return SecurityCategory.UNKNOWN

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    async def get_all_capabilities(
        self, include_disabled: bool = False
    ) -> list[Capability]:
        """Get all capabilities from all servers.

        Args:
            include_disabled: If True, include capabilities from disabled servers

        Returns:
            List of all Capability objects
        """
        cache = await self._build_cache()
        capabilities = list(cache.values())

        if not include_disabled:
            capabilities = [c for c in capabilities if c.server_enabled]

        return capabilities

    async def get_capability(self, capability_id: str) -> Capability | None:
        """Get a specific capability by its ID.

        Args:
            capability_id: Unique capability ID (format: "{server_id}:{type}:{name}")

        Returns:
            Capability object or None if not found
        """
        cache = await self._build_cache()
        return cache.get(capability_id)

    async def find_capability_by_name(
        self, name: str, capability_type: CapabilityType | None = None
    ) -> list[Capability]:
        """Find capabilities by name (exact or partial match).

        Args:
            name: Capability name to search for
            capability_type: Optional type filter

        Returns:
            List of matching capabilities
        """
        cache = await self._build_cache()
        results = []

        name_lower = name.lower()
        for cap in cache.values():
            if name_lower in cap.name.lower():
                if capability_type is None or cap.type == capability_type:
                    results.append(cap)

        return results

    async def get_capabilities_by_server(self, server_id: str) -> list[Capability]:
        """Get all capabilities from a specific server.

        Args:
            server_id: Server identifier

        Returns:
            List of capabilities from that server
        """
        cache = await self._build_cache()
        return [c for c in cache.values() if c.server_id == server_id]

    async def get_capabilities_by_type(
        self, capability_type: CapabilityType
    ) -> list[Capability]:
        """Get capabilities by type (tool, resource, prompt).

        Args:
            capability_type: Type of capability to filter by

        Returns:
            List of capabilities of that type
        """
        cache = await self._build_cache()
        return [c for c in cache.values() if c.type == capability_type]

    async def get_capabilities_by_security_level(
        self, security_level: SecurityLevel
    ) -> list[Capability]:
        """Get capabilities by security level.

        Args:
            security_level: Security level to filter by

        Returns:
            List of capabilities with that security level
        """
        cache = await self._build_cache()
        return [c for c in cache.values() if c.security_level == security_level]

    async def get_capabilities_by_category(
        self, category: SecurityCategory
    ) -> list[Capability]:
        """Get capabilities by category.

        Args:
            category: Security category to filter by

        Returns:
            List of capabilities in that category
        """
        cache = await self._build_cache()
        return [c for c in cache.values() if c.category == category]

    async def search_capabilities(
        self,
        query: str | None = None,
        capability_type: CapabilityType | None = None,
        security_level: SecurityLevel | None = None,
        category: SecurityCategory | None = None,
        server_id: str | None = None,
        include_disabled: bool = False,
    ) -> list[Capability]:
        """Search capabilities with multiple filters.

        Args:
            query: Text search in name and description
            capability_type: Filter by type
            security_level: Filter by security level
            category: Filter by category
            server_id: Filter by server
            include_disabled: Include disabled servers

        Returns:
            List of matching capabilities
        """
        cache = await self._build_cache()
        results = list(cache.values())

        # Apply filters
        if not include_disabled:
            results = [c for c in results if c.server_enabled]

        if query:
            query_lower = query.lower()
            results = [
                c
                for c in results
                if query_lower in c.name.lower()
                or (c.description and query_lower in c.description.lower())
            ]

        if capability_type:
            results = [c for c in results if c.type == capability_type]

        if security_level:
            results = [c for c in results if c.security_level == security_level]

        if category:
            results = [c for c in results if c.category == category]

        if server_id:
            results = [c for c in results if c.server_id == server_id]

        return results

    # -------------------------------------------------------------------------
    # Introspection Methods
    # -------------------------------------------------------------------------

    async def find_server_for_tool(self, tool_name: str) -> str | None:
        """Find which server provides a specific tool.

        Args:
            tool_name: Name of the tool to find

        Returns:
            Server ID or None if not found
        """
        capabilities = await self.find_capability_by_name(
            tool_name, CapabilityType.TOOL
        )
        # Prefer exact match from enabled server
        for cap in capabilities:
            if cap.name == tool_name and cap.server_enabled:
                return cap.server_id
        # Fall back to partial match
        return capabilities[0].server_id if capabilities else None

    async def get_unavailable_capabilities(self) -> list[UnavailableCapability]:
        """Get capabilities that exist but cannot be used, with reasons.

        Returns:
            List of unavailable capabilities with explanations
        """
        cache = await self._build_cache()
        unavailable: list[UnavailableCapability] = []

        for cap in cache.values():
            # Check various reasons for unavailability
            if not cap.server_enabled:
                unavailable.append(
                    UnavailableCapability(
                        capability=cap,
                        reason=f"Server '{cap.server_name}' is disabled",
                        can_be_enabled=True,
                        how_to_enable=f"Enable the server via PUT /api/mcp/servers/{cap.server_id}",
                    )
                )
            elif cap.security_level == SecurityLevel.BLOCKED:
                unavailable.append(
                    UnavailableCapability(
                        capability=cap,
                        reason="This capability is blocked by security policy",
                        can_be_enabled=False,
                        how_to_enable=None,
                    )
                )

        return unavailable

    async def can_perform_action(
        self, action_description: str
    ) -> dict[str, Any]:
        """Check if an action can be performed and which capabilities could do it.

        This is a high-level introspection for agents to understand what's possible.

        Args:
            action_description: Natural language description of desired action

        Returns:
            Dict with 'possible', 'capabilities', and 'blocked_reason' if applicable
        """
        # Simple keyword-based matching (could be enhanced with embeddings)
        keywords = action_description.lower().split()

        cache = await self._build_cache()
        matches: list[Capability] = []
        blocked: list[Capability] = []

        for cap in cache.values():
            # Check if any keyword matches
            cap_text = f"{cap.name} {cap.description or ''}".lower()
            if any(kw in cap_text for kw in keywords):
                if cap.security_level == SecurityLevel.BLOCKED:
                    blocked.append(cap)
                elif cap.server_enabled:
                    matches.append(cap)

        if matches:
            return {
                "possible": True,
                "capabilities": [c.to_dict() for c in matches],
                "blocked_reason": None,
            }
        elif blocked:
            return {
                "possible": False,
                "capabilities": [],
                "blocked_reason": f"{len(blocked)} matching capabilities are blocked by security policy",
                "blocked_capabilities": [c.to_dict() for c in blocked],
            }
        else:
            return {
                "possible": False,
                "capabilities": [],
                "blocked_reason": "No capabilities found matching the requested action",
            }

    # -------------------------------------------------------------------------
    # Analytics Methods
    # -------------------------------------------------------------------------

    async def get_stats(self) -> CapabilityStats:
        """Get aggregated statistics about all capabilities.

        Returns:
            CapabilityStats object
        """
        cache = await self._build_cache()

        # Get server counts
        result = await self._session.execute(select(MCPServer))
        servers = list(result.scalars().all())

        stats = CapabilityStats(
            total_capabilities=len(cache),
            total_servers=len(servers),
            enabled_servers=len([s for s in servers if s.enabled]),
        )

        # Count by type
        for cap in cache.values():
            if cap.type == CapabilityType.TOOL:
                stats.total_tools += 1
            elif cap.type == CapabilityType.RESOURCE:
                stats.total_resources += 1
            elif cap.type == CapabilityType.PROMPT:
                stats.total_prompts += 1

            # Count by security level
            level = cap.security_level.value
            stats.by_security_level[level] = stats.by_security_level.get(level, 0) + 1

            # Count by category
            if cap.category:
                cat = cap.category.value
                stats.by_category[cat] = stats.by_category.get(cat, 0) + 1

            # Count by server
            stats.by_server[cap.server_id] = stats.by_server.get(cap.server_id, 0) + 1

        return stats

    async def get_usage_stats(
        self, server_id: str | None = None, tool_name: str | None = None
    ) -> dict[str, Any]:
        """Get usage statistics from execution logs.

        Args:
            server_id: Optional server filter
            tool_name: Optional tool filter

        Returns:
            Usage statistics including counts and timestamps
        """
        from sqlalchemy import case

        # Use case expression for counting successes (SQLite doesn't support boolean sum)
        success_count_expr = func.sum(
            case((MCPExecutionLog.success == True, 1), else_=0)  # noqa: E712
        ).label("success_count")

        query = select(
            MCPExecutionLog.server_id,
            MCPExecutionLog.tool_name,
            func.count(MCPExecutionLog.id).label("count"),
            func.max(MCPExecutionLog.executed_at).label("last_used"),
            success_count_expr,
        ).group_by(MCPExecutionLog.server_id, MCPExecutionLog.tool_name)

        if server_id:
            query = query.where(MCPExecutionLog.server_id == server_id)
        if tool_name:
            query = query.where(MCPExecutionLog.tool_name == tool_name)

        result = await self._session.execute(query)
        rows = result.fetchall()

        usage: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = f"{row.server_id}:{row.tool_name}"
            usage[key] = {
                "server_id": row.server_id,
                "tool_name": row.tool_name,
                "total_calls": row.count,
                "success_count": row.success_count or 0,
                "last_used": row.last_used.isoformat() if row.last_used else None,
            }

        return usage

    # -------------------------------------------------------------------------
    # Integration Status Methods
    # -------------------------------------------------------------------------

    async def get_integration_status(self) -> list[dict[str, Any]]:
        """Get status of all MCP integrations for user-facing display.

        Returns:
            List of integration status objects
        """
        result = await self._session.execute(select(MCPServer))
        servers = list(result.scalars().all())

        integrations: list[dict[str, Any]] = []

        for server in servers:
            # Count capabilities
            tools_count = len(server.capabilities.get("tools", []))
            resources_count = len(server.capabilities.get("resources", []))
            prompts_count = len(server.capabilities.get("prompts", []))

            # Count blocked tools
            blocked_count = sum(
                1
                for level in (server.security_rules or {}).values()
                if level == SecurityLevel.BLOCKED.value
            )

            integrations.append(
                {
                    "server_id": server.server_id,
                    "name": server.name,
                    "description": server.description,
                    "enabled": server.enabled,
                    "version": server.version,
                    "capabilities": {
                        "tools": tools_count,
                        "resources": resources_count,
                        "prompts": prompts_count,
                        "blocked": blocked_count,
                    },
                    "rate_limit": server.rate_limit,
                    "created_at": server.created_at.isoformat(),
                    "updated_at": server.updated_at.isoformat(),
                }
            )

        return integrations
