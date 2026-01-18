"""Context assembly service for routing relevant context into agent workflows."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from app.context.models import ContextPayload, SelectionScope
from app.context.references import parse_references
from app.database import AsyncSessionLocal
from app.models.intent import AttachmentDB
from app.models.edge import Edge
from app.models.node import Node
from app.models.turn import Turn, TurnActor, TurnType
from app.repositories.session_repo import AsyncSessionRepository

EmbeddingProvider = Callable[[str], Sequence[float] | None]

try:  # Optional dependency for semantic similarity.
    from app.services.embedding import create_embedding_provider
except Exception:  # pragma: no cover - optional dependency surface
    create_embedding_provider = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from app.services.intent_memory import IntentMemoryStore

try:  # Optional dependency for intent memory boosts.
    from app.services.intent_memory import get_intent_memory_store
except Exception:  # pragma: no cover - optional dependency surface
    get_intent_memory_store = None  # type: ignore[assignment]


_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ContextAssemblyConfig:
    """Tuning parameters for context assembly."""

    max_nodes: int = 6
    max_turns: int = 8
    candidate_node_limit: int = 200
    recent_turn_limit: int = 20
    expansion_limit: int = 10
    similarity_threshold: float = 0.2
    recency_decay: float = 0.9

    selection_weight: float = 0.6
    primary_weight: float = 0.3
    explicit_weight: float = 0.55
    expansion_weight: float = 0.25
    recency_weight: float = 0.35
    similarity_weight: float = 0.5
    memory_weight: float = 0.3


@dataclass
class ContextNode:
    """Scored node context for routing."""

    id: str
    title: str
    node_type: str
    content: str | None = None
    metadata: dict[str, Any] | None = None
    score: float = 0.0
    similarity: float | None = None
    recency: float | None = None
    reasons: list[str] = field(default_factory=list)
    reason_scores: dict[str, float] = field(default_factory=dict)
    is_primary: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "node_type": self.node_type,
            "score": self.score,
            "reasons": list(self.reasons),
            "is_primary": self.is_primary,
        }
        if self.similarity is not None:
            payload["similarity"] = self.similarity
        if self.recency is not None:
            payload["recency"] = self.recency
        if self.reason_scores:
            payload["reason_scores"] = dict(self.reason_scores)
        if self.content is not None:
            payload["content"] = self.content
        if self.metadata is not None:
            payload["metadata"] = self.metadata
        return payload


@dataclass
class ContextTurn:
    """Scored turn context for routing."""

    id: int
    sequence_number: int
    summary: str
    actor: TurnActor | str
    turn_type: TurnType | str
    timestamp: str
    score: float = 0.0
    similarity: float | None = None
    recency: float | None = None
    reasons: list[str] = field(default_factory=list)
    reason_scores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "sequence_number": self.sequence_number,
            "summary": self.summary,
            "actor": str(self.actor),
            "turn_type": str(self.turn_type),
            "timestamp": self.timestamp,
            "score": self.score,
            "reasons": list(self.reasons),
        }
        if self.similarity is not None:
            payload["similarity"] = self.similarity
        if self.recency is not None:
            payload["recency"] = self.recency
        if self.reason_scores:
            payload["reason_scores"] = dict(self.reason_scores)
        return payload


@dataclass
class ContextAttachment:
    """Attachment metadata for routing context."""

    id: str
    filename: str
    attachment_type: str
    mime_type: str
    size_bytes: int
    text_content: str | None = None
    transcription: str | None = None
    description: str | None = None
    status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "filename": self.filename,
            "attachment_type": self.attachment_type,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
        }
        if self.text_content is not None:
            payload["text_content"] = self.text_content
        if self.transcription is not None:
            payload["transcription"] = self.transcription
        if self.description is not None:
            payload["description"] = self.description
        if self.status is not None:
            payload["status"] = self.status
        return payload


@dataclass
class ContextWindow:
    """Assembled context window for a user interaction."""

    input_text: str
    nodes: list[ContextNode]
    turns: list[ContextTurn]
    attachments: list[ContextAttachment]
    selection: SelectionScope | None = None
    explicit_node_refs: list[str] = field(default_factory=list)
    explicit_turn_refs: list[int] = field(default_factory=list)

    def to_prompt(self, max_content_chars: int = 220) -> str:
        """Render a concise context summary for agent prompts."""
        lines: list[str] = []

        primary_nodes = [node for node in self.nodes if node.is_primary]
        other_nodes = [node for node in self.nodes if not node.is_primary]

        if primary_nodes:
            lines.append("Primary nodes:")
            lines.extend(_format_node_lines(primary_nodes, max_content_chars))

        if other_nodes:
            lines.append("Other nodes:")
            lines.extend(_format_node_lines(other_nodes, max_content_chars))

        if self.turns:
            lines.append("Recent turns:")
            lines.extend(_format_turn_lines(self.turns, max_content_chars))

        if self.attachments:
            lines.append("Attachments:")
            lines.extend(_format_attachment_lines(self.attachments, max_content_chars))

        return "\n".join(lines).strip()

    def to_dict(self) -> dict[str, Any]:
        """Serialize context window for debugging or preview."""
        payload: dict[str, Any] = {
            "input_text": self.input_text,
            "prompt": self.to_prompt(),
            "nodes": [node.to_dict() for node in self.nodes],
            "turns": [turn.to_dict() for turn in self.turns],
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "explicit_node_refs": list(self.explicit_node_refs),
            "explicit_turn_refs": list(self.explicit_turn_refs),
        }
        if self.selection is not None:
            payload["selection"] = self.selection.to_dict()
        return payload


@dataclass(frozen=True)
class _MemorySignal:
    tokens: set[str]
    score: float
    reason: str


class ContextAssembler:
    """Compute relevant context for a user interaction."""

    def __init__(
        self,
        *,
        config: ContextAssemblyConfig | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        intent_memory_store: IntentMemoryStore | None = None,
    ) -> None:
        self._config = config or ContextAssemblyConfig()
        self._embedding_provider = embedding_provider
        if self._embedding_provider is None and create_embedding_provider is not None:
            try:
                self._embedding_provider = create_embedding_provider()
            except Exception:
                self._embedding_provider = None
        self._intent_memory_store = intent_memory_store

    async def assemble(
        self,
        payload: ContextPayload,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        workspace_id: int | str | None = None,
    ) -> ContextWindow:
        selection = payload.selection or SelectionScope()
        selected_ids = list(selection.selected_nodes)
        if not selected_ids and selection.node_context:
            selected_ids = [node.id for node in selection.node_context if node.id]
        selected_edge_ids = list(selection.selected_edges)
        primary_id = selection.primary_node_id
        if primary_id is None and selected_ids:
            primary_id = selected_ids[-1]

        selected_node_ids_int: set[int] = set()
        for node_id in selected_ids:
            parsed = _coerce_int(node_id)
            if parsed is not None:
                selected_node_ids_int.add(parsed)
        selected_edge_ids_int: set[int] = set()
        for edge_id in selected_edge_ids:
            parsed = _coerce_int(edge_id)
            if parsed is not None:
                selected_edge_ids_int.add(parsed)

        nodes_by_id: dict[str, ContextNode] = {}
        for node_ctx in selection.node_context:
            node_id = node_ctx.id
            nodes_by_id[node_id] = ContextNode(
                id=node_id,
                title=node_ctx.title or f"Node {node_id}",
                node_type=node_ctx.node_type or "text",
                content=node_ctx.content,
                metadata=node_ctx.metadata,
            )

        parsed_refs = parse_references(payload.text)
        explicit_node_ids = set(parsed_refs.node_ids)
        explicit_turn_ids = set(parsed_refs.turn_numbers)
        explicit_node_handles = set(parsed_refs.node_handles)
        explicit_named_entities = set(parsed_refs.named_entities)

        node_ids_to_fetch: set[int] = set()
        for node_id in selected_ids:
            if node_id not in nodes_by_id:
                parsed = _coerce_int(node_id)
                if parsed is not None:
                    node_ids_to_fetch.add(parsed)
        for node_id in explicit_node_ids:
            if node_id not in nodes_by_id:
                parsed = _coerce_int(node_id)
                if parsed is not None:
                    node_ids_to_fetch.add(parsed)

        recent_turns: list[Turn] = []
        explicit_turns: list[Turn] = []
        recent_node_ids: set[int] = set()
        expanded_node_ids: set[int] = set()
        attachment_context: list[ContextAttachment] = []
        resolved_workspace_id = _coerce_int(workspace_id)

        if (
            session_id
            or node_ids_to_fetch
            or resolved_workspace_id is not None
            or payload.attachments
            or explicit_node_handles
            or explicit_named_entities
        ):
            async with AsyncSessionLocal() as session:
                if session_id and resolved_workspace_id is None:
                    session_repo = AsyncSessionRepository(session)
                    session_row = await session_repo.get_by_session_id(session_id)
                    if session_row is not None:
                        resolved_workspace_id = session_row.workspace_id

                if session_id:
                    recent_turns = await _fetch_recent_turns(
                        session,
                        session_id,
                        limit=self._config.recent_turn_limit,
                    )
                    explicit_turns = await _fetch_turns_by_sequence(
                        session,
                        session_id,
                        explicit_turn_ids,
                    )
                    recent_node_ids = {
                        int(turn.related_node_id)
                        for turn in recent_turns
                        if turn.related_node_id is not None
                    }

                node_ids_to_fetch.update(recent_node_ids)
                if (
                    resolved_workspace_id is not None
                    and (selected_node_ids_int or selected_edge_ids_int)
                    and self._config.expansion_limit > 0
                ):
                    expanded_node_ids = await _fetch_expanded_node_ids(
                        session,
                        resolved_workspace_id,
                        selected_node_ids_int,
                        selected_edge_ids_int,
                        limit=self._config.expansion_limit,
                    )
                    node_ids_to_fetch.update(expanded_node_ids)
                if node_ids_to_fetch:
                    fetched_nodes = await _fetch_nodes_by_ids(session, node_ids_to_fetch)
                    _merge_nodes(nodes_by_id, fetched_nodes)

                candidate_nodes: list[Node] = []
                if resolved_workspace_id is not None:
                    if explicit_node_handles:
                        handle_nodes = await _fetch_nodes_by_compact_labels(
                            session,
                            resolved_workspace_id,
                            explicit_node_handles,
                        )
                        _merge_nodes(nodes_by_id, handle_nodes)
                    if explicit_named_entities:
                        entity_nodes = await _fetch_nodes_by_compact_labels(
                            session,
                            resolved_workspace_id,
                            explicit_named_entities,
                        )
                        _merge_nodes(nodes_by_id, entity_nodes)
                    candidate_nodes = await _fetch_candidate_nodes(
                        session,
                        resolved_workspace_id,
                        limit=self._config.candidate_node_limit,
                    )
                    _merge_nodes(nodes_by_id, candidate_nodes)

                if payload.attachments:
                    attachment_rows = await _fetch_attachments_by_ids(
                        session, payload.attachments
                    )
                    attachment_map = {attachment.id: attachment for attachment in attachment_rows}
                    for attachment_id in payload.attachments:
                        attachment = attachment_map.get(attachment_id)
                        if attachment is None:
                            continue
                        attachment_context.append(
                            ContextAttachment(
                                id=attachment.id,
                                filename=attachment.filename,
                                attachment_type=attachment.attachment_type,
                                mime_type=attachment.mime_type,
                                size_bytes=attachment.size_bytes,
                                text_content=attachment.text_content,
                                transcription=attachment.transcription,
                                description=attachment.description,
                                status=attachment.status,
                            )
                        )

        expanded_node_refs = {str(node_id) for node_id in expanded_node_ids}
        memory_signal = self._resolve_memory_signal(
            user_id=user_id,
            text=payload.text,
            workspace_id=resolved_workspace_id,
            session_id=session_id,
        )

        resolved_handle_ids, unresolved_handles = _resolve_handle_refs(
            explicit_node_handles,
            nodes_by_id,
        )
        explicit_node_ids.update(resolved_handle_ids)

        resolved_entity_ids, unresolved_entities = _resolve_named_entity_refs(
            explicit_named_entities,
            nodes_by_id,
        )
        explicit_node_ids.update(resolved_entity_ids)

        if unresolved_handles or unresolved_entities:
            async with AsyncSessionLocal() as session:
                if resolved_workspace_id is None and session_id:
                    session_repo = AsyncSessionRepository(session)
                    session_row = await session_repo.get_by_session_id(session_id)
                    if session_row is not None:
                        resolved_workspace_id = session_row.workspace_id
                if resolved_workspace_id is not None:
                    if unresolved_handles:
                        handle_nodes = await _fetch_nodes_by_compact_labels(
                            session,
                            resolved_workspace_id,
                            unresolved_handles,
                        )
                        _merge_nodes(nodes_by_id, handle_nodes)
                        explicit_node_ids.update(
                            _resolve_handle_refs(unresolved_handles, nodes_by_id)[0]
                        )
                    if unresolved_entities:
                        entity_nodes = await _fetch_nodes_by_compact_labels(
                            session,
                            resolved_workspace_id,
                            unresolved_entities,
                        )
                        _merge_nodes(nodes_by_id, entity_nodes)
                        explicit_node_ids.update(
                            _resolve_named_entity_refs(unresolved_entities, nodes_by_id)[0]
                        )

        for node_id in [*selected_ids, *explicit_node_ids]:
            if node_id not in nodes_by_id:
                nodes_by_id[node_id] = ContextNode(
                    id=node_id,
                    title=f"Node {node_id}",
                    node_type="text",
                )

        node_similarity = self._compute_similarity_scores(
            payload.text,
            {node_id: _node_text(node) for node_id, node in nodes_by_id.items()},
        )

        node_recency = _build_node_recency(recent_turns, decay=self._config.recency_decay)

        for node_id, node in nodes_by_id.items():
            if node_id in selected_ids:
                _apply_reason(node, self._config.selection_weight, "selected")
            if primary_id is not None and node_id == primary_id:
                node.is_primary = True
                _apply_reason(node, self._config.primary_weight, "primary")
            if node_id in explicit_node_ids:
                _apply_reason(node, self._config.explicit_weight, "explicit_reference")
            if (
                node_id in expanded_node_refs
                and node_id not in selected_ids
                and node_id not in explicit_node_ids
            ):
                _apply_reason(node, self._config.expansion_weight, "expanded")

            similarity = node_similarity.get(node_id, 0.0)
            node.similarity = similarity
            if similarity >= self._config.similarity_threshold:
                _apply_reason(
                    node,
                    similarity * self._config.similarity_weight,
                    f"semantic_match:{similarity:.2f}",
                )

            recency = node_recency.get(node_id)
            node.recency = recency
            if recency is not None:
                _apply_reason(
                    node,
                    recency * self._config.recency_weight,
                    "recent_turn",
                )

            if memory_signal:
                overlap = _token_overlap(
                    memory_signal.tokens,
                    _tokenize(_node_text(node)),
                )
                if overlap > 0:
                    _apply_reason(
                        node,
                        overlap * memory_signal.score * self._config.memory_weight,
                        "intent_memory",
                    )

        scored_turns = _score_turns(
            recent_turns=recent_turns,
            explicit_turns=explicit_turns,
            input_text=payload.text,
            config=self._config,
            memory_signal=memory_signal,
            embedding_provider=self._embedding_provider,
        )

        ordered_nodes = _select_nodes(
            nodes_by_id,
            selected_ids=selected_ids,
            primary_id=primary_id,
            explicit_ids=explicit_node_ids,
            limit=self._config.max_nodes,
        )
        ordered_turns = _select_turns(
            scored_turns,
            explicit_turn_ids,
            limit=self._config.max_turns,
        )

        return ContextWindow(
            input_text=payload.text,
            nodes=ordered_nodes,
            turns=ordered_turns,
            attachments=attachment_context,
            selection=selection,
            explicit_node_refs=sorted(explicit_node_ids),
            explicit_turn_refs=sorted(explicit_turn_ids),
        )

    def _resolve_memory_signal(
        self,
        *,
        user_id: str | None,
        text: str,
        workspace_id: int | None,
        session_id: str | None,
    ) -> _MemorySignal | None:
        if user_id is None:
            return None
        store = self._intent_memory_store
        if store is None and get_intent_memory_store is not None:
            try:
                store = get_intent_memory_store()
            except Exception:
                store = None
        if store is None:
            return None
        match = store.match_classification(
            user_id=user_id,
            text=text,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        if match is None:
            return None
        tokens = set(_tokenize(match.entry.trigger))
        response = match.entry.response
        if isinstance(response, str):
            tokens.update(_tokenize(response))
        elif isinstance(response, Mapping):
            for value in response.values():
                if isinstance(value, str):
                    tokens.update(_tokenize(value))
        if not tokens:
            return None
        return _MemorySignal(tokens=tokens, score=match.score, reason=match.reason)

    def _compute_similarity_scores(
        self,
        input_text: str,
        candidates: dict[str, str],
    ) -> dict[str, float]:
        if not input_text.strip():
            return {key: 0.0 for key in candidates}
        if not candidates:
            return {}

        input_tokens = _tokenize(input_text)
        if not input_tokens:
            return {key: 0.0 for key in candidates}

        input_embedding = None
        if self._embedding_provider is not None:
            try:
                input_embedding = _coerce_embedding(self._embedding_provider(input_text))
            except Exception:
                input_embedding = None

        scores: dict[str, float] = {}
        embedding_cache: dict[str, list[float] | None] = {}
        for key, text in candidates.items():
            if not text:
                scores[key] = 0.0
                continue
            score = 0.0
            if input_embedding is not None and self._embedding_provider is not None:
                embedding = embedding_cache.get(text)
                if embedding is None and text not in embedding_cache:
                    try:
                        embedding = _coerce_embedding(self._embedding_provider(text))
                    except Exception:
                        embedding = None
                    embedding_cache[text] = embedding
                score = _cosine_similarity(input_embedding, embedding)
            if score <= 0.0:
                score = _token_similarity(input_tokens, _tokenize(text))
            scores[key] = score
        return scores


def _coerce_int(value: int | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _normalize_compact(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "", value.lower())
    return cleaned.strip()


def _build_compact_index(nodes_by_id: dict[str, ContextNode]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for node in nodes_by_id.values():
        if not node.title:
            continue
        key = _normalize_compact(node.title)
        if not key:
            continue
        index.setdefault(key, []).append(node.id)
    return index


def _resolve_handle_refs(
    handles: set[str],
    nodes_by_id: dict[str, ContextNode],
) -> tuple[set[str], set[str]]:
    if not handles:
        return set(), set()
    index = _build_compact_index(nodes_by_id)
    resolved: set[str] = set()
    unresolved: set[str] = set()
    for handle in handles:
        key = _normalize_compact(handle)
        matches = index.get(key)
        if matches:
            resolved.update(matches)
        else:
            unresolved.add(handle)
    return resolved, unresolved


def _resolve_named_entity_refs(
    entities: set[str],
    nodes_by_id: dict[str, ContextNode],
) -> tuple[set[str], set[str]]:
    if not entities:
        return set(), set()
    index = _build_compact_index(nodes_by_id)
    resolved: set[str] = set()
    unresolved: set[str] = set()
    for entity in entities:
        key = _normalize_compact(entity)
        matches = index.get(key)
        if matches:
            resolved.update(matches)
        else:
            unresolved.add(entity)
    return resolved, unresolved


async def _fetch_nodes_by_ids(
    session: Any,
    node_ids: Iterable[int],
) -> list[Node]:
    ids = sorted({int(node_id) for node_id in node_ids if node_id is not None})
    if not ids:
        return []
    result = await session.execute(select(Node).where(Node.id.in_(ids)))
    return list(result.scalars().all())


async def _fetch_nodes_by_compact_labels(
    session: Any,
    canvas_id: int,
    labels: Iterable[str],
) -> list[Node]:
    values = {_normalize_compact(label) for label in labels if label}
    if not values:
        return []
    label_expr = func.lower(Node.label)
    for token in (" ", "-", "_"):
        label_expr = func.replace(label_expr, token, "")
    result = await session.execute(
        select(Node).where(Node.canvas_id == canvas_id, label_expr.in_(sorted(values)))
    )
    return list(result.scalars().all())


async def _fetch_expanded_node_ids(
    session: Any,
    canvas_id: int,
    selected_node_ids: Iterable[int],
    selected_edge_ids: Iterable[int],
    *,
    limit: int,
) -> set[int]:
    if limit <= 0:
        return set()
    node_ids = {int(node_id) for node_id in selected_node_ids if node_id is not None}
    edge_ids = {int(edge_id) for edge_id in selected_edge_ids if edge_id is not None}
    if not node_ids and not edge_ids:
        return set()
    filters = []
    if edge_ids:
        filters.append(Edge.id.in_(sorted(edge_ids)))
    if node_ids:
        filters.append(Edge.from_node_id.in_(sorted(node_ids)))
        filters.append(Edge.to_node_id.in_(sorted(node_ids)))
    if not filters:
        return set()
    result = await session.execute(
        select(Edge)
        .where(Edge.canvas_id == canvas_id, or_(*filters))
        .order_by(Edge.id.desc())
    )
    expanded: list[int] = []
    seen: set[int] = set(node_ids)
    for edge in result.scalars().all():
        for node_id in (edge.from_node_id, edge.to_node_id):
            if node_id in seen:
                continue
            seen.add(node_id)
            expanded.append(node_id)
            if len(expanded) >= limit:
                return set(expanded)
    return set(expanded)


async def _fetch_candidate_nodes(
    session: Any,
    canvas_id: int,
    *,
    limit: int,
) -> list[Node]:
    if limit <= 0:
        return []
    result = await session.execute(
        select(Node).where(Node.canvas_id == canvas_id).order_by(Node.id.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def _fetch_recent_turns(
    session: Any,
    session_id: str,
    *,
    limit: int,
) -> list[Turn]:
    if limit <= 0:
        return []
    result = await session.execute(
        select(Turn)
        .where(Turn.session_id == session_id)
        .order_by(Turn.sequence_number.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _fetch_turns_by_sequence(
    session: Any,
    session_id: str,
    sequence_numbers: set[int],
) -> list[Turn]:
    if not sequence_numbers:
        return []
    result = await session.execute(
        select(Turn).where(
            Turn.session_id == session_id,
            Turn.sequence_number.in_(sorted(sequence_numbers)),
        )
    )
    return list(result.scalars().all())


async def _fetch_attachments_by_ids(
    session: Any,
    attachment_ids: Iterable[str],
) -> list[AttachmentDB]:
    ids = [str(item) for item in attachment_ids if item]
    if not ids:
        return []
    result = await session.execute(select(AttachmentDB).where(AttachmentDB.id.in_(ids)))
    return list(result.scalars().all())


def _merge_nodes(nodes_by_id: dict[str, ContextNode], nodes: Iterable[Node]) -> None:
    for node in nodes:
        node_id = str(node.id)
        existing = nodes_by_id.get(node_id)
        metadata = node.get_metadata() if hasattr(node, "get_metadata") else {}
        content = getattr(node, "content", None)
        if not content and isinstance(metadata, Mapping):
            content = metadata.get("content")
        if not content:
            content = node.label
        if existing is None:
            nodes_by_id[node_id] = ContextNode(
                id=node_id,
                title=node.label or f"Node {node_id}",
                node_type=getattr(node.type, "value", node.type),
                content=content,
                metadata=metadata if metadata else None,
            )
        else:
            if not existing.title:
                existing.title = node.label or existing.title
            if existing.content is None:
                existing.content = content
            if existing.metadata is None and metadata:
                existing.metadata = metadata


def _build_node_recency(turns: Iterable[Turn], *, decay: float) -> dict[str, float]:
    if decay <= 0 or decay >= 1:
        decay = 0.9
    latest_seq = None
    recency: dict[str, float] = {}
    for turn in turns:
        if latest_seq is None or turn.sequence_number > latest_seq:
            latest_seq = turn.sequence_number
    if latest_seq is None:
        return recency
    for turn in turns:
        if turn.related_node_id is None:
            continue
        steps = max(0, latest_seq - turn.sequence_number)
        weight = decay**steps
        node_id = str(turn.related_node_id)
        existing = recency.get(node_id)
        if existing is None or weight > existing:
            recency[node_id] = weight
    return recency


def _score_turns(
    *,
    recent_turns: list[Turn],
    explicit_turns: list[Turn],
    input_text: str,
    config: ContextAssemblyConfig,
    memory_signal: _MemorySignal | None,
    embedding_provider: EmbeddingProvider | None,
) -> dict[int, ContextTurn]:
    turns_by_seq: dict[int, ContextTurn] = {}
    all_turns = {turn.sequence_number: turn for turn in recent_turns}
    for turn in explicit_turns:
        all_turns.setdefault(turn.sequence_number, turn)
    explicit_seq = {turn.sequence_number for turn in explicit_turns}

    if not all_turns:
        return turns_by_seq

    latest_seq = max(all_turns)
    input_tokens = _tokenize(input_text)
    input_embedding = None
    if embedding_provider is not None:
        try:
            input_embedding = _coerce_embedding(embedding_provider(input_text))
        except Exception:
            input_embedding = None

    for seq, turn in all_turns.items():
        summary_text = _resolve_turn_summary(turn)
        context_turn = ContextTurn(
            id=turn.id,
            sequence_number=turn.sequence_number,
            summary=summary_text,
            actor=turn.actor,
            turn_type=turn.type,
            timestamp=turn.timestamp.isoformat() if turn.timestamp else "",
        )

        steps = max(0, latest_seq - turn.sequence_number)
        recency = config.recency_decay**steps
        context_turn.recency = recency
        _apply_reason(
            context_turn,
            recency * config.recency_weight,
            "recent_turn",
        )

        if turn.sequence_number in explicit_seq:
            _apply_reason(context_turn, config.explicit_weight, "explicit_reference")

        similarity = 0.0
        if input_embedding is not None and embedding_provider is not None:
            try:
                embedding = _coerce_embedding(embedding_provider(summary_text))
            except Exception:
                embedding = None
            similarity = _cosine_similarity(input_embedding, embedding)
        if similarity <= 0.0 and input_tokens:
            similarity = _token_similarity(input_tokens, _tokenize(summary_text))
        context_turn.similarity = similarity
        if similarity >= config.similarity_threshold:
            _apply_reason(
                context_turn,
                similarity * config.similarity_weight,
                f"semantic_match:{similarity:.2f}",
            )

        if memory_signal:
            overlap = _token_overlap(memory_signal.tokens, _tokenize(summary_text))
            if overlap > 0:
                _apply_reason(
                    context_turn,
                    overlap * memory_signal.score * config.memory_weight,
                    "intent_memory",
                )

        turns_by_seq[seq] = context_turn

    return turns_by_seq


def _select_nodes(
    nodes_by_id: dict[str, ContextNode],
    *,
    selected_ids: list[str],
    primary_id: str | None,
    explicit_ids: set[str],
    limit: int,
) -> list[ContextNode]:
    if limit <= 0:
        return []
    ranked = sorted(nodes_by_id.values(), key=lambda node: node.score, reverse=True)
    ordered: list[ContextNode] = []
    selected_order = list(selected_ids)
    if primary_id and primary_id in selected_order:
        selected_order.remove(primary_id)
        selected_order.insert(0, primary_id)

    for node_id in selected_order:
        node = nodes_by_id.get(node_id)
        if node and node not in ordered:
            ordered.append(node)
        if len(ordered) >= limit:
            return ordered

    for node_id in sorted(explicit_ids):
        node = nodes_by_id.get(node_id)
        if node and node not in ordered:
            ordered.append(node)
        if len(ordered) >= limit:
            return ordered

    for node in ranked:
        if node in ordered:
            continue
        ordered.append(node)
        if len(ordered) >= limit:
            break

    return ordered


def _select_turns(
    turns_by_seq: dict[int, ContextTurn],
    explicit_turns: set[int],
    *,
    limit: int,
) -> list[ContextTurn]:
    if limit <= 0:
        return []
    ordered: list[ContextTurn] = []
    for seq in sorted(explicit_turns, reverse=True):
        turn = turns_by_seq.get(seq)
        if turn and turn not in ordered:
            ordered.append(turn)
        if len(ordered) >= limit:
            return ordered
    ranked = sorted(turns_by_seq.values(), key=lambda turn: turn.score, reverse=True)
    for turn in ranked:
        if turn in ordered:
            continue
        ordered.append(turn)
        if len(ordered) >= limit:
            break
    return ordered


def _apply_reason(target: Any, score: float, reason: str) -> None:
    if score <= 0:
        return
    target.score += score
    if reason not in target.reasons:
        target.reasons.append(reason)
    reason_scores = getattr(target, "reason_scores", None)
    if isinstance(reason_scores, dict):
        reason_scores[reason] = reason_scores.get(reason, 0.0) + score


def _node_text(node: ContextNode) -> str:
    parts = [node.title]
    if node.content and node.content != node.title:
        parts.append(node.content)
    if node.metadata:
        summary = node.metadata.get("summary") if isinstance(node.metadata, Mapping) else None
        if isinstance(summary, str):
            parts.append(summary)
    return " ".join(part for part in parts if part)


def _extract_payload_text(payload: Mapping[str, Any]) -> str | None:
    if isinstance(payload.get("title"), str) and isinstance(payload.get("message"), str):
        return f"{payload['title']}: {payload['message']}"
    candidates = [
        payload.get("message"),
        payload.get("status"),
        payload.get("error"),
        payload.get("prompt"),
        payload.get("text"),
        payload.get("content"),
        payload.get("result"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            return candidate
    nested = payload.get("result")
    if isinstance(nested, Mapping):
        return _extract_payload_text(nested)
    return None


def _resolve_turn_summary(turn: Turn) -> str:
    payload = turn.get_payload()
    if turn.type == TurnType.USER_INPUT:
        command = payload.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
    if turn.type == TurnType.ASSUMPTION_CONFIRMED:
        final_text = payload.get("final_text")
        if isinstance(final_text, str) and final_text.strip():
            return f"Clarification confirmed: {final_text.strip()}"
    if turn.type == TurnType.ASSUMPTION_REJECTED:
        original_text = payload.get("original_text")
        if isinstance(original_text, str) and original_text.strip():
            return f"Clarification rejected: {original_text.strip()}"
    if turn.type == TurnType.ASSUMPTION_MODIFIED:
        final_text = payload.get("final_text")
        if isinstance(final_text, str) and final_text.strip():
            return f"Clarification updated: {final_text.strip()}"
    payload_text = _extract_payload_text(payload)
    if payload_text and payload_text.strip():
        return payload_text.strip()
    return turn.summary


def _format_node_lines(nodes: Iterable[ContextNode], max_content_chars: int) -> list[str]:
    lines: list[str] = []
    for node in nodes:
        content = node.content or ""
        content = content if content != node.title else ""
        detail = _clip_text(content, max_content_chars)
        if detail:
            lines.append(f"- [node {node.id}] {node.title}: {detail}")
        else:
            lines.append(f"- [node {node.id}] {node.title}")
    return lines


def _format_turn_lines(turns: Iterable[ContextTurn], max_content_chars: int) -> list[str]:
    lines: list[str] = []
    for turn in turns:
        summary = _clip_text(turn.summary, max_content_chars)
        lines.append(
            f"- [turn {turn.sequence_number}] {turn.actor}/{turn.turn_type}: {summary}"
        )
    return lines


def _format_attachment_lines(
    attachments: Iterable[ContextAttachment], max_content_chars: int
) -> list[str]:
    lines: list[str] = []
    for attachment in attachments:
        details: list[str] = []
        if attachment.attachment_type:
            details.append(attachment.attachment_type)
        if attachment.mime_type:
            details.append(attachment.mime_type)
        if attachment.size_bytes:
            details.append(f"{attachment.size_bytes} bytes")
        detail_suffix = f" ({', '.join(details)})" if details else ""

        summary_source = (
            attachment.text_content
            or attachment.transcription
            or attachment.description
            or ""
        )
        summary = _clip_text(summary_source, max_content_chars)
        if summary:
            lines.append(
                f"- [attachment {attachment.id}] {attachment.filename}{detail_suffix}: {summary}"
            )
        else:
            lines.append(
                f"- [attachment {attachment.id}] {attachment.filename}{detail_suffix}"
            )
    return lines


def _clip_text(text: str, limit: int) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: max(0, limit - 3)].rstrip()}..."


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _token_similarity(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    left_set = set(left)
    right_set = set(right)
    overlap = left_set & right_set
    union = left_set | right_set
    if not union:
        return 0.0
    return len(overlap) / len(union)


def _token_overlap(tokens: set[str], candidate_tokens: list[str]) -> float:
    if not tokens or not candidate_tokens:
        return 0.0
    candidate_set = set(candidate_tokens)
    overlap = tokens & candidate_set
    return len(overlap) / len(tokens)


def _coerce_embedding(value: Sequence[float] | None) -> list[float] | None:
    if value is None:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


def _cosine_similarity(left: Sequence[float] | None, right: Sequence[float] | None) -> float:
    if not left or not right:
        return 0.0
    if len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    return dot / (left_norm * right_norm)


_assembler: ContextAssembler | None = None


def get_context_assembler(
    *,
    config: ContextAssemblyConfig | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    intent_memory_store: IntentMemoryStore | None = None,
    force_new: bool = False,
) -> ContextAssembler:
    """Get singleton context assembler instance."""
    global _assembler
    if _assembler is None or force_new:
        _assembler = ContextAssembler(
            config=config,
            embedding_provider=embedding_provider,
            intent_memory_store=intent_memory_store,
        )
    return _assembler
