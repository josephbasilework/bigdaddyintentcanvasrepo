"""Tests for Markdown/Obsidian user data storage."""

import json
from pathlib import Path

from app.services.user_data_store import UserDataStore


def test_persist_workspace_snapshot(tmp_path: Path) -> None:
    store = UserDataStore(base_path=str(tmp_path))

    nodes = [
        {
            "id": 1,
            "label": "Alpha",
            "type": "text",
            "x": 12,
            "y": 34,
            "metadata": {"tags": ["one", "two"]},
            "content": "Hello world",
        },
        {
            "id": 2,
            "label": "Doc Node",
            "type": "document",
            "x": 0,
            "y": 0,
        },
    ]
    edges = [
        {
            "id": 9,
            "fromNodeId": 1,
            "toNodeId": 2,
            "relationType": "references",
            "label": "ref",
        }
    ]
    documents = [
        {
            "id": "doc-1",
            "nodeId": 2,
            "title": "Doc Title",
            "content": "<p>Doc body</p>",
            "createdAt": "2026-01-17T00:00:00Z",
            "updatedAt": "2026-01-17T01:00:00Z",
        }
    ]

    store.persist_workspace_snapshot(
        user_id="user-1",
        workspace_id="ws-1",
        workspace_name="Workspace A",
        nodes=nodes,
        edges=edges,
        documents=documents,
        timestamp="2026-01-17T02:00:00Z",
    )

    workspace_dir = tmp_path / "users" / "user-1" / "workspaces" / "ws-1"
    assert (workspace_dir / "workspace.md").exists()
    assert (workspace_dir / "nodes" / "node-1.md").exists()
    assert (workspace_dir / "edges.md").exists()
    assert (workspace_dir / "documents" / "document-doc-1.md").exists()

    workspace_contents = (workspace_dir / "workspace.md").read_text(encoding="utf-8")
    assert "Workspace: Workspace A" in workspace_contents
    assert "[[node-1]]" in workspace_contents

    edges_contents = (workspace_dir / "edges.md").read_text(encoding="utf-8")
    assert "[[node-1]] --references--> [[node-2]]" in edges_contents


def test_persist_turn_and_artifact(tmp_path: Path) -> None:
    store = UserDataStore(base_path=str(tmp_path))

    store.persist_turn(
        user_id="user-1",
        session_id="session-1",
        workspace_id="ws-1",
        sequence_number=1,
        actor="user",
        turn_type="user_input",
        summary="Hello",
        payload={"job_id": "job-1"},
        timestamp="2026-01-17T03:00:00Z",
        related_node_id=1,
        related_edge_id=None,
    )
    store.persist_turn(
        user_id="user-1",
        session_id="session-1",
        workspace_id="ws-1",
        sequence_number=2,
        origin_sequence_number=1,
        actor="system",
        turn_type="node_updated",
        summary="Updated node",
        payload=None,
        timestamp="2026-01-17T03:05:00Z",
        related_node_id=1,
        related_edge_id=None,
    )

    turns_dir = tmp_path / "users" / "user-1" / "workspaces" / "ws-1" / "turns"
    turn_path = turns_dir / "turn-0001.md"
    assert turn_path.exists()
    followup_path = turns_dir / "turn-0002.md"
    assert followup_path.exists()
    index_path = turns_dir / "index.jsonl"
    assert index_path.exists()

    entries = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert entries[0]["job_id"] == "job-1"
    assert entries[1]["origin_sequence_number"] == 1
    assert "Origin turn: [[turn-0001]]" in followup_path.read_text(encoding="utf-8")

    store.persist_artifact(
        artifact={
            "id": 5,
            "job_id": "job-1",
            "user_id": "user-1",
            "workspace_id": "ws-1",
            "artifact_type": "markdown_document",
            "artifact_name": "Research Report",
            "description": "Summary report",
            "created_at": "2026-01-17T04:00:00Z",
            "updated_at": "2026-01-17T04:05:00Z",
            "inline_data": {"note": "ok"},
        }
    )

    artifacts_dir = tmp_path / "users" / "user-1" / "workspaces" / "ws-1" / "artifacts"
    artifact_path = artifacts_dir / "artifact-5.md"
    assert artifact_path.exists()
    artifact_contents = artifact_path.read_text(encoding="utf-8")
    assert "Originating turn: [[turn-0001]]" in artifact_contents


def test_persist_workspace_snapshot_includes_edge_metadata(tmp_path: Path) -> None:
    store = UserDataStore(base_path=str(tmp_path))

    nodes = [
        {"id": 1, "label": "Alpha", "type": "text", "x": 0, "y": 0},
        {"id": 2, "label": "Beta", "type": "text", "x": 40, "y": 0},
    ]
    metadata = {
        "annotation": {
            "comment": "Edge note",
            "tags": ["review", "priority"],
            "status": "draft",
        },
        "confidence": 0.72,
    }
    edges = [
        {
            "id": 9,
            "fromNodeId": 1,
            "toNodeId": 2,
            "relationType": "relates_to",
            "label": "Relates",
            "metadata": metadata,
        }
    ]

    store.persist_workspace_snapshot(
        user_id="user-2",
        workspace_id="ws-2",
        workspace_name="Workspace B",
        nodes=nodes,
        edges=edges,
        documents=[],
        timestamp="2026-01-18T02:00:00Z",
    )

    edges_path = (
        tmp_path
        / "users"
        / "user-2"
        / "workspaces"
        / "ws-2"
        / "edges.md"
    )
    edges_contents = edges_path.read_text(encoding="utf-8")
    metadata_line = next(
        line for line in edges_contents.splitlines() if "metadata=" in line
    )
    metadata_json = metadata_line.split("metadata=", 1)[1]
    assert json.loads(metadata_json) == metadata
