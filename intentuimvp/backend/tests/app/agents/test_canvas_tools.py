"""Tests for canvas tool implementations."""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.agents.tools import DEFAULT_USER_ID, ToolValidationError, get_tool_manager
from app.database import AsyncSessionLocal, async_engine
from app.models.edge import RelationType
from app.models.node import Node, NodeType
from app.repositories.canvas_repo import CanvasRepository
from app.repositories.edge_repo import EdgeRepository
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
async def test_canvas_link_nodes_tool_creates_edge() -> None:
    """Verify canvas.link_nodes persists an edge and returns its ID."""
    manager = get_tool_manager()
    token = uuid.uuid4().hex

    async with AsyncSessionLocal() as session:
        canvas_repo = CanvasRepository(session)
        node_repo = NodeRepository(session)
        canvas = await canvas_repo.create_canvas(
            DEFAULT_USER_ID, name=f"tool-edge-{token}"
        )
        source_node = await node_repo.create_node(
            canvas_id=canvas.id,
            label=f"tool-edge-source-{token}",
            type=NodeType.TEXT,
            position={"x": 0, "y": 0, "z": 0},
        )
        target_node = await node_repo.create_node(
            canvas_id=canvas.id,
            label=f"tool-edge-target-{token}",
            type=NodeType.TEXT,
            position={"x": 10, "y": 0, "z": 0},
        )

    result = await manager.execute_tool(
        "canvas.link_nodes",
        {
            "from_id": source_node.id,
            "to_id": target_node.id,
            "relation_type": RelationType.REFERENCES,
            "metadata": {"source": "tool-test"},
        },
    )

    assert result.success
    edge_id = result.output["id"]

    async with AsyncSessionLocal() as session:
        edge_repo = EdgeRepository(session)
        edge = await edge_repo.get_by_id(edge_id)
        assert edge is not None
        assert edge.canvas_id == canvas.id
        assert edge.from_node_id == source_node.id
        assert edge.to_node_id == target_node.id
        assert edge.relation_type == RelationType.REFERENCES

        source_edges = await edge_repo.get_by_node(
            source_node.id, as_source=True, as_target=True
        )
        target_edges = await edge_repo.get_by_node(
            target_node.id, as_source=True, as_target=True
        )
        assert edge_id in {edge.id for edge in source_edges}
        assert edge_id in {edge.id for edge in target_edges}


@pytest.mark.asyncio
async def test_canvas_link_nodes_tool_rejects_invalid_relation_type() -> None:
    """Verify invalid relation types are rejected before execution."""
    manager = get_tool_manager()
    token = uuid.uuid4().hex

    async with AsyncSessionLocal() as session:
        canvas_repo = CanvasRepository(session)
        node_repo = NodeRepository(session)
        canvas = await canvas_repo.create_canvas(
            DEFAULT_USER_ID, name=f"tool-edge-invalid-{token}"
        )
        source_node = await node_repo.create_node(
            canvas_id=canvas.id,
            label=f"tool-edge-source-{token}",
            type=NodeType.TEXT,
            position={"x": 0, "y": 0, "z": 0},
        )
        target_node = await node_repo.create_node(
            canvas_id=canvas.id,
            label=f"tool-edge-target-{token}",
            type=NodeType.TEXT,
            position={"x": 10, "y": 0, "z": 0},
        )

    with pytest.raises(ToolValidationError):
        await manager.execute_tool(
            "canvas.link_nodes",
            {
                "from_id": source_node.id,
                "to_id": target_node.id,
                "relation_type": "invalid-relation",
            },
        )


@pytest.mark.asyncio
async def test_canvas_link_nodes_tool_rejects_invalid_node() -> None:
    """Verify invalid node IDs fail without creating edges."""
    manager = get_tool_manager()
    token = uuid.uuid4().hex

    async with AsyncSessionLocal() as session:
        canvas_repo = CanvasRepository(session)
        node_repo = NodeRepository(session)
        canvas = await canvas_repo.create_canvas(
            DEFAULT_USER_ID, name=f"tool-edge-missing-{token}"
        )
        source_node = await node_repo.create_node(
            canvas_id=canvas.id,
            label=f"tool-edge-source-{token}",
            type=NodeType.TEXT,
            position={"x": 0, "y": 0, "z": 0},
        )

    result = await manager.execute_tool(
        "canvas.link_nodes",
        {
            "from_id": source_node.id,
            "to_id": 999999,
            "relation_type": RelationType.DEPENDS_ON,
        },
    )

    assert not result.success

    async with AsyncSessionLocal() as session:
        edge_repo = EdgeRepository(session)
        edges = await edge_repo.get_by_node(
            source_node.id, as_source=True, as_target=True
        )

    assert edges == []


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
