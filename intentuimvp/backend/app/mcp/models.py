"""SQLAlchemy models for MCP server configuration.

Defines persistent storage for registered MCP servers, their capabilities,
and security classifications.
"""

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SecurityLevel(str, Enum):
    """Security classification for MCP capabilities.

    ALLOWED: Safe to execute without confirmation
    REQUIRES_CONFIRM: Must show user confirmation dialog before execution
    BLOCKED: Never allowed to execute
    """

    ALLOWED = "allowed"
    REQUIRES_CONFIRM = "requires_confirm"
    BLOCKED = "blocked"


class MCPServer(Base):
    """MCP Server configuration model.

    Stores registered MCP servers, their connection details, capabilities,
    and security settings.
    """

    __tablename__ = "mcp_servers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Unique server identifier (e.g., "google-calendar", "filesystem")
    server_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    # Human-readable name
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Server description
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    # Connection configuration
    # For stdio: command to run and arguments
    # For SSE: URL endpoint
    transport_type: Mapped[str] = mapped_column(String, nullable=False, default="stdio")  # stdio or sse
    transport_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Server metadata from manifest
    version: Mapped[str | None] = mapped_column(String, nullable=True)
    capabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Security classifications per capability (tool name -> SecurityLevel)
    security_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Runtime settings
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Rate limit: max calls per minute
    rate_limit: Mapped[int] = mapped_column(default=60)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "server_id": self.server_id,
            "name": self.name,
            "description": self.description,
            "transport_type": self.transport_type,
            "transport_config": self._sanitize_transport_config(),
            "version": self.version,
            "capabilities": self.capabilities,
            "security_rules": self.security_rules,
            "enabled": self.enabled,
            "rate_limit": self.rate_limit,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def _sanitize_transport_config(self) -> dict:
        """Remove sensitive data from transport config for API responses."""
        config = dict(self.transport_config)
        # Remove sensitive keys like API keys, tokens, etc.
        sensitive_keys = {"api_key", "token", "password", "secret", "credentials"}
        for key in list(config.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                config[key] = "***REDACTED***"
        return config


class MCPExecutionLog(Base):
    """Log of MCP tool executions for monitoring and audit.

    Tracks all MCP tool executions for security monitoring and rate limiting.

    Per FR-019 runtime monitoring requirements:
    - Tool calls logged with timestamp, input hash, output size
    - Rate limiting: 100 tool calls per minute per MCP
    - Anomaly detection: alert if >10x normal call volume
    """

    __tablename__ = "mcp_execution_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Agent or user who initiated the call
    initiated_by: Mapped[str] = mapped_column(String, nullable=False)
    # Whether user confirmation was obtained
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Execution result
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    # Timestamp
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    # Runtime monitoring: SHA256 hash of tool arguments for deduplication/analysis
    input_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # Runtime monitoring: Approximate size of tool output in bytes
    output_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "server_id": self.server_id,
            "tool_name": self.tool_name,
            "initiated_by": self.initiated_by,
            "confirmed": self.confirmed,
            "success": self.success,
            "error_message": self.error_message,
            "executed_at": self.executed_at.isoformat(),
            "input_hash": self.input_hash,
            "output_size": self.output_size,
        }


def compute_input_hash(arguments: dict) -> str:
    """Compute SHA256 hash of tool arguments for runtime monitoring.

    Args:
        arguments: Tool arguments dictionary

    Returns:
        Hex-encoded SHA256 hash of the JSON-serialized arguments
    """
    # Sort keys for consistent hashing
    json_str = json.dumps(arguments, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()


def compute_output_size(result: Any) -> int:
    """Compute approximate size of tool output in bytes.

    Args:
        result: Tool result (can be dict, list, str, etc.)

    Returns:
        Approximate size in bytes
    """
    json_str = json.dumps(result, default=str, ensure_ascii=False)
    return len(json_str.encode())
