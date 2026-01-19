"""Intent memory storage and lookup.

Stores user intent memory in Markdown files (Obsidian-style) with frontmatter
metadata. Supports explicit rules, implicit learning, and confirmation patterns
across user/workspace/session scopes.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9]+")
_SCOPE_SESSION_RE = re.compile(r"\b(for|this)\s+session( only)?\b", re.I)
_SCOPE_WORKSPACE_RE = re.compile(r"\b(for|this)\s+(workspace|canvas)( only)?\b", re.I)
_EXPLICIT_RULE_RE = re.compile(
    r"(?:when|whenever)\s+i\s+(?:say|do|ask|type)?\s*(?P<trigger>.+?)"
    r"(?:,|\bthen\b)?\s*(?:always|please)?\s*"
    r"(?:respond with|reply with|route to|treat it as|handle it as|classify it as|do)\s+"
    r"(?P<response>.+)",
    re.I,
)
_SUGGEST_RULE_RE = re.compile(
    r"(?:when|whenever)\s+i\s+(?:note|write|capture|log)\s+(?P<trigger>.+?)"
    r"(?:,|\bthen\b)?\s*(?:suggest|recommend)\s+(?P<response>.+)",
    re.I,
)

_SLASH_COMMAND_HANDLERS = {
    "/research": "research_handler",
    "/help": "help_handler",
    "/clear": "clear_handler",
    "/plan": "plan_handler",
    "/judge": "judge_handler",
    "/dashboard": "dashboard_handler",
    "/graph": "graph_handler",
    "/export": "export_handler",
    "/calendar": "calendar_handler",
}

_INTENT_HANDLER_MAP = {
    "research": "research_handler",
    "help": "help_handler",
    "clear": "clear_handler",
    "plan": "plan_handler",
    "judge": "judge_handler",
    "dashboard": "dashboard_handler",
    "graph": "graph_handler",
    "export": "export_handler",
    "calendar": "calendar_handler",
    "create": "create_handler",
    "analyze": "analyze_handler",
    "chat": "chat_handler",
    "note": "note_handler",
}


class MemoryScope(str, Enum):
    """Scopes for intent memory entries."""

    USER = "user"
    WORKSPACE = "workspace"
    SESSION = "session"


class MemoryKind(str, Enum):
    """Learning sources for intent memory."""

    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
    CONFIRMATION = "confirmation"


class MemoryUsage(str, Enum):
    """How a memory entry should be applied."""

    CLASSIFICATION = "classification"
    ROUTING = "routing"
    AUTO_CONFIRM = "auto_confirm"
    NOTE_SUGGESTION = "note_suggestion"


@dataclass
class MemoryStats:
    """Usage statistics for a memory entry."""

    total: int = 0
    accepted: int = 0
    rejected: int = 0
    last_used_at: str | None = None


@dataclass
class MemoryEntry:
    """Stored memory entry."""

    entry_id: str
    scope: MemoryScope
    kind: MemoryKind
    usage: MemoryUsage
    trigger: str
    trigger_type: str = "contains"
    response: Any = None
    confidence: float = 0.0
    enabled: bool = True
    workspace_id: str | None = None
    session_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    stats: MemoryStats = field(default_factory=MemoryStats)
    description: str | None = None


@dataclass
class MemoryMatch:
    """Match details for applying memory entries."""

    entry: MemoryEntry
    score: float
    reason: str


@dataclass
class IntentMemorySettings:
    """Per-user memory settings."""

    enabled: bool = True
    auto_classify_enabled: bool = True
    auto_confirm_enabled: bool = True
    suggestions_enabled: bool = True
    auto_classify_threshold: float = 0.7
    auto_confirm_threshold: float = 0.8
    auto_confirm_min_samples: int = 3
    auto_confirm_similarity_threshold: float = 0.85
    note_suggestion_threshold: float = 0.6


@dataclass
class IntentMemoryPolicy:
    """Thresholds and tunables for memory decisions."""

    auto_classify_threshold: float = 0.7
    auto_confirm_threshold: float = 0.8
    auto_confirm_min_samples: int = 3
    auto_confirm_similarity_threshold: float = 0.85
    note_suggestion_threshold: float = 0.6


@dataclass
class ExplicitRuleResult:
    """Outcome of parsing an explicit memory rule."""

    entry: MemoryEntry
    acknowledgement: str


def _normalize_text(text: str) -> str:
    tokens = _WORD_RE.findall(text.lower())
    return " ".join(tokens)


def _sanitize_component(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
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


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", raw):
        try:
            return int(raw)
        except ValueError:
            return raw
    if re.fullmatch(r"-?\d+\.\d+", raw):
        try:
            return float(raw)
        except ValueError:
            return raw
    if raw[0] in "[{\"" and raw[-1] in "]}\"":
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _coerce_threshold(value: Any, default: float) -> float:
    parsed = _coerce_float(value)
    if parsed is None or parsed < 0.0 or parsed > 1.0:
        return default
    return parsed


def _coerce_min_samples(value: Any, default: int) -> int:
    parsed = _coerce_int(value)
    if parsed is None or parsed < 1:
        return default
    return parsed


def _parse_frontmatter(contents: str) -> tuple[dict[str, Any], str]:
    if not contents.startswith("---"):
        return {}, contents
    lines = contents.splitlines()
    if len(lines) < 3:
        return {}, contents
    try:
        end_index = lines[1:].index("---") + 1
    except ValueError:
        return {}, contents
    frontmatter_lines = lines[1:end_index]
    body_lines = lines[end_index + 1 :]
    data: dict[str, Any] = {}
    for line in frontmatter_lines:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        data[key.strip()] = _parse_value(value)
    return data, "\n".join(body_lines)


def _format_response(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    return json.dumps(response, indent=2, ensure_ascii=True, sort_keys=True)


def _extract_scope_hint(text: str) -> tuple[MemoryScope | None, str]:
    cleaned = text
    if _SCOPE_SESSION_RE.search(cleaned):
        cleaned = _SCOPE_SESSION_RE.sub("", cleaned)
        return MemoryScope.SESSION, cleaned.strip()
    if _SCOPE_WORKSPACE_RE.search(cleaned):
        cleaned = _SCOPE_WORKSPACE_RE.sub("", cleaned)
        return MemoryScope.WORKSPACE, cleaned.strip()
    return None, cleaned.strip()


def _parse_suggestions(response: str) -> list[str]:
    parts = re.split(r"\s+and\s+|,\s*", response)
    suggestions = [part.strip(" .") for part in parts if part.strip(" .")]
    return suggestions or [response.strip()]


def _interpret_response(response_text: str) -> tuple[MemoryUsage | None, Any]:
    normalized = response_text.strip()
    if not normalized:
        return None, None
    lower = normalized.lower()
    if lower.startswith("/"):
        handler = _SLASH_COMMAND_HANDLERS.get(lower)
        if handler:
            return MemoryUsage.ROUTING, {"handler": handler, "intent": lower.lstrip("/")}
    handler = _INTENT_HANDLER_MAP.get(lower)
    if handler:
        if handler == "note_handler":
            return MemoryUsage.CLASSIFICATION, {"classification": "note"}
        if handler == "chat_handler":
            return MemoryUsage.CLASSIFICATION, {"classification": "question"}
        return MemoryUsage.ROUTING, {"handler": handler, "intent": lower}
    if "note" in lower or "memo" in lower or "eureka" in lower:
        return MemoryUsage.CLASSIFICATION, {"classification": "note"}
    if "configure" in lower or "setting" in lower or "preference" in lower:
        return MemoryUsage.CLASSIFICATION, {"classification": "configuration"}
    if "clarify" in lower:
        return MemoryUsage.CLASSIFICATION, {"classification": "clarification_response"}
    if "command" in lower or "execute" in lower:
        return MemoryUsage.CLASSIFICATION, {"classification": "command"}
    return None, None


class IntentMemoryStore:
    """Intent memory persistence for markdown-backed entries."""

    def __init__(
        self,
        *,
        base_path: str | None = None,
        policy: IntentMemoryPolicy | None = None,
    ) -> None:
        settings = get_settings()
        self._base_path = Path(base_path or settings.intent_memory_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._policy = policy or IntentMemoryPolicy(
            auto_classify_threshold=settings.intent_memory_auto_classify_threshold,
            auto_confirm_threshold=settings.intent_memory_auto_confirm_threshold,
            auto_confirm_min_samples=settings.intent_memory_auto_confirm_min_samples,
            auto_confirm_similarity_threshold=(
                settings.intent_memory_auto_confirm_similarity_threshold
            ),
            note_suggestion_threshold=settings.intent_memory_note_suggestion_threshold,
        )
        self._default_settings = IntentMemorySettings(
            enabled=settings.intent_memory_enabled,
            auto_classify_enabled=settings.intent_memory_auto_classify_enabled,
            auto_confirm_enabled=settings.intent_memory_auto_confirm_enabled,
            suggestions_enabled=settings.intent_memory_suggestions_enabled,
            auto_classify_threshold=self._policy.auto_classify_threshold,
            auto_confirm_threshold=self._policy.auto_confirm_threshold,
            auto_confirm_min_samples=self._policy.auto_confirm_min_samples,
            auto_confirm_similarity_threshold=self._policy.auto_confirm_similarity_threshold,
            note_suggestion_threshold=self._policy.note_suggestion_threshold,
        )

    def get_settings(self, user_id: str) -> IntentMemorySettings:
        path = self._user_dir(user_id) / "settings.md"
        if not path.exists():
            return self._default_settings
        try:
            contents = path.read_text(encoding="utf-8")
        except Exception:
            logger.warning("Failed to read intent memory settings", exc_info=True)
            return self._default_settings
        data, _body = _parse_frontmatter(contents)
        return IntentMemorySettings(
            enabled=bool(data.get("enabled", self._default_settings.enabled)),
            auto_classify_enabled=bool(
                data.get("auto_classify", self._default_settings.auto_classify_enabled)
            ),
            auto_confirm_enabled=bool(
                data.get("auto_confirm", self._default_settings.auto_confirm_enabled)
            ),
            suggestions_enabled=bool(
                data.get("suggestions", self._default_settings.suggestions_enabled)
            ),
            auto_classify_threshold=_coerce_threshold(
                data.get("auto_classify_threshold"),
                self._default_settings.auto_classify_threshold,
            ),
            auto_confirm_threshold=_coerce_threshold(
                data.get("auto_confirm_threshold"),
                self._default_settings.auto_confirm_threshold,
            ),
            auto_confirm_min_samples=_coerce_min_samples(
                data.get("auto_confirm_min_samples"),
                self._default_settings.auto_confirm_min_samples,
            ),
            auto_confirm_similarity_threshold=_coerce_threshold(
                data.get("auto_confirm_similarity_threshold"),
                self._default_settings.auto_confirm_similarity_threshold,
            ),
            note_suggestion_threshold=_coerce_threshold(
                data.get("note_suggestion_threshold"),
                self._default_settings.note_suggestion_threshold,
            ),
        )

    def update_settings(self, user_id: str, updates: dict[str, Any]) -> IntentMemorySettings:
        current = self.get_settings(user_id)
        updated = IntentMemorySettings(
            enabled=updates["enabled"] if "enabled" in updates else current.enabled,
            auto_classify_enabled=updates["auto_classify_enabled"]
            if "auto_classify_enabled" in updates
            else current.auto_classify_enabled,
            auto_confirm_enabled=updates["auto_confirm_enabled"]
            if "auto_confirm_enabled" in updates
            else current.auto_confirm_enabled,
            suggestions_enabled=updates["suggestions_enabled"]
            if "suggestions_enabled" in updates
            else current.suggestions_enabled,
            auto_classify_threshold=updates["auto_classify_threshold"]
            if "auto_classify_threshold" in updates
            else current.auto_classify_threshold,
            auto_confirm_threshold=updates["auto_confirm_threshold"]
            if "auto_confirm_threshold" in updates
            else current.auto_confirm_threshold,
            auto_confirm_min_samples=updates["auto_confirm_min_samples"]
            if "auto_confirm_min_samples" in updates
            else current.auto_confirm_min_samples,
            auto_confirm_similarity_threshold=updates["auto_confirm_similarity_threshold"]
            if "auto_confirm_similarity_threshold" in updates
            else current.auto_confirm_similarity_threshold,
            note_suggestion_threshold=updates["note_suggestion_threshold"]
            if "note_suggestion_threshold" in updates
            else current.note_suggestion_threshold,
        )
        self._write_settings_file(user_id, updated)
        return updated

    def get_policy(self, user_id: str) -> IntentMemoryPolicy:
        settings = self.get_settings(user_id)
        return IntentMemoryPolicy(
            auto_classify_threshold=settings.auto_classify_threshold,
            auto_confirm_threshold=settings.auto_confirm_threshold,
            auto_confirm_min_samples=settings.auto_confirm_min_samples,
            auto_confirm_similarity_threshold=settings.auto_confirm_similarity_threshold,
            note_suggestion_threshold=settings.note_suggestion_threshold,
        )

    def list_entries(
        self,
        *,
        user_id: str,
        workspace_id: str | int | None = None,
        session_id: str | None = None,
    ) -> list[MemoryEntry]:
        return self._load_entries(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )

    def get_entry(
        self,
        *,
        user_id: str,
        entry_id: str,
        workspace_id: str | int | None = None,
        session_id: str | None = None,
    ) -> MemoryEntry | None:
        entries = self._load_entries(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry
        return None

    def save_entry(self, *, user_id: str, entry: MemoryEntry, previous: MemoryEntry | None) -> None:
        previous_path = self._entry_path(user_id=user_id, entry=previous) if previous else None
        self._persist_entry(user_id, entry)
        if previous_path and previous_path != self._entry_path(user_id=user_id, entry=entry):
            if previous_path.exists():
                previous_path.unlink()

    def delete_entry(
        self,
        *,
        user_id: str,
        entry: MemoryEntry,
    ) -> bool:
        path = self._entry_path(user_id=user_id, entry=entry)
        if not path.exists():
            return False
        path.unlink()
        return True

    def match_routing(
        self,
        *,
        user_id: str,
        text: str,
        workspace_id: str | int | None = None,
        session_id: str | None = None,
    ) -> MemoryMatch | None:
        policy = self.get_policy(user_id)
        return self._match_entries(
            usage=MemoryUsage.ROUTING,
            user_id=user_id,
            text=text,
            workspace_id=workspace_id,
            session_id=session_id,
            threshold=policy.auto_classify_threshold,
        )

    def match_classification(
        self,
        *,
        user_id: str,
        text: str,
        workspace_id: str | int | None = None,
        session_id: str | None = None,
    ) -> MemoryMatch | None:
        policy = self.get_policy(user_id)
        match = self._match_entries(
            usage=MemoryUsage.CLASSIFICATION,
            user_id=user_id,
            text=text,
            workspace_id=workspace_id,
            session_id=session_id,
            threshold=policy.auto_classify_threshold,
        )
        if match is not None:
            return match
        return self._match_entries(
            usage=MemoryUsage.ROUTING,
            user_id=user_id,
            text=text,
            workspace_id=workspace_id,
            session_id=session_id,
            threshold=policy.auto_classify_threshold,
        )

    def suggest_for_note(
        self,
        *,
        user_id: str,
        text: str,
        workspace_id: str | int | None = None,
        session_id: str | None = None,
    ) -> list[str]:
        settings = self.get_settings(user_id)
        if not settings.enabled or not settings.suggestions_enabled:
            return []
        policy = self.get_policy(user_id)
        matches = self._match_entries(
            usage=MemoryUsage.NOTE_SUGGESTION,
            user_id=user_id,
            text=text,
            workspace_id=workspace_id,
            session_id=session_id,
            threshold=policy.note_suggestion_threshold,
            collect_all=True,
        )
        if not matches:
            return []
        suggestions: list[str] = []
        for match in matches:
            response = match.entry.response
            if isinstance(response, dict):
                items = response.get("suggestions", [])
                if isinstance(items, list):
                    suggestions.extend(
                        [str(item).strip() for item in items if str(item).strip()]
                    )
            elif isinstance(response, list):
                suggestions.extend([str(item).strip() for item in response if str(item).strip()])
            elif isinstance(response, str):
                suggestions.append(response.strip())
            self._record_usage(match.entry, accepted=None)
            self.log_audit_event(
                user_id,
                "note_suggestion_applied",
                {
                    "entry_id": match.entry.entry_id,
                    "scope": match.entry.scope.value,
                    "trigger": match.entry.trigger,
                },
            )
        return sorted(set(suggestions))

    def auto_confirm_assumptions(
        self,
        *,
        user_id: str,
        assumptions: list[dict[str, Any]],
        workspace_id: str | int | None = None,
        session_id: str | None = None,
    ) -> tuple[list[tuple[dict[str, Any], MemoryEntry]], list[dict[str, Any]]]:
        settings = self.get_settings(user_id)
        if not settings.enabled or not settings.auto_confirm_enabled:
            return [], assumptions
        policy = self.get_policy(user_id)
        confirmed: list[tuple[dict[str, Any], MemoryEntry]] = []
        remaining: list[dict[str, Any]] = []
        for assumption in assumptions:
            text = str(assumption.get("text", "")).strip()
            category = str(assumption.get("category", "")).strip().lower()
            if not text or not category:
                remaining.append(assumption)
                continue
            match = self._match_assumption(
                user_id=user_id,
                assumption_text=text,
                category=category,
                workspace_id=workspace_id,
                session_id=session_id,
                policy=policy,
            )
            if match is None:
                remaining.append(assumption)
                continue
            if match.entry.stats.total < policy.auto_confirm_min_samples:
                remaining.append(assumption)
                continue
            if match.score < policy.auto_confirm_threshold:
                remaining.append(assumption)
                continue
            confirmed.append((assumption, match.entry))
            self._record_usage(match.entry, accepted=True)
            self.log_audit_event(
                user_id,
                "auto_confirm_applied",
                {
                    "entry_id": match.entry.entry_id,
                    "scope": match.entry.scope.value,
                    "trigger": match.entry.trigger,
                    "category": category,
                },
            )
        return confirmed, remaining

    def record_assumption_resolution(
        self,
        *,
        user_id: str,
        assumption_text: str,
        category: str,
        action: str,
        workspace_id: str | int | None = None,
        session_id: str | None = None,
    ) -> list[MemoryEntry]:
        settings = self.get_settings(user_id)
        if not settings.enabled:
            return []
        normalized_action = action.strip().lower()
        accepted = normalized_action == "accept"
        rejected = normalized_action in {"reject", "edit"}
        updated_entries: list[MemoryEntry] = []

        category_entry = self._get_or_create_entry(
            user_id=user_id,
            scope=MemoryScope.USER,
            kind=MemoryKind.IMPLICIT,
            usage=MemoryUsage.AUTO_CONFIRM,
            trigger=category.strip().lower(),
            trigger_type="category",
            response={"action": "accept", "category": category.strip().lower()},
            workspace_id=None,
            session_id=None,
        )
        self._update_stats(category_entry, accepted=accepted, rejected=rejected)
        updated_entries.append(category_entry)
        self._persist_entry(user_id, category_entry)

        scope = MemoryScope.WORKSPACE if workspace_id is not None else MemoryScope.USER
        text_entry = self._get_or_create_entry(
            user_id=user_id,
            scope=scope,
            kind=MemoryKind.CONFIRMATION,
            usage=MemoryUsage.AUTO_CONFIRM,
            trigger=assumption_text.strip(),
            trigger_type="similarity",
            response={"action": "accept", "category": category.strip().lower()},
            workspace_id=str(workspace_id) if workspace_id is not None else None,
            session_id=None,
        )
        self._update_stats(text_entry, accepted=accepted, rejected=rejected)
        updated_entries.append(text_entry)
        self._persist_entry(user_id, text_entry)

        return updated_entries

    def record_explicit_rule(
        self,
        *,
        user_id: str,
        text: str,
        workspace_id: str | int | None = None,
        session_id: str | None = None,
    ) -> ExplicitRuleResult | None:
        settings = self.get_settings(user_id)
        if not settings.enabled:
            return None
        scope_hint, cleaned = _extract_scope_hint(text)
        scope = scope_hint or MemoryScope.USER
        if scope == MemoryScope.WORKSPACE and workspace_id is None:
            scope = MemoryScope.USER
        if scope == MemoryScope.SESSION and session_id is None:
            scope = MemoryScope.USER
        target_workspace = str(workspace_id) if scope == MemoryScope.WORKSPACE else None
        target_session = session_id if scope == MemoryScope.SESSION else None
        match = _SUGGEST_RULE_RE.search(cleaned)
        if match:
            trigger = match.group("trigger").strip(" .")
            response = match.group("response").strip()
            suggestions = _parse_suggestions(response)
            entry = self._build_entry(
                user_id=user_id,
                scope=scope,
                kind=MemoryKind.EXPLICIT,
                usage=MemoryUsage.NOTE_SUGGESTION,
                trigger=trigger,
                trigger_type="contains",
                response={"suggestions": suggestions},
                confidence=0.95,
                workspace_id=target_workspace,
                session_id=target_session,
            )
            self._persist_entry(user_id, entry)
            ack = (
                f"Saved note suggestion rule ({scope.value} scope): "
                f"when '{trigger}' then suggest {', '.join(suggestions)}."
            )
            self.log_audit_event(
                user_id,
                "explicit_rule_created",
                {
                    "entry_id": entry.entry_id,
                    "scope": scope.value,
                    "trigger": trigger,
                    "usage": entry.usage.value,
                },
            )
            return ExplicitRuleResult(entry=entry, acknowledgement=ack)
        match = _EXPLICIT_RULE_RE.search(cleaned)
        if not match:
            return None
        trigger = match.group("trigger").strip(" .")
        response_text = match.group("response").strip()
        usage, response = _interpret_response(response_text)
        if usage is None:
            return None
        entry = self._build_entry(
            user_id=user_id,
            scope=scope,
            kind=MemoryKind.EXPLICIT,
            usage=usage,
            trigger=trigger,
            trigger_type="contains",
            response=response,
            confidence=0.95,
            workspace_id=target_workspace,
            session_id=target_session,
        )
        self._persist_entry(user_id, entry)
        ack = (
            f"Saved intent rule ({scope.value} scope): when '{trigger}' "
            f"then {self._response_summary(entry)}."
        )
        self.log_audit_event(
            user_id,
            "explicit_rule_created",
            {
                "entry_id": entry.entry_id,
                "scope": scope.value,
                "trigger": trigger,
                "usage": entry.usage.value,
            },
        )
        return ExplicitRuleResult(entry=entry, acknowledgement=ack)

    def log_audit_event(self, user_id: str, event: str, details: dict[str, Any]) -> None:
        try:
            user_dir = self._user_dir(user_id)
            user_dir.mkdir(parents=True, exist_ok=True)
            audit_path = user_dir / "audit.md"
            timestamp = datetime.now(UTC).isoformat()
            detail_str = " ".join(f"{key}={value}" for key, value in details.items())
            entry = f"- {timestamp} [{event}] {detail_str}\n"
            with audit_path.open("a", encoding="utf-8") as handle:
                handle.write(entry)
        except Exception:
            logger.warning("Failed to write intent memory audit entry", exc_info=True)

    def _response_summary(self, entry: MemoryEntry) -> str:
        response = entry.response or {}
        if isinstance(response, dict):
            if entry.usage == MemoryUsage.ROUTING:
                handler = response.get("handler")
                if handler:
                    return f"route to {handler}"
            if entry.usage == MemoryUsage.CLASSIFICATION:
                classification = response.get("classification")
                if classification:
                    return f"classify as {classification}"
        if isinstance(response, str):
            return response
        return entry.usage.value

    def _match_entries(
        self,
        *,
        usage: MemoryUsage,
        user_id: str,
        text: str,
        workspace_id: str | int | None,
        session_id: str | None,
        threshold: float,
        collect_all: bool = False,
    ) -> MemoryMatch | list[MemoryMatch] | None:
        settings = self.get_settings(user_id)
        if not settings.enabled:
            return [] if collect_all else None
        if usage in {MemoryUsage.CLASSIFICATION, MemoryUsage.ROUTING}:
            if not settings.auto_classify_enabled:
                return [] if collect_all else None
        entries = self._load_entries(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        matches: list[MemoryMatch] = []
        for entry in entries:
            if not entry.enabled or entry.usage != usage:
                continue
            score = self._match_trigger(entry, text)
            if score is None:
                continue
            score *= entry.confidence
            if score < threshold:
                continue
            matches.append(
                MemoryMatch(
                    entry=entry,
                    score=score,
                    reason=f"Matched {entry.trigger_type} trigger",
                )
            )
        if not matches:
            return [] if collect_all else None
        matches.sort(key=lambda m: m.score, reverse=True)
        if collect_all:
            return matches
        return matches[0]

    def _match_assumption(
        self,
        *,
        user_id: str,
        assumption_text: str,
        category: str,
        workspace_id: str | int | None,
        session_id: str | None,
        policy: IntentMemoryPolicy,
    ) -> MemoryMatch | None:
        entries = self._load_entries(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        best: MemoryMatch | None = None
        for entry in entries:
            if not entry.enabled or entry.usage != MemoryUsage.AUTO_CONFIRM:
                continue
            score = self._match_assumption_trigger(
                entry, assumption_text, category, policy=policy
            )
            if score is None:
                continue
            score *= entry.confidence
            if best is None or score > best.score:
                best = MemoryMatch(entry=entry, score=score, reason="Matched auto-confirm rule")
        return best

    def _match_trigger(self, entry: MemoryEntry, text: str) -> float | None:
        normalized_text = _normalize_text(text)
        normalized_trigger = _normalize_text(entry.trigger)
        if entry.trigger_type == "exact":
            return 1.0 if normalized_text == normalized_trigger else None
        if entry.trigger_type == "contains":
            return 1.0 if normalized_trigger and normalized_trigger in normalized_text else None
        if entry.trigger_type == "regex":
            try:
                pattern = re.compile(entry.trigger, re.I)
            except re.error:
                return None
            return 1.0 if pattern.search(text) else None
        if entry.trigger_type == "similarity":
            return self._similarity_score(normalized_text, normalized_trigger)
        if entry.trigger_type == "category":
            return 1.0 if normalized_text == normalized_trigger else None
        return None

    def _match_assumption_trigger(
        self,
        entry: MemoryEntry,
        assumption_text: str,
        category: str,
        *,
        policy: IntentMemoryPolicy,
    ) -> float | None:
        if entry.trigger_type == "category":
            return 1.0 if entry.trigger == category else None
        if entry.trigger_type == "similarity":
            score = self._similarity_score(
                _normalize_text(assumption_text),
                _normalize_text(entry.trigger),
            )
            if score is None or score < policy.auto_confirm_similarity_threshold:
                return None
            return score
        return self._match_trigger(entry, assumption_text)

    def _similarity_score(self, left: str, right: str) -> float | None:
        if not left or not right:
            return None
        if left == right:
            return 1.0
        import difflib

        return difflib.SequenceMatcher(None, left, right).ratio()

    def _load_entries(
        self,
        *,
        user_id: str,
        workspace_id: str | int | None,
        session_id: str | None,
    ) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        for scope, scope_id in (
            (MemoryScope.SESSION, session_id),
            (MemoryScope.WORKSPACE, workspace_id),
            (MemoryScope.USER, None),
        ):
            if scope in {MemoryScope.SESSION, MemoryScope.WORKSPACE} and scope_id is None:
                continue
            path = self._scope_dir(
                user_id=user_id,
                scope=scope,
                workspace_id=workspace_id if scope == MemoryScope.WORKSPACE else None,
                session_id=session_id if scope == MemoryScope.SESSION else None,
            )
            if not path.exists():
                continue
            for file_path in path.glob("*.md"):
                entry = self._load_entry(file_path, fallback_scope=scope, scope_id=scope_id)
                if entry:
                    entries.append(entry)
        return entries

    def _load_entry(
        self,
        path: Path,
        *,
        fallback_scope: MemoryScope,
        scope_id: str | int | None,
    ) -> MemoryEntry | None:
        try:
            contents = path.read_text(encoding="utf-8")
        except Exception:
            logger.warning("Failed to read intent memory entry", exc_info=True)
            return None
        data, _body = _parse_frontmatter(contents)
        entry_id = str(data.get("id") or path.stem)
        scope_value = data.get("scope") or fallback_scope.value
        kind_value = data.get("kind") or MemoryKind.EXPLICIT.value
        usage_value = data.get("usage") or MemoryUsage.CLASSIFICATION.value
        trigger = str(data.get("trigger") or "").strip()
        if not trigger:
            return None
        try:
            scope = MemoryScope(scope_value)
        except ValueError:
            scope = fallback_scope
        try:
            kind = MemoryKind(kind_value)
        except ValueError:
            kind = MemoryKind.EXPLICIT
        try:
            usage = MemoryUsage(usage_value)
        except ValueError:
            usage = MemoryUsage.CLASSIFICATION
        entry = MemoryEntry(
            entry_id=entry_id,
            scope=scope,
            kind=kind,
            usage=usage,
            trigger=trigger,
            trigger_type=str(data.get("trigger_type") or "contains"),
            response=data.get("response"),
            confidence=float(data.get("confidence") or 0.0),
            enabled=bool(data.get("enabled", True)),
            workspace_id=str(data.get("workspace_id") or "")
            if data.get("workspace_id") is not None
            else None,
            session_id=str(data.get("session_id") or "")
            if data.get("session_id") is not None
            else None,
            created_at=str(data.get("created_at") or datetime.now(UTC).isoformat()),
            updated_at=str(data.get("updated_at") or datetime.now(UTC).isoformat()),
            stats=MemoryStats(
                total=int(data.get("stats_total") or 0),
                accepted=int(data.get("stats_accepted") or 0),
                rejected=int(data.get("stats_rejected") or 0),
                last_used_at=str(data.get("stats_last_used") or "")
                if data.get("stats_last_used") is not None
                else None,
            ),
            description=str(data.get("description") or "")
            if data.get("description") is not None
            else None,
        )
        if entry.scope == MemoryScope.WORKSPACE and entry.workspace_id is None and scope_id:
            entry.workspace_id = str(scope_id)
        if entry.scope == MemoryScope.SESSION and entry.session_id is None and scope_id:
            entry.session_id = str(scope_id)
        return entry

    def _build_entry(
        self,
        *,
        user_id: str,
        scope: MemoryScope,
        kind: MemoryKind,
        usage: MemoryUsage,
        trigger: str,
        trigger_type: str,
        response: Any,
        confidence: float,
        workspace_id: str | None,
        session_id: str | None,
    ) -> MemoryEntry:
        entry_id = f"mem-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{abs(hash(trigger)) % 10000}"
        return MemoryEntry(
            entry_id=entry_id,
            scope=scope,
            kind=kind,
            usage=usage,
            trigger=trigger,
            trigger_type=trigger_type,
            response=response,
            confidence=confidence,
            workspace_id=workspace_id,
            session_id=session_id,
        )

    def _get_or_create_entry(
        self,
        *,
        user_id: str,
        scope: MemoryScope,
        kind: MemoryKind,
        usage: MemoryUsage,
        trigger: str,
        trigger_type: str,
        response: Any,
        workspace_id: str | None,
        session_id: str | None,
    ) -> MemoryEntry:
        existing = self._find_entry(
            user_id=user_id,
            scope=scope,
            usage=usage,
            trigger=trigger,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        if existing:
            existing.kind = kind
            existing.response = response
            return existing
        return self._build_entry(
            user_id=user_id,
            scope=scope,
            kind=kind,
            usage=usage,
            trigger=trigger,
            trigger_type=trigger_type,
            response=response,
            confidence=0.0,
            workspace_id=workspace_id,
            session_id=session_id,
        )

    def _find_entry(
        self,
        *,
        user_id: str,
        scope: MemoryScope,
        usage: MemoryUsage,
        trigger: str,
        workspace_id: str | None,
        session_id: str | None,
    ) -> MemoryEntry | None:
        entries = self._load_entries(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        for entry in entries:
            if (
                entry.scope == scope
                and entry.usage == usage
                and _normalize_text(entry.trigger) == _normalize_text(trigger)
            ):
                return entry
        return None

    def _update_stats(
        self,
        entry: MemoryEntry,
        *,
        accepted: bool,
        rejected: bool,
    ) -> None:
        entry.stats.total += 1
        if accepted:
            entry.stats.accepted += 1
        if rejected:
            entry.stats.rejected += 1
        entry.stats.last_used_at = datetime.now(UTC).isoformat()
        if entry.stats.total > 0:
            entry.confidence = entry.stats.accepted / entry.stats.total
        entry.updated_at = datetime.now(UTC).isoformat()

    def _record_usage(self, entry: MemoryEntry, accepted: bool | None) -> None:
        if accepted is None:
            entry.stats.total += 1
        else:
            entry.stats.total += 1
            if accepted:
                entry.stats.accepted += 1
            else:
                entry.stats.rejected += 1
        entry.stats.last_used_at = datetime.now(UTC).isoformat()
        if entry.stats.total > 0:
            entry.confidence = max(entry.confidence, entry.stats.accepted / entry.stats.total)
        entry.updated_at = datetime.now(UTC).isoformat()

    def _persist_entry(self, user_id: str, entry: MemoryEntry) -> None:
        path = self._entry_path(user_id=user_id, entry=entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_settings_file(user_id)
        frontmatter = {
            "id": entry.entry_id,
            "scope": entry.scope.value,
            "kind": entry.kind.value,
            "usage": entry.usage.value,
            "trigger": entry.trigger,
            "trigger_type": entry.trigger_type,
            "response": entry.response,
            "confidence": round(entry.confidence, 4),
            "enabled": entry.enabled,
            "workspace_id": entry.workspace_id,
            "session_id": entry.session_id,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
            "stats_total": entry.stats.total,
            "stats_accepted": entry.stats.accepted,
            "stats_rejected": entry.stats.rejected,
            "stats_last_used": entry.stats.last_used_at,
        }
        lines = ["---"]
        for key, value in frontmatter.items():
            lines.append(f"{key}: {_serialize_value(value)}")
        lines.append("---")
        title = f"Intent Memory: {entry.trigger[:48]}"
        body = [
            "",
            f"# {title}",
            "",
            "## Trigger",
            entry.trigger,
            "",
            "## Response",
            _format_response(entry.response),
            "",
            "## Notes",
            f"- scope: {entry.scope.value}",
            f"- kind: {entry.kind.value}",
            f"- usage: {entry.usage.value}",
        ]
        path.write_text("\n".join(lines + body) + "\n", encoding="utf-8")

    def _ensure_settings_file(self, user_id: str) -> None:
        settings_path = self._user_dir(user_id) / "settings.md"
        if settings_path.exists():
            return
        self._write_settings_file(user_id, self._default_settings)

    def _write_settings_file(self, user_id: str, settings: IntentMemorySettings) -> None:
        settings_path = self._user_dir(user_id) / "settings.md"
        body = None
        if settings_path.exists():
            try:
                contents = settings_path.read_text(encoding="utf-8")
                _data, body = _parse_frontmatter(contents)
            except Exception:
                body = None
        if not body or not body.strip():
            body = "\n".join(
                [
                    "",
                    "# Intent Memory Settings",
                    "",
                    "Toggle intent memory behaviors by editing the frontmatter values.",
                    "",
                ]
            )
        frontmatter = {
            "enabled": settings.enabled,
            "auto_classify": settings.auto_classify_enabled,
            "auto_confirm": settings.auto_confirm_enabled,
            "suggestions": settings.suggestions_enabled,
            "auto_classify_threshold": settings.auto_classify_threshold,
            "auto_confirm_threshold": settings.auto_confirm_threshold,
            "auto_confirm_min_samples": settings.auto_confirm_min_samples,
            "auto_confirm_similarity_threshold": settings.auto_confirm_similarity_threshold,
            "note_suggestion_threshold": settings.note_suggestion_threshold,
        }
        lines = ["---"]
        for key, value in frontmatter.items():
            lines.append(f"{key}: {_serialize_value(value)}")
        lines.append("---")
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(lines)
        if not body.startswith("\n"):
            payload = f"{payload}\n{body}"
        else:
            payload = f"{payload}{body}"
        if not payload.endswith("\n"):
            payload = f"{payload}\n"
        settings_path.write_text(payload, encoding="utf-8")

    def _user_dir(self, user_id: str) -> Path:
        return self._base_path / "users" / _sanitize_component(user_id)

    def _scope_dir(
        self,
        *,
        user_id: str,
        scope: MemoryScope,
        workspace_id: str | int | None,
        session_id: str | None,
    ) -> Path:
        base = self._user_dir(user_id)
        if scope == MemoryScope.USER:
            return base / "user"
        if scope == MemoryScope.WORKSPACE:
            workspace_component = _sanitize_component(str(workspace_id or "default"))
            return base / "workspaces" / workspace_component
        session_component = _sanitize_component(str(session_id or "default"))
        return base / "sessions" / session_component

    def _entry_path(self, *, user_id: str, entry: MemoryEntry) -> Path:
        scope_dir = self._scope_dir(
            user_id=user_id,
            scope=entry.scope,
            workspace_id=entry.workspace_id,
            session_id=entry.session_id,
        )
        filename = f"{_sanitize_component(entry.entry_id)}.md"
        return scope_dir / filename


_intent_memory_store: IntentMemoryStore | None = None


def get_intent_memory_store(
    *,
    base_path: str | None = None,
    policy: IntentMemoryPolicy | None = None,
    force_new: bool = False,
) -> IntentMemoryStore:
    """Get singleton intent memory store."""
    global _intent_memory_store
    if _intent_memory_store is None or force_new:
        _intent_memory_store = IntentMemoryStore(base_path=base_path, policy=policy)
    return _intent_memory_store
