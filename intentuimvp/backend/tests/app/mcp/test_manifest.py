"""Tests for MCP Manifest Schema.

Tests MCP manifest schema definitions including:
- Semver validation
- Tool capability validation
- Security classification
- FR-019 requirement compliance
"""

import pytest

from app.mcp.manifest import (
    BLOCKED_CAPABILITIES,
    MCPCapabilities,
    MCPManifest,
    PromptCapability,
    ResourceCapability,
    SecurityCategory,
    SecurityLevel,
    ToolCapability,
    ToolInputSchema,
    classify_capability,
    is_blocked_capability,
)


def _make_manifest(**kwargs: object) -> MCPManifest:
    """Helper to create MCPManifest with protocolVersion."""
    return MCPManifest.model_validate({"protocolVersion": "2024-11-05", **kwargs})


class TestToolInputSchema:
    """Tests for ToolInputSchema."""

    def test_default_values(self) -> None:
        """Test default input schema values."""
        schema = ToolInputSchema()
        assert schema.type == "object"
        assert schema.properties == {}
        assert schema.required == []

    def test_custom_properties(self) -> None:
        """Test input schema with custom properties."""
        schema = ToolInputSchema(
            properties={"path": {"type": "string"}},
            required=["path"],
        )
        assert schema.properties == {"path": {"type": "string"}}
        assert schema.required == ["path"]


class TestToolCapability:
    """Tests for ToolCapability."""

    def test_valid_tool(self) -> None:
        """Test creating a valid tool capability."""
        tool = ToolCapability(
            name="read_file",
            description="Read a file from disk",
        )
        assert tool.name == "read_file"
        assert tool.description == "Read a file from disk"
        assert tool.input_schema.type == "object"

    def test_reject_dangerous_name_shell(self) -> None:
        """Test rejection of tool with 'shell' in name."""
        with pytest.raises(ValueError, match="Dangerous tool name"):
            ToolCapability(
                name="shell_execute",
                description="Execute shell commands",
            )

    def test_reject_dangerous_name_exec(self) -> None:
        """Test rejection of tool with 'exec' in name."""
        with pytest.raises(ValueError, match="Dangerous tool name"):
            ToolCapability(
                name="execute_command",
                description="Execute a command",
            )

    def test_reject_dangerous_name_delete(self) -> None:
        """Test rejection of tool with 'delete' in name."""
        with pytest.raises(ValueError, match="Dangerous tool name"):
            ToolCapability(
                name="delete_all_files",
                description="Delete files",
            )

    def test_reject_dangerous_name_eval(self) -> None:
        """Test rejection of tool with 'eval' in name."""
        with pytest.raises(ValueError, match="Dangerous tool name"):
            ToolCapability(
                name="evaluate_code",
                description="Evaluate code",
            )


class TestResourceCapability:
    """Tests for ResourceCapability."""

    def test_minimal_resource(self) -> None:
        """Test creating a minimal resource capability."""
        resource = ResourceCapability(
            uri="file:///path/to/file.txt",
            name="file.txt",
            description=None,
            mime_type=None,
        )
        assert resource.uri == "file:///path/to/file.txt"
        assert resource.name == "file.txt"
        assert resource.description is None
        assert resource.mime_type is None

    def test_full_resource(self) -> None:
        """Test creating a full resource capability with all fields."""
        resource = ResourceCapability(
            uri="file:///path/to/file.txt",
            name="file.txt",
            description="A text file",
            mime_type="text/plain",
        )
        assert resource.uri == "file:///path/to/file.txt"
        assert resource.name == "file.txt"
        assert resource.description == "A text file"
        assert resource.mime_type == "text/plain"


class TestPromptCapability:
    """Tests for PromptCapability."""

    def test_minimal_prompt(self) -> None:
        """Test creating a minimal prompt capability."""
        prompt = PromptCapability(name="summarize", description=None)
        assert prompt.name == "summarize"
        assert prompt.description is None
        assert prompt.arguments == []

    def test_full_prompt(self) -> None:
        """Test creating a full prompt capability."""
        prompt = PromptCapability(
            name="summarize",
            description="Summarize text",
            arguments=[
                {"name": "text", "description": "Text to summarize", "required": True}
            ],
        )
        assert prompt.name == "summarize"
        assert prompt.description == "Summarize text"
        assert len(prompt.arguments) == 1


