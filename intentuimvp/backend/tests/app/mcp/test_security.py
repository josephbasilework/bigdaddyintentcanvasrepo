"""Tests for MCP Security Validation.

Tests MCPSecurityValidator including:
- Manifest validation
- Permission checking (FR-019 classification integration)
- Rate limiting
- Anomaly detection
- Execution logging
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.mcp.models  # noqa: F401 - Side-effect import to register models
from app.database import Base
from app.mcp.manifest import (
    BLOCKED_CAPABILITIES,
    SecurityCategory,
    classify_capability,
    is_blocked_capability,
)
from app.mcp.manifest import (
    SecurityLevel as ManifestSecurityLevel,
)
from app.mcp.models import MCPExecutionLog, MCPServer, SecurityLevel
from app.mcp.security import MCPSecurityValidator, SecurityDecision

# In-memory async test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async test engine with in-memory database."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for tests."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture
def validator(db_session: AsyncSession) -> MCPSecurityValidator:
    """Provide a security validator instance."""
    return MCPSecurityValidator(db_session)


@pytest_asyncio.fixture
async def test_server(db_session: AsyncSession) -> MCPServer:
    """Create a test MCP server in the database."""
    server = MCPServer(
        server_id="test-server",
        name="Test MCP Server",
        description="A test server for security validation",
        transport_type="stdio",
        transport_config={"command": ["echo"], "args": []},
        version="1.0.0",
        capabilities={
            "tools": [
                {"name": "read_data", "description": "Read data"},
                {"name": "write_data", "description": "Write data"},
            ]
        },
        security_rules={
            "read_data": "allowed",
            "write_data": "requires_confirm",
        },
        enabled=True,
        rate_limit=100,
    )
    db_session.add(server)
    await db_session.flush()
    return server


class TestSecurityDecision:
    """Tests for SecurityDecision dataclass."""

    def test_allowed_decision(self) -> None:
        """Test creating an allowed security decision."""
        decision = SecurityDecision(
            allowed=True,
            requires_confirmation=False,
            reason="Tool is safe",
            security_level=SecurityLevel.ALLOWED,
        )
        assert decision.allowed is True
        assert decision.requires_confirmation is False
        assert decision.reason == "Tool is safe"
        assert decision.security_level == SecurityLevel.ALLOWED

    def test_blocked_decision(self) -> None:
        """Test creating a blocked security decision."""
        decision = SecurityDecision(
            allowed=False,
            requires_confirmation=False,
            reason="Tool is blocked",
            security_level=SecurityLevel.BLOCKED,
        )
        assert decision.allowed is False
        assert decision.requires_confirmation is False
        assert decision.security_level == SecurityLevel.BLOCKED

    def test_requires_confirm_decision(self) -> None:
        """Test creating a decision that requires confirmation."""
        decision = SecurityDecision(
            allowed=True,
            requires_confirmation=True,
            reason="Tool requires confirmation",
            security_level=SecurityLevel.REQUIRES_CONFIRM,
        )
        assert decision.allowed is True
        assert decision.requires_confirmation is True
        assert decision.security_level == SecurityLevel.REQUIRES_CONFIRM


@pytest.mark.asyncio
class TestValidateManifest:
    """Tests for manifest validation."""

    async def test_valid_minimal_manifest(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test validation of a minimal valid manifest."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["echo"]}
        )
        assert is_valid is True
        assert error is None

    async def test_valid_manifest_with_tools(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test validation of manifest with tools."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": [
                    {"name": "read_file", "description": "Read a file"},
                    {"name": "write_file", "description": "Write a file"},
                ]
            },
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["python", "server.py"]}
        )
        assert is_valid is True
        assert error is None

    async def test_missing_protocol_version(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test rejection of manifest without protocolVersion."""
        manifest: dict = {
            "capabilities": {},
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["echo"]}
        )
        assert is_valid is False
        assert error is not None and "protocolVersion" in error

    async def test_missing_capabilities(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test rejection of manifest without capabilities."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["echo"]}
        )
        assert is_valid is False
        assert error is not None and "capabilities" in error

    async def test_invalid_protocol_version(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test rejection of empty protocol version."""
        manifest: dict = {
            "protocolVersion": "",
            "capabilities": {},
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["echo"]}
        )
        assert is_valid is False
        assert error is not None and (
            "protocolversion" in error.lower() or "protocol" in error.lower()
        )

    async def test_capabilities_not_dict(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test rejection of non-dict capabilities."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
            "capabilities": [],
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["echo"]}
        )
        assert is_valid is False
        assert error is not None and "dictionary" in error.lower()

    async def test_tools_not_list(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test rejection of non-list tools."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["echo"]}
        )
        assert is_valid is False
        assert error is not None and "list" in error.lower()

    async def test_tool_missing_name(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test rejection of tool without name."""
        manifest = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": [
                    {"description": "A tool without a name"},
                ]
            },
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["echo"]}
        )
        assert is_valid is False
        assert error is not None and "name" in error.lower()

    async def test_dangerous_tool_name_exec(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test rejection of tool with 'exec' in name."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": [
                    {"name": "execute_command", "description": "Execute commands"},
                ]
            },
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["echo"]}
        )
        assert is_valid is False
        assert error is not None and "dangerous" in error.lower()
        assert error is not None and "exec" in error.lower()

    async def test_dangerous_tool_name_shell(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test rejection of tool with 'shell' in name."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": [
                    {"name": "shell_execute", "description": "Execute shell"},
                ]
            },
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["echo"]}
        )
        assert is_valid is False
        assert error is not None and "dangerous" in error.lower()
        assert error is not None and "shell" in error.lower()

    async def test_dangerous_tool_name_delete(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test rejection of tool with 'delete' in name."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": [
                    {"name": "delete_all", "description": "Delete everything"},
                ]
            },
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"command": ["echo"]}
        )
        assert is_valid is False
        assert error is not None and "dangerous" in error.lower()
        assert error is not None and "delete" in error.lower()

    async def test_stdio_transport_requires_command(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test stdio transport requires command in config."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "stdio", {"args": []}
        )
        assert is_valid is False
        assert error is not None and "command" in error.lower()

    async def test_sse_transport_requires_url(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test SSE transport requires url in config."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "sse", {"port": 8080}
        )
        assert is_valid is False
        assert error is not None and "url" in error.lower()

    async def test_unknown_transport_type(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test rejection of unknown transport type."""
        manifest: dict = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
        }
        is_valid, error = await validator.validate_manifest(
            manifest, "unknown", {}
        )
        assert is_valid is False
        assert error is not None and "unknown" in error.lower()


@pytest.mark.asyncio
class TestCheckPermission:
    """Tests for permission checking."""

    async def test_blocked_capability_f019(
        self, validator: MCPSecurityValidator, test_server: MCPServer
    ) -> None:
        """Test that FR-019 blocked capabilities are rejected."""
        # Test all blocked capabilities from FR-019
        for blocked_cap in BLOCKED_CAPABILITIES:
            decision = await validator.check_permission(
                test_server.server_id, blocked_cap, "test_user"
            )
            assert decision.allowed is False
            assert decision.security_level == SecurityLevel.BLOCKED
            assert "FR-019" in decision.reason

    async def test_blocked_capability_delete_external(
        self, validator: MCPSecurityValidator, test_server: MCPServer
    ) -> None:
        """Test that delete_external capability is blocked."""
        decision = await validator.check_permission(
            test_server.server_id, "delete_external", "test_user"
        )
        assert decision.allowed is False
        assert decision.security_level == SecurityLevel.BLOCKED

    async def test_blocked_capability_file_write(
        self, validator: MCPSecurityValidator, test_server: MCPServer
    ) -> None:
        """Test that file write capability is blocked."""
        decision = await validator.check_permission(
            test_server.server_id, "write", "test_user"
        )
        assert decision.allowed is False
        assert decision.security_level == SecurityLevel.BLOCKED

    async def test_blocked_capability_file_execute(
        self, validator: MCPSecurityValidator, test_server: MCPServer
    ) -> None:
        """Test that file execute capability is blocked."""
        decision = await validator.check_permission(
            test_server.server_id, "execute", "test_user"
        )
        assert decision.allowed is False
        assert decision.security_level == SecurityLevel.BLOCKED

    async def test_blocked_capability_raw_socket(
        self, validator: MCPSecurityValidator, test_server: MCPServer
    ) -> None:
        """Test that raw_socket capability is blocked."""
        decision = await validator.check_permission(
            test_server.server_id, "raw_socket", "test_user"
        )
        assert decision.allowed is False
        assert decision.security_level == SecurityLevel.BLOCKED

    async def test_blocked_capability_shell_execute(
        self, validator: MCPSecurityValidator, test_server: MCPServer
    ) -> None:
        """Test that shell_execute capability is blocked."""
        decision = await validator.check_permission(
            test_server.server_id, "shell_execute", "test_user"
        )
        assert decision.allowed is False
        assert decision.security_level == SecurityLevel.BLOCKED

    async def test_server_not_found(
        self, validator: MCPSecurityValidator
    ) -> None:
        """Test permission check for non-existent server."""
        decision = await validator.check_permission(
            "nonexistent-server", "safe_tool", "test_user"
        )
        assert decision.allowed is False
        assert "not found or disabled" in decision.reason

    async def test_server_disabled(
        self, db_session: AsyncSession, validator: MCPSecurityValidator
    ) -> None:
        """Test permission check for disabled server."""
        server = MCPServer(
            server_id="disabled-server",
            name="Disabled Server",
            transport_type="stdio",
            transport_config={"command": ["echo"]},
            enabled=False,  # Disabled
            security_rules={},
        )
        db_session.add(server)
        await db_session.flush()

        decision = await validator.check_permission(
            "disabled-server", "safe_tool", "test_user"
        )
        assert decision.allowed is False
        assert "not found or disabled" in decision.reason

    async def test_allowed_tool(
        self, validator: MCPSecurityValidator, test_server: MCPServer
    ) -> None:
        """Test allowed tool execution."""
        decision = await validator.check_permission(
            test_server.server_id, "read_data", "test_user"
        )
        assert decision.allowed is True
        assert decision.requires_confirmation is False
        assert decision.security_level == SecurityLevel.ALLOWED

    async def test_requires_confirm_tool(
        self, validator: MCPSecurityValidator, test_server: MCPServer
    ) -> None:
        """Test tool that requires confirmation."""
        decision = await validator.check_permission(
            test_server.server_id, "write_data", "test_user"
        )
        assert decision.allowed is True
        assert decision.requires_confirmation is True
        assert decision.security_level == SecurityLevel.REQUIRES_CONFIRM
        assert "requires user confirmation" in decision.reason

    async def test_unknown_capability_defaults_to_confirm(
        self, db_session: AsyncSession, validator: MCPSecurityValidator
    ) -> None:
        """Test unknown capabilities default to REQUIRES_CONFIRM."""
        server = MCPServer(
            server_id="unknown-cap-server",
            name="Unknown Capability Server",
            transport_type="stdio",
            transport_config={"command": ["echo"]},
            enabled=True,
            security_rules={},  # No rules defined
        )
        db_session.add(server)
        await db_session.flush()

        decision = await validator.check_permission(
            "unknown-cap-server", "unknown_tool", "test_user"
        )
        # Unknown tools require confirmation by default
        assert decision.allowed is True
        assert decision.requires_confirmation is True


@pytest.mark.asyncio
class TestRateLimiting:
    """Tests for rate limiting."""

    async def test_rate_limit_within_bounds(
        self, db_session: AsyncSession, validator: MCPSecurityValidator
    ) -> None:
        """Test calls within rate limit are allowed."""
        server = MCPServer(
            server_id="rate-limit-server",
            name="Rate Limit Server",
            transport_type="stdio",
            transport_config={"command": ["echo"]},
            enabled=True,
            security_rules={"safe_tool": "allowed"},
            rate_limit=5,  # Low limit for testing
        )
        db_session.add(server)
        await db_session.flush()

        # Make 5 calls (at the limit)
        for _ in range(5):
            decision = await validator.check_permission(
                "rate-limit-server", "safe_tool", "test_user"
            )
            assert decision.allowed is True, "Should be allowed within rate limit"

    async def test_rate_limit_exceeded(
        self, db_session: AsyncSession, validator: MCPSecurityValidator
    ) -> None:
        """Test calls exceeding rate limit are blocked."""
        server = MCPServer(
            server_id="rate-limit-server-2",
            name="Rate Limit Server 2",
            transport_type="stdio",
            transport_config={"command": ["echo"]},
            enabled=True,
            security_rules={"safe_tool": "allowed"},
            rate_limit=3,  # Very low limit
        )
        db_session.add(server)
        await db_session.flush()

        # Make 4 calls (exceeds limit of 3)
        for i in range(3):
            decision = await validator.check_permission(
                "rate-limit-server-2", "safe_tool", "test_user"
            )
            assert decision.allowed is True, f"Call {i+1} should be allowed"

        # Fourth call should be blocked
        decision = await validator.check_permission(
            "rate-limit-server-2", "safe_tool", "test_user"
        )
        assert decision.allowed is False
        assert "Rate limit exceeded" in decision.reason


@pytest.mark.asyncio
class TestExecutionLogging:
    """Tests for execution logging."""

    async def test_log_execution(
        self, db_session: AsyncSession, validator: MCPSecurityValidator
    ) -> None:
        """Test logging an execution."""
        log = await validator.log_execution(
            server_id="test-server",
            tool_name="test_tool",
            initiated_by="test_user",
            confirmed=True,
            success=True,
        )

        assert log.server_id == "test-server"
        assert log.tool_name == "test_tool"
        assert log.initiated_by == "test_user"
        assert log.confirmed is True
        assert log.success is True
        assert log.error_message is None

    async def test_log_execution_failure(
        self, db_session: AsyncSession, validator: MCPSecurityValidator
    ) -> None:
        """Test logging a failed execution."""
        log = await validator.log_execution(
            server_id="test-server",
            tool_name="test_tool",
            initiated_by="test_user",
            confirmed=False,
            success=False,
            error_message="Connection failed",
        )

        assert log.success is False
        assert log.error_message == "Connection failed"

    async def test_log_persists_to_database(
        self, db_session: AsyncSession, validator: MCPSecurityValidator
    ) -> None:
        """Test that logs are persisted to the database."""
        await validator.log_execution(
            server_id="persist-server",
            tool_name="persist_tool",
            initiated_by="persist_user",
            confirmed=True,
            success=True,
        )
        await db_session.flush()

        # Query the database
        result = await db_session.execute(
            select(MCPExecutionLog).where(
                MCPExecutionLog.server_id == "persist-server"
            )
        )
        logs = list(result.scalars().all())

        assert len(logs) == 1
        assert logs[0].tool_name == "persist_tool"
        assert logs[0].initiated_by == "persist_user"


@pytest.mark.asyncio
class TestAnomalyDetection:
    """Tests for anomaly detection."""

    async def test_no_anomalies_with_no_logs(
        self, db_session: AsyncSession, validator: MCPSecurityValidator
    ) -> None:
        """Test anomaly detection with no logs."""
        anomalies = await validator.detect_anomalies()
        assert anomalies == []

    async def test_high_failure_rate_detection(
        self, db_session: AsyncSession, validator: MCPSecurityValidator
    ) -> None:
        """Test detection of high failure rates."""
        # Create logs with high failure rate
        for i in range(10):
            log = MCPExecutionLog(
                server_id="anomaly-server",
                tool_name="failing_tool",
                initiated_by="test_user",
                confirmed=False,
                success=(i < 3),  # Only first 3 succeed
                error_message="Failed" if i >= 3 else None,
                executed_at=datetime.utcnow(),
            )
            db_session.add(log)
        await db_session.flush()

        anomalies = await validator.detect_anomalies(
            server_id="anomaly-server", minutes=5
        )

        assert len(anomalies) > 0
        assert any(a["type"] == "high_failure_rate" for a in anomalies)

    async def test_low_volume_tools_skipped(
        self, db_session: AsyncSession, validator: MCPSecurityValidator
    ) -> None:
        """Test that low-volume tools are skipped in anomaly detection."""
        # Create only 4 logs (below threshold of 5)
        for _ in range(4):
            log = MCPExecutionLog(
                server_id="low-volume-server",
                tool_name="low_volume_tool",
                initiated_by="test_user",
                confirmed=False,
                success=False,
                error_message="Failed",
                executed_at=datetime.utcnow(),
            )
            db_session.add(log)
        await db_session.flush()

        anomalies = await validator.detect_anomalies(
            server_id="low-volume-server", minutes=5
        )

        # Should not report anomalies for low-volume tools
        assert len(anomalies) == 0


class TestFR019Compliance:
    """Tests for FR-019 compliance in security validation."""

    def test_blocked_capabilities_set_matches_f019(self) -> None:
        """Test that BLOCKED_CAPABILITIES matches FR-019 table."""
        expected_blocked = {
            "delete_external",  # Document
            "write",  # File
            "execute",  # File
            "raw_socket",  # Network
            "shell_execute",  # System
        }
        assert BLOCKED_CAPABILITIES == expected_blocked

    def test_is_blocked_capability_for_all_blocked(self) -> None:
        """Test is_blocked_capability for all blocked capabilities."""
        for cap in BLOCKED_CAPABILITIES:
            assert is_blocked_capability(cap), f"{cap} should be blocked"

    def test_is_blocked_capability_false_for_safe(self) -> None:
        """Test is_blocked_capability returns False for safe capabilities."""
        safe_caps = ["read", "read_scoped", "internal_api", "write_calendar"]
        for cap in safe_caps:
            assert not is_blocked_capability(cap), f"{cap} should not be blocked"

    def test_classify_capability_calendar(self) -> None:
        """Test calendar capability classification."""
        assert classify_capability(
            SecurityCategory.CALENDAR, "read"
        ) == ManifestSecurityLevel.ALLOWED
        assert classify_capability(
            SecurityCategory.CALENDAR, "write"
        ) == ManifestSecurityLevel.REQUIRES_CONFIRM
        assert classify_capability(
            SecurityCategory.CALENDAR, "delete"
        ) == ManifestSecurityLevel.REQUIRES_CONFIRM

    def test_classify_capability_document(self) -> None:
        """Test document capability classification."""
        assert classify_capability(
            SecurityCategory.DOCUMENT, "read"
        ) == ManifestSecurityLevel.ALLOWED
        assert classify_capability(
            SecurityCategory.DOCUMENT, "write"
        ) == ManifestSecurityLevel.REQUIRES_CONFIRM
        assert classify_capability(
            SecurityCategory.DOCUMENT, "delete_external"
        ) == ManifestSecurityLevel.BLOCKED

    def test_classify_capability_file(self) -> None:
        """Test file capability classification."""
        assert classify_capability(
            SecurityCategory.FILE, "read_scoped"
        ) == ManifestSecurityLevel.REQUIRES_CONFIRM
        assert classify_capability(
            SecurityCategory.FILE, "write"
        ) == ManifestSecurityLevel.BLOCKED
        assert classify_capability(
            SecurityCategory.FILE, "execute"
        ) == ManifestSecurityLevel.BLOCKED

    def test_classify_capability_network(self) -> None:
        """Test network capability classification."""
        assert classify_capability(
            SecurityCategory.NETWORK, "internal_api"
        ) == ManifestSecurityLevel.ALLOWED
        assert classify_capability(
            SecurityCategory.NETWORK, "raw_socket"
        ) == ManifestSecurityLevel.BLOCKED

    def test_classify_capability_system(self) -> None:
        """Test system capability classification."""
        assert classify_capability(
            SecurityCategory.SYSTEM, "shell_execute"
        ) == ManifestSecurityLevel.BLOCKED

    def test_unknown_capability_requires_confirm(self) -> None:
        """Test unknown capabilities default to REQUIRES_CONFIRM."""
        assert classify_capability(
            SecurityCategory.UNKNOWN, "unknown_op"
        ) == ManifestSecurityLevel.REQUIRES_CONFIRM
