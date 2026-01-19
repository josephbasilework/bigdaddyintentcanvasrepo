"""User data storage in Markdown/Obsidian-compatible format."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_COMPONENT_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def _sanitize_component(value: str) -> str:
    cleaned = _COMPONENT_RE.sub("_", value.strip())
    return cleaned.strip("_") or "default"


def _serialize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    return json.dumps(value, ensure_ascii=True)


def _format_json_block(payload: Any) -> list[str]:
    if payload is None:
        return []
    try:
        rendered = json.dumps(
            payload, ensure_ascii=True, indent=2, sort_keys=True, default=str
        )
    except TypeError:
        rendered = json.dumps(str(payload), ensure_ascii=True)
    return ["```json", rendered, "```"]


def _write_markdown_file(
    path: Path,
    frontmatter: Iterable[tuple[str, Any]],
    body_lines: list[str],
) -> None:
    lines = ["---"]
    for key, value in frontmatter:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        lines.append(f"{key}: {_serialize_value(value)}")
    lines.append("---")
    path.write_text("\n".join(lines + body_lines) + "\n", encoding="utf-8")


def _extract_node_metadata(node: Mapping[str, Any]) -> dict[str, Any]:
    metadata = node.get("metadata") or node.get("node_metadata") or node.get("nodeMetadata")
    return metadata if isinstance(metadata, dict) else {}


def _extract_node_position(node: Mapping[str, Any]) -> dict[str, float]:
    position = node.get("position")
    if isinstance(position, Mapping):
        return {
            "x": float(position.get("x", node.get("x", 0)) or 0),
            "y": float(position.get("y", node.get("y", 0)) or 0),
            "z": float(position.get("z", node.get("z", 0)) or 0),
        }
    return {
        "x": float(node.get("x", 0) or 0),
        "y": float(node.get("y", 0) or 0),
        "z": float(node.get("z", 0) or 0),
    }


def _extract_node_content(
    node: Mapping[str, Any], metadata: Mapping[str, Any]
) -> str | None:
    content = node.get("content")
    if isinstance(content, str) and content.strip():
        return content
    for key in ("content", "text", "body", "markdown", "html"):
        candidate = metadata.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return None


def _detect_content_format(content: str | None) -> str:
    if not content:
        return "markdown"
    lower = content.lower()
    if "</" in lower and "<" in lower and ">" in lower:
        return "html"
    return "markdown"


def _node_file_base(node_id: Any, index: int) -> str:
    if node_id is None:
        return f"node-temp-{index + 1}"
    return f"node-{_sanitize_component(str(node_id))}"


def _document_file_base(doc_id: Any, index: int) -> str:
    if doc_id is None:
        return f"document-temp-{index + 1}"
    return f"document-{_sanitize_component(str(doc_id))}"


def _turn_file_base(sequence_number: int) -> str:
    seq = str(sequence_number).zfill(4)
    return f"turn-{seq}"


def _edge_relation(edge: Mapping[str, Any]) -> str:
    relation = (
        edge.get("relationType")
        or edge.get("relation_type")
        or edge.get("type")
        or "references"
    )
    return str(relation)


def _edge_source(edge: Mapping[str, Any]) -> Any:
    return (
        edge.get("fromNodeId")
        or edge.get("sourceNodeId")
        or edge.get("from_node_id")
        or edge.get("source")
    )


def _edge_target(edge: Mapping[str, Any]) -> Any:
    return (
        edge.get("toNodeId")
        or edge.get("targetNodeId")
        or edge.get("to_node_id")
        or edge.get("target")
    )


def _extract_edge_metadata(edge: Mapping[str, Any]) -> dict[str, Any] | None:
    metadata = (
        edge.get("metadata")
        or edge.get("edge_metadata")
        or edge.get("edgeMetadata")
    )
    if isinstance(metadata, Mapping) and metadata:
        return dict(metadata)
    return None


def _serialize_edge_metadata(metadata: Mapping[str, Any]) -> str:
    try:
        return json.dumps(metadata, ensure_ascii=True, sort_keys=True)
    except TypeError:
        return json.dumps(str(metadata), ensure_ascii=True)


def _extract_job_id(payload: Mapping[str, Any] | None) -> str | None:
    if not payload:
        return None
    job_id = payload.get("job_id") or payload.get("jobId")
    return str(job_id) if job_id else None


class UserDataStore:
    """Persist user data as Markdown/Obsidian-friendly files."""

    def __init__(self, *, base_path: str | None = None) -> None:
        settings = get_settings()
        self._base_path = Path(base_path or settings.user_data_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def persist_workspace_snapshot(
        self,
        *,
        user_id: str,
        workspace_id: str | int | None,
        workspace_name: str | None,
        nodes: list[Mapping[str, Any]],
        edges: list[Mapping[str, Any]],
        documents: list[Mapping[str, Any]] | None = None,
        timestamp: str | None = None,
    ) -> None:
        workspace_dir = self._workspace_dir(user_id, workspace_id)
        nodes_dir = workspace_dir / "nodes"
        documents_dir = workspace_dir / "documents"
        nodes_dir.mkdir(parents=True, exist_ok=True)
        documents_dir.mkdir(parents=True, exist_ok=True)

        resolved_docs = self._normalize_documents(documents or [], nodes)
        node_bases: list[str] = []
        node_labels: dict[str, str] = {}

        for index, node in enumerate(nodes):
            node_id = node.get("id") or node.get("nodeId")
            node_label = str(node.get("label") or node.get("title") or "Untitled")
            node_type = str(node.get("type") or "text")
            position = _extract_node_position(node)
            metadata = _extract_node_metadata(node)
            content = _extract_node_content(node, metadata)
            node_base = _node_file_base(node_id, index)
            node_labels[node_base] = node_label
            node_bases.append(node_base)

            frontmatter = [
                ("node_id", node_id),
                ("type", node_type),
                ("label", node_label),
                ("position_x", position.get("x", 0)),
                ("position_y", position.get("y", 0)),
                ("position_z", position.get("z", 0)),
                ("created_at", node.get("created_at") or node.get("createdAt")),
                ("metadata_keys", sorted(metadata.keys()) if metadata else None),
                ("metadata_json", metadata if metadata else None),
            ]

            body_lines = [f"# {node_label}", ""]
            if content:
                body_lines.extend(["## Content", content, ""])
            if metadata:
                body_lines.extend(["## Metadata"] + _format_json_block(metadata) + [""])

            node_path = nodes_dir / f"{node_base}.md"
            _write_markdown_file(node_path, frontmatter, body_lines)

        self._prune_extra_files(nodes_dir, node_bases, prefix="node-")

        document_bases: list[str] = []
        for index, doc in enumerate(resolved_docs):
            doc_id = doc.get("id")
            node_id = doc.get("node_id")
            title = str(doc.get("title") or "Untitled")
            content = doc.get("content") if isinstance(doc.get("content"), str) else ""
            doc_base = _document_file_base(doc_id or node_id, index)
            document_bases.append(doc_base)

            node_link = self._node_link(node_id)
            frontmatter = [
                ("document_id", doc_id),
                ("node_id", node_id),
                ("title", title),
                ("content_format", _detect_content_format(content)),
                ("created_at", doc.get("created_at")),
                ("updated_at", doc.get("updated_at")),
            ]
            body_lines = [f"# {title}", ""]
            if node_link:
                body_lines.extend([f"Linked node: {node_link}", ""])
            if content:
                body_lines.append(content)

            doc_path = documents_dir / f"{doc_base}.md"
            _write_markdown_file(doc_path, frontmatter, body_lines)

        self._prune_extra_files(documents_dir, document_bases, prefix="document-")

        edges_path = workspace_dir / "edges.md"
        self._write_edges_file(
            edges_path=edges_path,
            workspace_id=workspace_id,
            edges=edges,
        )

        workspace_path = workspace_dir / "workspace.md"
        self._write_workspace_overview(
            workspace_path=workspace_path,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            nodes=node_bases,
            node_labels=node_labels,
            documents=document_bases,
            edges_count=len(edges),
            timestamp=timestamp or datetime.now(UTC).isoformat(),
        )

    def persist_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        sequence_number: int,
        origin_sequence_number: int | None = None,
        actor: str,
        turn_type: str,
        summary: str,
        payload: Mapping[str, Any] | None,
        timestamp: str,
        workspace_id: str | int | None = None,
        related_node_id: int | str | None = None,
        related_edge_id: int | str | None = None,
    ) -> None:
        turns_dir = self._turns_dir(user_id, workspace_id, session_id)
        turns_dir.mkdir(parents=True, exist_ok=True)

        turn_base = _turn_file_base(sequence_number)
        turn_path = turns_dir / f"{turn_base}.md"
        job_id = _extract_job_id(payload)

        frontmatter = [
            ("sequence_number", sequence_number),
            ("origin_sequence_number", origin_sequence_number),
            ("session_id", session_id),
            ("workspace_id", workspace_id),
            ("timestamp", timestamp),
            ("actor", actor),
            ("type", turn_type),
            ("related_node_id", related_node_id),
            ("related_edge_id", related_edge_id),
            ("job_id", job_id),
        ]

        body_lines = [f"# Turn {sequence_number}", "", summary, ""]
        if origin_sequence_number is not None:
            origin_link = self._turn_link(origin_sequence_number)
            if origin_link:
                body_lines.extend([f"Origin turn: {origin_link}", ""])
        if payload:
            body_lines.extend(["## Payload"] + _format_json_block(payload) + [""])

        _write_markdown_file(turn_path, frontmatter, body_lines)

        index_entry = {
            "sequence_number": sequence_number,
            "origin_sequence_number": origin_sequence_number,
            "session_id": session_id,
            "workspace_id": workspace_id,
            "timestamp": timestamp,
            "actor": actor,
            "type": turn_type,
            "summary": summary,
            "related_node_id": related_node_id,
            "related_edge_id": related_edge_id,
            "job_id": job_id,
            "turn_file": f"{turn_base}.md",
        }
        self._upsert_index(
            index_path=turns_dir / "index.jsonl",
            entries=[index_entry],
            key="sequence_number",
            order_key="sequence_number",
            markdown_path=turns_dir / "index.md",
            markdown_title="Turns Index",
            link_key="turn_file",
            label_key="summary",
        )

    def persist_artifact(
        self,
        *,
        artifact: Mapping[str, Any],
        origin_turn: int | None = None,
    ) -> None:
        user_id = str(artifact.get("user_id") or "system")
        workspace_id = artifact.get("workspace_id")
        artifacts_dir = self._artifacts_dir(user_id, workspace_id)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        artifact_id = artifact.get("id")
        job_id = artifact.get("job_id")
        if artifact_id is None:
            artifact_base = f"artifact-temp-{_sanitize_component(str(job_id or 'unknown'))}"
        else:
            artifact_base = f"artifact-{_sanitize_component(str(artifact_id))}"
        artifact_path = artifacts_dir / f"{artifact_base}.md"

        resolved_turn = origin_turn
        if resolved_turn is None and job_id:
            resolved_turn = self._find_turn_for_job(
                user_id=user_id,
                workspace_id=workspace_id,
                session_id=None,
                job_id=str(job_id),
            )

        turn_link = (
            self._turn_link(resolved_turn) if resolved_turn is not None else None
        )

        frontmatter = [
            ("artifact_id", artifact_id),
            ("job_id", job_id),
            ("workspace_id", workspace_id),
            ("artifact_type", artifact.get("artifact_type")),
            ("artifact_name", artifact.get("artifact_name")),
            ("description", artifact.get("description")),
            ("filename", artifact.get("filename")),
            ("mime_type", artifact.get("mime_type")),
            ("size_bytes", artifact.get("size_bytes")),
            ("storage_path", artifact.get("storage_path")),
            ("created_at", artifact.get("created_at")),
            ("updated_at", artifact.get("updated_at")),
            ("origin_turn", resolved_turn),
        ]

        body_lines = [f"# Artifact: {artifact.get('artifact_name')}", ""]
        if turn_link:
            body_lines.append(f"Originating turn: {turn_link}")
            body_lines.append("")
        if artifact.get("description"):
            body_lines.append(str(artifact["description"]))
            body_lines.append("")
        if artifact.get("inline_data"):
            body_lines.extend(["## Inline Data"] + _format_json_block(artifact["inline_data"]) + [""])
        if artifact.get("storage_path"):
            body_lines.append(f"File: `{artifact['storage_path']}`")

        _write_markdown_file(artifact_path, frontmatter, body_lines)

        index_entry = {
            "artifact_id": artifact_id,
            "artifact_type": artifact.get("artifact_type"),
            "artifact_name": artifact.get("artifact_name"),
            "job_id": job_id,
            "workspace_id": workspace_id,
            "created_at": artifact.get("created_at"),
            "origin_turn": resolved_turn,
            "artifact_file": f"{artifact_base}.md",
        }
        self._upsert_index(
            index_path=artifacts_dir / "index.jsonl",
            entries=[index_entry],
            key="artifact_id",
            order_key="artifact_id",
            markdown_path=artifacts_dir / "index.md",
            markdown_title="Artifacts Index",
            link_key="artifact_file",
            label_key="artifact_name",
        )

    def export_workspace_from_database(
        self,
        *,
        db: Any,
        user_id: str,
        workspace_id: int,
    ) -> None:
        """Export a workspace from database storage into Markdown files."""
        from app.repositories.canvas import CanvasRepository
        from app.repositories.session_repo import SessionRepository
        from app.repositories.turn_repo import TurnRepository

        canvas_repo = CanvasRepository(db)
        canvas = canvas_repo.get_by_id(workspace_id)
        if canvas is None:
            return

        payload = canvas_repo.serialize_canvas(canvas, include_edges=True)
        self.persist_workspace_snapshot(
            user_id=user_id,
            workspace_id=workspace_id,
            workspace_name=payload.get("name"),
            nodes=payload.get("nodes", []),
            edges=payload.get("edges", []),
            documents=[],
            timestamp=payload.get("updated_at") or datetime.now(UTC).isoformat(),
        )

        session_repo = SessionRepository(db)
        session = session_repo.get_by_user_and_workspace(user_id, workspace_id)
        if session is None:
            return

        turn_repo = TurnRepository(db)
        turns = turn_repo.get_turns_for_session(session.session_id)
        for turn in turns:
            self.persist_turn(
                user_id=session.user_id or user_id,
                session_id=session.session_id,
                sequence_number=turn.sequence_number,
                origin_sequence_number=turn.origin_sequence_number,
                actor=getattr(turn.actor, "value", str(turn.actor)),
                turn_type=getattr(turn.type, "value", str(turn.type)),
                summary=turn.summary,
                payload=turn.get_payload(),
                timestamp=turn.timestamp.isoformat(),
                workspace_id=workspace_id,
                related_node_id=turn.related_node_id,
                related_edge_id=turn.related_edge_id,
            )

    def _workspace_dir(self, user_id: str, workspace_id: str | int | None) -> Path:
        workspace_component = _sanitize_component(str(workspace_id or "default"))
        return self._user_dir(user_id) / "workspaces" / workspace_component

    def _turns_dir(
        self,
        user_id: str,
        workspace_id: str | int | None,
        session_id: str,
    ) -> Path:
        if workspace_id is not None:
            return self._workspace_dir(user_id, workspace_id) / "turns"
        session_component = _sanitize_component(str(session_id))
        return self._user_dir(user_id) / "sessions" / session_component / "turns"

    def _artifacts_dir(
        self, user_id: str, workspace_id: str | int | None
    ) -> Path:
        if workspace_id is not None:
            return self._workspace_dir(user_id, workspace_id) / "artifacts"
        return self._user_dir(user_id) / "artifacts"

    def _user_dir(self, user_id: str) -> Path:
        return self._base_path / "users" / _sanitize_component(user_id)

    def _node_link(self, node_id: Any) -> str | None:
        if node_id is None:
            return None
        base = _node_file_base(node_id, 0)
        return f"[[{base}]]"

    def _turn_link(self, sequence_number: int | None) -> str | None:
        if sequence_number is None:
            return None
        return f"[[{_turn_file_base(sequence_number)}]]"

    def _normalize_documents(
        self,
        documents: list[Mapping[str, Any]],
        nodes: list[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen_node_ids: set[str] = set()
        for doc in documents:
            node_id = doc.get("node_id") or doc.get("nodeId")
            doc_id = doc.get("id")
            normalized.append(
                {
                    "id": doc_id,
                    "node_id": node_id,
                    "title": doc.get("title") or doc.get("label"),
                    "content": doc.get("content"),
                    "created_at": doc.get("created_at") or doc.get("createdAt"),
                    "updated_at": doc.get("updated_at") or doc.get("updatedAt"),
                }
            )
            if node_id:
                seen_node_ids.add(str(node_id))

        for node in nodes:
            node_type = str(node.get("type") or "").lower()
            if node_type != "document":
                continue
            node_id = node.get("id") or node.get("nodeId")
            if node_id is None or str(node_id) in seen_node_ids:
                continue
            metadata = _extract_node_metadata(node)
            normalized.append(
                {
                    "id": None,
                    "node_id": node_id,
                    "title": node.get("label") or node.get("title"),
                    "content": _extract_node_content(node, metadata),
                    "created_at": node.get("created_at") or node.get("createdAt"),
                    "updated_at": None,
                }
            )
            seen_node_ids.add(str(node_id))

        return normalized

    def _write_edges_file(
        self,
        *,
        edges_path: Path,
        workspace_id: str | int | None,
        edges: list[Mapping[str, Any]],
    ) -> None:
        body_lines = ["# Workspace Edges", ""]
        for edge in edges:
            source = _edge_source(edge)
            target = _edge_target(edge)
            relation = _edge_relation(edge)
            label = edge.get("label")
            metadata = _extract_edge_metadata(edge)
            source_link = self._node_link(source) or str(source)
            target_link = self._node_link(target) or str(target)
            line = f"- {source_link} --{relation}--> {target_link}"
            if label:
                line += f" ({label})"
            if metadata:
                line += f" | metadata={_serialize_edge_metadata(metadata)}"
            body_lines.append(line)

        frontmatter = [
            ("workspace_id", workspace_id),
            ("edges_count", len(edges)),
        ]
        _write_markdown_file(edges_path, frontmatter, body_lines)

    def _write_workspace_overview(
        self,
        *,
        workspace_path: Path,
        workspace_id: str | int | None,
        workspace_name: str | None,
        nodes: list[str],
        node_labels: Mapping[str, str],
        documents: list[str],
        edges_count: int,
        timestamp: str,
    ) -> None:
        frontmatter = [
            ("workspace_id", workspace_id),
            ("workspace_name", workspace_name or "default"),
            ("updated_at", timestamp),
            ("nodes_count", len(nodes)),
            ("edges_count", edges_count),
            ("documents_count", len(documents)),
        ]

        body_lines = [f"# Workspace: {workspace_name or 'default'}", ""]
        if nodes:
            body_lines.append("## Nodes")
            for node_base in nodes:
                label = node_labels.get(node_base, "")
                label_suffix = f" - {label}" if label else ""
                body_lines.append(f"- [[{node_base}]]{label_suffix}")
            body_lines.append("")
        if documents:
            body_lines.append("## Documents")
            for doc_base in documents:
                body_lines.append(f"- [[{doc_base}]]")
            body_lines.append("")

        _write_markdown_file(workspace_path, frontmatter, body_lines)

    def _prune_extra_files(
        self, directory: Path, expected_bases: list[str], *, prefix: str
    ) -> None:
        expected = {f"{base}.md" for base in expected_bases}
        for path in directory.glob("*.md"):
            if not path.name.startswith(prefix):
                continue
            if path.name not in expected:
                path.unlink(missing_ok=True)

    def _find_turn_for_job(
        self,
        *,
        user_id: str,
        workspace_id: str | int | None,
        session_id: str | None,
        job_id: str,
    ) -> int | None:
        if session_id:
            turns_dir = self._turns_dir(user_id, None, session_id)
        else:
            turns_dir = self._turns_dir(user_id, workspace_id, "default")
        index_path = turns_dir / "index.jsonl"
        entries = self._load_index_entries(index_path)
        matching = [entry for entry in entries if entry.get("job_id") == job_id]
        if not matching:
            return None
        latest = max(matching, key=lambda entry: entry.get("sequence_number", 0))
        return latest.get("sequence_number")

    def _load_index_entries(self, index_path: Path) -> list[dict[str, Any]]:
        if not index_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping malformed index line in %s", index_path)
        return entries

    def _upsert_index(
        self,
        *,
        index_path: Path,
        entries: list[dict[str, Any]],
        key: str,
        order_key: str,
        markdown_path: Path,
        markdown_title: str,
        link_key: str,
        label_key: str,
    ) -> None:
        existing = self._load_index_entries(index_path)
        merged: dict[Any, dict[str, Any]] = {
            entry.get(key): entry for entry in existing if entry.get(key) is not None
        }
        for entry in entries:
            merged[entry.get(key)] = entry

        ordered = sorted(merged.values(), key=lambda item: item.get(order_key, 0))
        index_path.write_text(
            "\n".join(json.dumps(entry, ensure_ascii=True) for entry in ordered) + "\n",
            encoding="utf-8",
        )

        body_lines = [f"# {markdown_title}", ""]
        for entry in ordered:
            link_value = entry.get(link_key)
            if not link_value:
                continue
            link_base = Path(str(link_value)).stem
            label = str(entry.get(label_key) or "").strip()
            if label:
                body_lines.append(f"- [[{link_base}]] - {label}")
            else:
                body_lines.append(f"- [[{link_base}]]")
        _write_markdown_file(markdown_path, [("entries", len(ordered))], body_lines)


_user_data_store: UserDataStore | None = None


def get_user_data_store(*, base_path: str | None = None, force_new: bool = False) -> UserDataStore:
    """Get singleton user data store."""
    global _user_data_store
    if _user_data_store is None or force_new:
        _user_data_store = UserDataStore(base_path=base_path)
    return _user_data_store