class TestMCPCapabilities:
    """Tests for MCPCapabilities."""

    def test_empty_capabilities(self) -> None:
        """Test creating empty capabilities."""
        caps = MCPCapabilities()
        assert caps.tools == []
        assert caps.resources == []
        assert caps.prompts == []

    def test_with_tools(self) -> None:
        """Test capabilities with tools."""
        caps = MCPCapabilities(
            tools=[
                ToolCapability(name="read", description="Read data"),
                ToolCapability(name="write", description="Write data"),
            ]
        )
        assert len(caps.tools) == 2
        assert caps.tools[0].name == "read"
        assert caps.tools[1].name == "write"

    def test_with_all_types(self) -> None:
        """Test capabilities with all types."""
        caps = MCPCapabilities(
            tools=[ToolCapability(name="read", description="Read data")],
            resources=[ResourceCapability(uri="file://test", name="test", description=None, mime_type=None)],
            prompts=[PromptCapability(name="help", description="Get help")],
        )
        assert len(caps.tools) == 1
        assert len(caps.resources) == 1
        assert len(caps.prompts) == 1


class TestMCPManifest:
    """Tests for MCPManifest."""

    def test_minimal_manifest(self) -> None:
        """Test creating a minimal valid manifest."""
        manifest = _make_manifest(name="test-server", version="1.0.0")
        assert manifest.protocol_version == "2024-11-05"
        assert manifest.name == "test-server"
        assert manifest.version == "1.0.0"
        assert manifest.description is None
        assert isinstance(manifest.capabilities, MCPCapabilities)
        assert manifest.metadata == {}

    def test_full_manifest(self) -> None:
        """Test creating a full manifest with all fields."""
        manifest = _make_manifest(
            name="test-server",
            version="1.0.0",
            description="A test MCP server",
            capabilities=MCPCapabilities(
                tools=[ToolCapability(name="read", description="Read data")]
            ),
            metadata={"author": "test"},
        )
        assert manifest.description == "A test MCP server"
        assert len(manifest.capabilities.tools) == 1
        assert manifest.metadata == {"author": "test"}

    def test_valid_semver_simple(self) -> None:
        """Test valid simple semver versions."""
        valid_versions = ["1.0.0", "0.1.0", "10.20.30"]
        for version in valid_versions:
            manifest = _make_manifest(name="test", version=version)
            assert manifest.version == version

    def test_valid_semver_with_prerelease(self) -> None:
        """Test valid semver with prerelease."""
        manifest = _make_manifest(name="test", version="1.0.0-alpha")
        assert manifest.version == "1.0.0-alpha"

    def test_valid_semver_with_build(self) -> None:
        """Test valid semver with build metadata."""
        manifest = _make_manifest(name="test", version="1.0.0+001")
        assert manifest.version == "1.0.0+001"

    def test_invalid_semver_missing_minor(self) -> None:
        """Test rejection of invalid semver (missing minor)."""
        with pytest.raises(ValueError, match="Invalid semver"):
            _make_manifest(name="test", version="1.0")

    def test_invalid_semver_missing_patch(self) -> None:
        """Test rejection of invalid semver (missing patch)."""
        with pytest.raises(ValueError, match="Invalid semver"):
            _make_manifest(name="test", version="1")

    def test_invalid_semver_text(self) -> None:
        """Test rejection of non-numeric version."""
        with pytest.raises(ValueError, match="Invalid semver"):
            _make_manifest(name="test", version="v1.0.0")

    def test_empty_protocol_version(self) -> None:
        """Test rejection of empty protocol version."""
        with pytest.raises(ValueError, match="protocolVersion must be a non-empty"):
            MCPManifest.model_validate(
                {"protocolVersion": "", "name": "test", "version": "1.0.0"}
            )

    def test_from_dict(self) -> None:
        """Test creating manifest from dictionary."""
        data = {
            "protocolVersion": "2024-11-05",
            "name": "test-server",
            "version": "1.0.0",
            "description": "Test",
            "capabilities": {
                "tools": [{"name": "read", "description": "Read data"}],
                "resources": [],
                "prompts": [],
            },
        }
        manifest = MCPManifest.model_validate(data)
        assert manifest.name == "test-server"
        assert manifest.version == "1.0.0"
        assert len(manifest.capabilities.tools) == 1


