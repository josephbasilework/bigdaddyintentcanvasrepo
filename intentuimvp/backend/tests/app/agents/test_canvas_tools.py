"""Tests for canvas tool implementations."""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.tools import DEFAULT_USER_ID, ToolValidationError, get_tool_manager
from app.database import AsyncSessionLocal, async_engine
from app.models.node import Node, NodeType
from app.repositories.canvas_repo import CanvasRepository
from app.repositories.node_repo import NodeRepository


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


@pytest.mark.asyncio
async def test_workspace_search_scopes() -> None:
    """Verify workspace.search filters results by scope."""
    manager = get_tool_manager()
    token = uuid.uuid4().hex
    query = f"search-{token}"

    async with AsyncSessionLocal() as session:
        canvas_repo = CanvasRepository(session)
        node_repo = NodeRepository(session)
        canvas_one = await canvas_repo.create_canvas(
            DEFAULT_USER_ID, name=f"search-{token}-one"
        )
        canvas_two = await canvas_repo.create_canvas(
            DEFAULT_USER_ID, name=f"search-{token}-two"
        )

        node_one = await node_repo.create_node(
            canvas_id=canvas_one.id,
            label=f"{query}-alpha",
            type=NodeType.TEXT,
            position={"x": 0, "y": 0, "z": 0},
            node_metadata={"note": "alpha"},
        )
        node_two = await node_repo.create_node(
            canvas_id=canvas_two.id,
            label=f"{query}-beta",
            type=NodeType.DOCUMENT,
            position={"x": 1, "y": 1, "z": 0},
            node_metadata={"note": "beta"},
        )
        await node_repo.create_node(
            canvas_id=canvas_two.id,
            label="unrelated",
            type=NodeType.TEXT,
            position={"x": 2, "y": 2, "z": 0},
        )

    selection_result = await manager.execute_tool(
        "workspace.search",
        {
            "query": query,
            "scope": "selection",
            "selection_ids": [node_one.id],
        },
    )
    assert selection_result.success
    assert [item["id"] for item in selection_result.output] == [node_one.id]

    canvas_result = await manager.execute_tool(
        "workspace.search",
        {
            "query": query,
            "scope": "canvas",
            "canvas_id": canvas_two.id,
        },
    )
    assert canvas_result.success
    canvas_ids = {item["id"] for item in canvas_result.output}
    assert canvas_ids == {node_two.id}

    all_result = await manager.execute_tool(
        "workspace.search",
        {
            "query": query,
            "scope": "all",
        },
    )
    assert all_result.success
    all_ids = {item["id"] for item in all_result.output}
    assert node_one.id in all_ids
    assert node_two.id in all_ids

    empty_result = await manager.execute_tool(
        "workspace.search",
        {
            "query": f"missing-{token}",
            "scope": "all",
        },
    )
    assert empty_result.success
    assert empty_result.output == []


@pytest_asyncio.fixture(autouse=True)
async def _dispose_async_engine() -> AsyncGenerator[None, None]:
    """Dispose the async engine to avoid lingering background threads."""
    yield
    await async_engine.dispose()
