"""Tests for MCP installer workflow."""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.mcp.models  # noqa: F401 - ensure models are registered
from app.database import Base
from app.mcp.installer import MCPInstaller
from app.mcp.registry import MCPServerRegistry
from app.schemas.mcp import MCPInstallRequest

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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

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


@pytest.mark.asyncio
async def test_install_preview_requires_confirmation(db_session: AsyncSession) -> None:
    installer = MCPInstaller(db_session)
    payload = MCPInstallRequest(catalog_id="google-calendar")
    result = await installer.install(payload)
    assert result["success"] is False
    assert result["requires_confirmation"] is True
    assert result["preview"]
    assert result["preview"]["missing_credentials"]
    assert result["preview"]["security_checks"]
    assert result["preview"]["permission_scopes"]


@pytest.mark.asyncio
async def test_install_missing_credentials_rejected(db_session: AsyncSession) -> None:
    installer = MCPInstaller(db_session)
    payload = MCPInstallRequest(catalog_id="google-calendar", confirmed=True)
    result = await installer.install(payload)
    assert result["success"] is False
    assert "Missing credentials" in (result.get("error") or "")


@pytest.mark.asyncio
async def test_install_with_credentials_enables_server(db_session: AsyncSession) -> None:
    installer = MCPInstaller(db_session)
    preview = await installer.build_preview(MCPInstallRequest(catalog_id="google-calendar"))
    tools = [tool["name"] for tool in preview["preview"]["tools"] if tool.get("name")]

    payload = MCPInstallRequest(
        catalog_id="google-calendar",
        credentials={"GOOGLE_CALENDAR_CREDENTIALS": "{}"},
        approved_tools=tools,
        confirmed=True,
    )
    result = await installer.install(payload)
    assert result["success"] is True

    registry = MCPServerRegistry(db_session)
    server = await registry.get_server("google-calendar")
    assert server is not None
    assert server.enabled is True


@pytest.mark.asyncio
async def test_install_blocks_duplicate_tools(db_session: AsyncSession) -> None:
    installer = MCPInstaller(db_session)
    manifest = {
        "protocolVersion": "2024-11-05",
        "name": "dup-mcp",
        "version": "1.0.0",
        "description": "Duplicate tool test",
        "capabilities": {
            "tools": [
                {
                    "name": "dup_tool",
                    "description": "First tool",
                    "input_schema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
                {
                    "name": "dup_tool",
                    "description": "Second tool",
                    "input_schema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            ]
        },
    }
    payload = MCPInstallRequest(
        server_id="dup-mcp",
        name="Duplicate MCP",
        transport_type="stdio",
        transport_config={"command": ["node", "server.js"]},
        manifest=manifest,
        approved_tools=["dup_tool"],
        confirmed=True,
    )
    result = await installer.install(payload)
    assert result["success"] is False
    assert "Duplicate tool names" in (result.get("error") or "")