class TestSecurityClassification:
    """Tests for security classification functions."""

    def test_calendar_allowed(self) -> None:
        """Test calendar read is allowed."""
        level = classify_capability(SecurityCategory.CALENDAR, "read")
        assert level == SecurityLevel.ALLOWED

    def test_calendar_write_requires_confirm(self) -> None:
        """Test calendar write requires confirmation."""
        level = classify_capability(SecurityCategory.CALENDAR, "write")
        assert level == SecurityLevel.REQUIRES_CONFIRM

    def test_calendar_delete_requires_confirm(self) -> None:
        """Test calendar delete requires confirmation."""
        level = classify_capability(SecurityCategory.CALENDAR, "delete")
        assert level == SecurityLevel.REQUIRES_CONFIRM

    def test_document_allowed(self) -> None:
        """Test document read is allowed."""
        level = classify_capability(SecurityCategory.DOCUMENT, "read")
        assert level == SecurityLevel.ALLOWED

    def test_document_write_requires_confirm(self) -> None:
        """Test document write requires confirmation."""
        level = classify_capability(SecurityCategory.DOCUMENT, "write")
        assert level == SecurityLevel.REQUIRES_CONFIRM

    def test_document_delete_external_blocked(self) -> None:
        """Test document delete_external is blocked."""
        level = classify_capability(SecurityCategory.DOCUMENT, "delete_external")
        assert level == SecurityLevel.BLOCKED

    def test_file_read_scoped_requires_confirm(self) -> None:
        """Test file read_scoped requires confirmation."""
        level = classify_capability(SecurityCategory.FILE, "read_scoped")
        assert level == SecurityLevel.REQUIRES_CONFIRM

    def test_file_write_blocked(self) -> None:
        """Test file write is blocked."""
        level = classify_capability(SecurityCategory.FILE, "write")
        assert level == SecurityLevel.BLOCKED

    def test_file_execute_blocked(self) -> None:
        """Test file execute is blocked."""
        level = classify_capability(SecurityCategory.FILE, "execute")
        assert level == SecurityLevel.BLOCKED

    def test_network_internal_api_allowed(self) -> None:
        """Test network internal_api is allowed."""
        level = classify_capability(SecurityCategory.NETWORK, "internal_api")
        assert level == SecurityLevel.ALLOWED

    def test_network_raw_socket_blocked(self) -> None:
        """Test network raw_socket is blocked."""
        level = classify_capability(SecurityCategory.NETWORK, "raw_socket")
        assert level == SecurityLevel.BLOCKED

    def test_system_shell_execute_blocked(self) -> None:
        """Test system shell_execute is blocked."""
        level = classify_capability(SecurityCategory.SYSTEM, "shell_execute")
        assert level == SecurityLevel.BLOCKED

    def test_unknown_capability_requires_confirm(self) -> None:
        """Test unknown capabilities require confirmation."""
        level = classify_capability(SecurityCategory.UNKNOWN, "unknown_operation")
        assert level == SecurityLevel.REQUIRES_CONFIRM

    def test_unknown_in_category_requires_confirm(self) -> None:
        """Test unknown operations in known categories require confirmation."""
        level = classify_capability(SecurityCategory.CALENDAR, "unknown_calendar_op")
        assert level == SecurityLevel.REQUIRES_CONFIRM


class TestBlockedCapabilities:
    """Tests for blocked capabilities detection."""

    def test_blocked_capabilities_set(self) -> None:
        """Test that blocked capabilities match FR-019 table."""
        expected = {
            "delete_external",  # Document
            "write",  # File
            "execute",  # File
            "raw_socket",  # Network
            "shell_execute",  # System
        }
        assert BLOCKED_CAPABILITIES == expected

    def test_is_blocked_capability_true(self) -> None:
        """Test detecting blocked capabilities."""
        blocked_caps = ["delete_external", "write", "execute", "raw_socket", "shell_execute"]
        for cap in blocked_caps:
            assert is_blocked_capability(cap), f"{cap} should be blocked"

    def test_is_blocked_capability_false(self) -> None:
        """Test non-blocked capabilities."""
        safe_caps = ["read", "read_scoped", "internal_api", "write_calendar"]
        for cap in safe_caps:
            assert not is_blocked_capability(cap), f"{cap} should not be blocked"


class TestManifestFR019Compliance:
    """Tests for FR-019 manifest compliance."""

    def test_manifest_declares_capabilities(self) -> None:
        """Test that manifest can declare all capabilities upfront."""
        manifest = _make_manifest(
            name="test-server",
            version="1.0.0",
            capabilities=MCPCapabilities(
                tools=[
                    ToolCapability(name="read", description="Read data"),
                    ToolCapability(name="write", description="Write data"),
                ],
                resources=[
                    ResourceCapability(uri="file://test", name="test", description=None, mime_type=None)
                ],
                prompts=[
                    PromptCapability(name="help", description="Get help")
                ],
            ),
        )
        assert len(manifest.capabilities.tools) == 2
        assert len(manifest.capabilities.resources) == 1
        assert len(manifest.capabilities.prompts) == 1

    def test_manifest_has_semver_version(self) -> None:
        """Test that manifest requires semver version."""
        # Valid semver should work
        manifest = _make_manifest(name="test", version="1.0.0")
        assert manifest.version == "1.0.0"

        # Invalid semver should fail
        with pytest.raises(ValueError, match="Invalid semver"):
            _make_manifest(name="test", version="not-a-version")

    def test_manifest_blocks_dangerous_tools(self) -> None:
        """Test that manifest rejects dangerous tool names."""
        dangerous_names = ["shell", "execute", "eval", "delete_all", "format_disk"]
        for name in dangerous_names:
            with pytest.raises(ValueError, match="Dangerous tool name"):
                ToolCapability(name=name, description="Test tool")
