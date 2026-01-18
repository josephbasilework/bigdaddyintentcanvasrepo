"""Tests for context assembly service."""

import pytest

from app.context.assembly import ContextAssembler, ContextAssemblyConfig
from app.context.models import ContextPayload, NodeContext, SelectionScope
from app.database import AsyncSessionLocal
from app.models.canvas import Canvas
from app.models.session import WorkspaceSession
from app.models.turn import TurnActor, TurnType
from app.repositories.turn_repo import AsyncTurnRepository
from app.services.intent_memory import IntentMemoryStore


@pytest.mark.asyncio
async def test_context_assembly_prioritizes_primary_selection() -> None:
    selection = SelectionScope(
        selected_nodes=["node-1", "node-2"],
        node_context=[
            NodeContext(id="node-1", title="Alpha", node_type="text"),
            NodeContext(id="node-2", title="Beta", node_type="text"),
        ],
        primary_node_id="node-2",
    )
    payload = ContextPayload(text="Plan next steps", selection=selection)

    assembler = ContextAssembler(
        config=ContextAssemblyConfig(max_nodes=3, max_turns=0),
        embedding_provider=None,
        intent_memory_store=None,
    )
    window = await assembler.assemble(payload)

    assert window.nodes
    assert window.nodes[0].id == "node-2"
    assert window.nodes[0].is_primary
    assert "selected" in window.nodes[0].reasons
    assert {node.id for node in window.nodes} == {"node-1", "node-2"}


@pytest.mark.asyncio
async def test_context_assembly_includes_explicit_turn_reference() -> None:
    session_id = "session-ctx-1"
    async with AsyncSessionLocal() as session:
        canvas = Canvas(user_id="user", name="Context Test")
        session.add(canvas)
        await session.commit()
        await session.refresh(canvas)

        workspace_session = WorkspaceSession(
            session_id=session_id,
            workspace_id=canvas.id,
            user_id="user",
        )
        session.add(workspace_session)
        await session.commit()

        repo = AsyncTurnRepository(session)
        await repo.create_turn(
            session_id=session_id,
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="First turn",
        )
        await repo.create_turn(
            session_id=session_id,
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="Second turn",
        )
        await repo.create_turn(
            session_id=session_id,
            actor=TurnActor.USER,
            turn_type=TurnType.USER_INPUT,
            summary="Third turn",
        )

    payload = ContextPayload(text="Revisit turn 1 details")
    assembler = ContextAssembler(
        config=ContextAssemblyConfig(max_nodes=0, max_turns=2, recent_turn_limit=2),
        embedding_provider=None,
        intent_memory_store=None,
    )
    window = await assembler.assemble(payload, user_id="user", session_id=session_id)

    seqs = [turn.sequence_number for turn in window.turns]
    assert 1 in seqs
    explicit_turn = next(turn for turn in window.turns if turn.sequence_number == 1)
    assert "explicit_reference" in explicit_turn.reasons


@pytest.mark.asyncio
async def test_context_assembly_applies_intent_memory_boost(tmp_path) -> None:
    memory_store = IntentMemoryStore(base_path=str(tmp_path))
    memory_store.record_explicit_rule(
        user_id="user",
        text="learn: when I say status, route to /dashboard",
    )

    selection = SelectionScope(
        selected_nodes=["node-9"],
        node_context=[
            NodeContext(id="node-9", title="Status dashboard", node_type="text"),
        ],
    )
    payload = ContextPayload(text="status update", selection=selection)

    assembler = ContextAssembler(
        config=ContextAssemblyConfig(max_nodes=2, max_turns=0),
        embedding_provider=None,
        intent_memory_store=memory_store,
    )
    window = await assembler.assemble(payload, user_id="user")

    assert window.nodes
    assert "intent_memory" in window.nodes[0].reasons
