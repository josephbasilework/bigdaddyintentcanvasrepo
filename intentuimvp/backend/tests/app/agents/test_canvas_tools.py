"""Tests for canvas tool implementations."""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.tools import ToolValidationError, get_tool_manager
from app.database import AsyncSessionLocal, async_engine
from app.models.node import Node, NodeType


@pytest.mark.asyncio
async def test_canvas_create_node_tool_creates_node() -> None:
    """Verify canvas.create_node persists a node and returns its ID."""
    manager = get_tool_manager()
    label = f"tool-node-{uuid.uuid4().hex}"
    result = await manager.execute_tool(
        "canvas.create_node",
        {
            "type": NodeType.TEXT,
            "content": label,
            "position": {"x": 12.5, "y": 3.25, "z": 0.0},
            "metadata": {"source": "tool-test"},
        },
    )

    assert result.success
    node_id = result.output["id"]

    async with AsyncSessionLocal() as session:
        query = await session.execute(select(Node).where(Node.id == node_id))
        node = query.scalar_one_or_none()

    assert node is not None
    assert node.label == label
    assert node.type == NodeType.TEXT
    assert node.get_position() == {"x": 12.5, "y": 3.25, "z": 0.0}
    assert node.get_metadata() == {"source": "tool-test"}


@pytest.mark.asyncio
async def test_canvas_create_node_tool_rejects_invalid_type() -> None:
    """Verify invalid payloads are rejected without node creation."""
    manager = get_tool_manager()
    label = f"invalid-node-{uuid.uuid4().hex}"

    with pytest.raises(ToolValidationError):
        await manager.execute_tool(
            "canvas.create_node",
            {
                "type": "not-a-real-type",
                "content": label,
                "position": {"x": 0, "y": 0, "z": 0},
            },
        )

    async with AsyncSessionLocal() as session:
        query = await session.execute(select(Node).where(Node.label == label))
        node = query.scalar_one_or_none()

    assert node is None


@pytest_asyncio.fixture(autouse=True)
async def _dispose_async_engine() -> AsyncGenerator[None, None]:
    """Dispose the async engine to avoid lingering background threads."""
    yield
    await async_engine.dispose()
