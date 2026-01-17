"""MCP Manifest Schema Definitions.

Defines Pydantic schemas for Model Context Protocol (MCP) server manifests,
following FR-019 requirements:
- Declare all capabilities upfront (tools, resources, prompts)
- Include version field (semver format)
- Block capabilities from the BLOCKED category
"""

from enum import Enum
from re import match
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SecurityCategory(str, Enum):
    """Security classification categories for MCP capabilities.

    Based on FR-019 capability classification table.
    """

    CALENDAR = "calendar"
    DOCUMENT = "document"
    FILE = "file"
    NETWORK = "network"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class SecurityLevel(str, Enum):
    """Security levels for MCP capabilities."""

    ALLOWED = "allowed"
    REQUIRES_CONFIRM = "requires_confirm"
    BLOCKED = "blocked"


class ToolInputSchema(BaseModel):
    """Input schema for an MCP tool.

    Describes the expected parameters for a tool using JSON Schema format.
    """

    type: str = Field(default="object", description="JSON Schema type")
    properties: dict[str, Any] = Field(default_factory=dict, description="Property definitions")
    required: list[str] = Field(default_factory=list, description="Required property names")


class ToolCapability(BaseModel):
    """Declaration of a single tool capability.

    An MCP tool represents a callable function with a name, description,
    and input schema.
    """

    name: str = Field(..., description="Tool name (must be unique within server)")
    description: str = Field(..., description="Human-readable tool description")
    input_schema: ToolInputSchema = Field(
        default_factory=ToolInputSchema,
        description="JSON Schema for tool input parameters",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Reject dangerous tool names.

        Args:
            v: The tool name to validate

        Returns:
            The validated tool name

        Raises:
            ValueError: If the name contains dangerous patterns
        """
        dangerous_patterns = [
            "exec",
            "eval",
            "system",
            "shell",
            "cmd",
            "drop",
            "format",
        ]
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in v_lower:
                raise ValueError(
                    f"Dangerous tool name detected: '{v}' (contains '{pattern}')"
                )
        return v


class ResourceCapability(BaseModel):
    """Declaration of a single resource capability.

    An MCP resource represents data that can be read or written,
    such as files, documents, or database records.
    """

    uri: str = Field(..., description="Resource URI or URI template")
    name: str = Field(..., description="Human-readable resource name")
    description: str | None = Field(None, description="Optional resource description")
    mime_type: str | None = Field(None, description="Optional MIME type")


class PromptCapability(BaseModel):
    """Declaration of a single prompt capability.

    An MCP prompt represents a reusable prompt template with
    optional arguments.
    """

    name: str = Field(..., description="Prompt name")
    description: str | None = Field(None, description="Optional prompt description")
    arguments: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional argument definitions for the prompt",
    )


class MCPCapabilities(BaseModel):
    """Capabilities declaration section of MCP manifest.

    Declares all available tools, resources, and prompts upfront
    as required by FR-019.
    """

    tools: list[ToolCapability] = Field(
        default_factory=list,
        description="List of available tools",
    )
    resources: list[ResourceCapability] = Field(
        default_factory=list,
        description="List of available resources",
    )
    prompts: list[PromptCapability] = Field(
        default_factory=list,
        description="List of available prompts",
    )


class MCPManifest(BaseModel):
    """Model Context Protocol (MCP) server manifest.

    The manifest declares an MCP server's identity, version, and capabilities.
    All capabilities must be declared upfront following FR-019 requirements.

    Attributes:
        protocol_version: MCP protocol version (e.g., "2024-11-05")
        name: Server name
        version: Server version in semver format (required by FR-019)
        description: Optional server description
        capabilities: Capability declarations (tools, resources, prompts)
        metadata: Optional additional metadata
    """

    model_config = {"populate_by_name": True}

    protocol_version: str = Field(
        ...,
        alias="protocolVersion",
        description="MCP protocol version identifier",
    )
    name: str = Field(..., description="Server name")
    version: str = Field(
        ...,
        description="Server version (semver format required by FR-019)",
    )
    description: str | None = Field(None, description="Optional server description")
    capabilities: MCPCapabilities = Field(
        default_factory=MCPCapabilities,
        description="Declared capabilities (tools, resources, prompts)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional additional metadata",
    )

    @field_validator("version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        """Validate that version follows semver format.

        Args:
            v: The version string to validate

        Returns:
            The validated version string

        Raises:
            ValueError: If the version is not valid semver
        """
        # Basic semver pattern: MAJOR.MINOR.PATCH with optional prerelease and build
        semver_pattern = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
        if not match(semver_pattern, v):
            raise ValueError(
                f"Invalid semver format: '{v}'. Expected MAJOR.MINOR.PATCH format."
            )
        return v

    @field_validator("protocol_version")
    @classmethod
    def validate_protocol_version(cls, v: str) -> str:
        """Validate protocol version is a non-empty string.

        Args:
            v: The protocol version to validate

        Returns:
            The validated protocol version

        Raises:
            ValueError: If the protocol version is empty
        """
        if not v or not isinstance(v, str):
            raise ValueError("protocolVersion must be a non-empty string")
        return v


# Blocked capabilities from FR-019 classification table
BLOCKED_CAPABILITIES: set[str] = {
    # Calendar: None blocked
    # Document
    "delete_external",
    # File
    "write",
    "execute",
    # Network
    "raw_socket",
    # System
    "shell_execute",
}


def classify_capability(
    capability_type: SecurityCategory, capability_name: str
) -> SecurityLevel:
    """Classify a capability by security level based on FR-019 table.

    Args:
        capability_type: The category of the capability
        capability_name: The specific capability name (e.g., "read", "write")

    Returns:
        The appropriate security level

    Examples:
        >>> classify_capability(SecurityCategory.CALENDAR, "read")
        <SecurityLevel.ALLOWED: 'allowed'>
        >>> classify_capability(SecurityCategory.CALENDAR, "write")
        <SecurityLevel.REQUIRES_CONFIRM: 'requires_confirm'>
        >>> classify_capability(SecurityCategory.FILE, "execute")
        <SecurityLevel.BLOCKED: 'blocked'>
    """
    # FR-019 Capability Classification Table
    classification: dict[SecurityCategory, dict[str, SecurityLevel]] = {
        SecurityCategory.CALENDAR: {
            "read": SecurityLevel.ALLOWED,
            "write": SecurityLevel.REQUIRES_CONFIRM,
            "delete": SecurityLevel.REQUIRES_CONFIRM,
        },
        SecurityCategory.DOCUMENT: {
            "read": SecurityLevel.ALLOWED,
            "write": SecurityLevel.REQUIRES_CONFIRM,
            "delete_external": SecurityLevel.BLOCKED,
        },
        SecurityCategory.FILE: {
            "read_scoped": SecurityLevel.REQUIRES_CONFIRM,
            "write": SecurityLevel.BLOCKED,
            "execute": SecurityLevel.BLOCKED,
        },
        SecurityCategory.NETWORK: {
            "internal_api": SecurityLevel.ALLOWED,
            "raw_socket": SecurityLevel.BLOCKED,
        },
        SecurityCategory.SYSTEM: {
            "shell_execute": SecurityLevel.BLOCKED,
        },
    }

    if capability_type not in classification:
        return SecurityLevel.REQUIRES_CONFIRM  # Unknown capabilities require confirmation

    level_map = classification[capability_type]
    return level_map.get(capability_name, SecurityLevel.REQUIRES_CONFIRM)


def is_blocked_capability(capability_name: str) -> bool:
    """Check if a capability is in the BLOCKED category per FR-019.

    Args:
        capability_name: The capability name to check

    Returns:
        True if the capability is blocked, False otherwise
    """
    return capability_name in BLOCKED_CAPABILITIES
