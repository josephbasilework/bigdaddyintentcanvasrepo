"""Input classification utilities for routing user input."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.context.models import ContextPayload

try:  # Optional intent memory lookup for ambiguous inputs
    from app.agents.intent_index import IntentIndexLookup, get_intent_index_lookup
except Exception:  # pragma: no cover - optional dependency surface
    IntentIndexLookup = None  # type: ignore[assignment]
    get_intent_index_lookup = None  # type: ignore[assignment]


class InputClassificationType(str, Enum):
    """High-level categories for user input."""

    QUESTION = "question"
    COMMAND = "command"
    NOTE = "note"
    CLARIFICATION_RESPONSE = "clarification_response"
    CONFIGURATION = "configuration"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class InputClassification:
    """Classification output with confidence and supporting signals."""

    input_type: InputClassificationType
    confidence: float
    reason: str
    signals: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0 and 1")


_SLASH_COMMAND = re.compile(r"^/\w")
_QUESTION_START = re.compile(
    r"^(who|what|when|where|why|how|can|could|should|is|are|do|does|did|"
    r"will|would|may|might)\b",
    re.I,
)
_QUESTION_END = re.compile(r"\?\s*$")
_NOTE_PREFIX = re.compile(
    r"^(note|note:|note\-|remember|memo|idea|insight|thought|observation|eureka|aha)\b",
    re.I,
)
_NOTE_INLINE = re.compile(r"\b(fyi|heads up|note to self|remember that|i realized)\b", re.I)
_CLARIFICATION_SHORT = re.compile(
    r"^(yes|yeah|yep|no|nope|nah|correct|incorrect|right|wrong|exactly|not exactly)\b",
    re.I,
)
_CLARIFICATION_PHRASE = re.compile(
    r"\b(to clarify|clarify|actually|i meant|i mean|what i meant)\b",
    re.I,
)
_CONFIG_SIGNAL = re.compile(
    r"\b(settings?|preferences?|configure|configuration|set|update|change|"
    r"enable|disable|turn on|turn off|theme|zoom|layout|panel)\b",
    re.I,
)
_COMMAND_VERB = re.compile(
    r"^(create|add|build|generate|make|draft|plan|research|analy[sz]e|"
    r"summari[sz]e|compare|clear|help|export|dashboard|graph|calendar|judge)\b",
    re.I,
)
_ZOOM_PATTERN = re.compile(
    r"\bzoom(?:\s+level)?(?:\s+(?:to|at|=))?\s*([0-9]+(?:\.[0-9]+)?)\s*(%?)",
    re.I,
)
_THEME_PATTERN = re.compile(r"\b(dark|light|auto)\b", re.I)


def strip_note_prefix(text: str) -> str:
    """Strip note prefixes like 'note:' or 'idea:' from input."""
    stripped = text.strip()
    match = _NOTE_PREFIX.match(stripped)
    if not match:
        return stripped
    remainder = stripped[match.end() :].lstrip(" :-").strip()
    return remainder or stripped


def extract_configuration_updates(text: str) -> tuple[dict[str, Any], list[str]]:
    """Parse configuration updates from input text."""
    normalized = text.lower()
    updates: dict[str, Any] = {}
    signals: list[str] = []

    theme_match = _THEME_PATTERN.search(normalized)
    if theme_match and ("theme" in normalized or "mode" in normalized):
        theme = theme_match.group(1).lower()
        updates["theme"] = theme
        signals.append("theme")

    zoom_match = _ZOOM_PATTERN.search(normalized)
    if zoom_match:
        raw_value = zoom_match.group(1)
        percent = bool(zoom_match.group(2))
        try:
            value = float(raw_value)
        except ValueError:
            value = 0.0
        if value:
            if percent or value > 10:
                value = value / 100.0
            updates["zoom_level"] = round(value, 2)
            signals.append("zoom_level")

    return updates, signals


class InputClassifier:
    """Classify user input into high-level categories."""

    def __init__(
        self,
        *,
        intent_index_lookup: IntentIndexLookup | None = None,
        ambiguous_threshold: float = 0.5,
        intent_memory_threshold: float = 0.75,
    ) -> None:
        if intent_index_lookup is None and get_intent_index_lookup is not None:
            try:
                intent_index_lookup = get_intent_index_lookup()
            except Exception:
                intent_index_lookup = None
        self._intent_index_lookup = intent_index_lookup
        self._ambiguous_threshold = ambiguous_threshold
        self._intent_memory_threshold = intent_memory_threshold

    async def classify(
        self,
        payload: ContextPayload,
        *,
        user_id: str | None = None,
    ) -> InputClassification:
        """Classify input text and return a category with confidence."""
        text = payload.text.strip()
        if not text:
            return InputClassification(
                input_type=InputClassificationType.AMBIGUOUS,
                confidence=0.0,
                reason="Empty input",
                signals={"empty": True},
            )

        if _SLASH_COMMAND.match(text):
            return InputClassification(
                input_type=InputClassificationType.COMMAND,
                confidence=0.95,
                reason="Slash command detected",
                signals={"slash_command": True},
            )

        normalized = text.lower()
        word_count = len(normalized.split())

        config_updates, config_signals = extract_configuration_updates(text)
        config_score = 0.0
        if config_updates:
            config_score = 0.8
        elif _CONFIG_SIGNAL.search(normalized):
            config_score = 0.55

        clarification_score = 0.0
        if _CLARIFICATION_SHORT.match(normalized) and word_count <= 6:
            clarification_score = 0.8
        elif _CLARIFICATION_PHRASE.search(normalized):
            clarification_score = 0.7

        note_score = 0.0
        if _NOTE_PREFIX.match(normalized):
            note_score = 0.75
        elif _NOTE_INLINE.search(normalized):
            note_score = 0.65

        question_score = 0.0
        if _QUESTION_END.search(text):
            question_score = 0.85
        elif _QUESTION_START.match(normalized):
            question_score = 0.65

        command_score = 0.0
        if _COMMAND_VERB.match(normalized):
            command_score = 0.7
        if payload.selection and (
            payload.selection.selected_nodes or payload.selection.selected_edges
        ):
            command_score = max(command_score, 0.65)
        if payload.attachments:
            command_score = max(command_score, 0.6)

        candidates = [
            (
                InputClassificationType.CONFIGURATION,
                config_score,
                "Configuration language detected",
            ),
            (
                InputClassificationType.CLARIFICATION_RESPONSE,
                clarification_score,
                "Clarification response detected",
            ),
            (InputClassificationType.NOTE, note_score, "Note cues detected"),
            (InputClassificationType.QUESTION, question_score, "Question cues detected"),
            (InputClassificationType.COMMAND, command_score, "Command cues detected"),
        ]

        best_type, best_score, best_reason = max(candidates, key=lambda item: item[1])
        signals: dict[str, Any] = {
            "scores": {
                "configuration": config_score,
                "clarification_response": clarification_score,
                "note": note_score,
                "question": question_score,
                "command": command_score,
            }
        }
        if config_signals:
            signals["configuration_signals"] = config_signals
        if config_updates:
            signals["configuration_updates"] = config_updates

        if best_score < self._ambiguous_threshold:
            ambiguous = await self._resolve_with_intent_memory(
                payload,
                user_id=user_id,
                signals=signals,
            )
            if ambiguous is not None:
                return ambiguous
            return InputClassification(
                input_type=InputClassificationType.AMBIGUOUS,
                confidence=best_score,
                reason="Low confidence classification",
                signals=signals,
            )

        return InputClassification(
            input_type=best_type,
            confidence=best_score,
            reason=best_reason,
            signals=signals,
        )

    async def _resolve_with_intent_memory(
        self,
        payload: ContextPayload,
        *,
        user_id: str | None,
        signals: dict[str, Any],
    ) -> InputClassification | None:
        if self._intent_index_lookup is None or user_id is None:
            return None
        try:
            matches = await self._intent_index_lookup.lookup(user_id, payload.text)
        except Exception:
            return None
        if not matches:
            return None
        top_match = matches[0]
        if top_match.score < self._intent_memory_threshold:
            return None
        signals = dict(signals)
        signals.update(
            {
                "intent_memory_resolution": top_match.resolution,
                "intent_memory_score": top_match.score,
            }
        )
        return InputClassification(
            input_type=InputClassificationType.COMMAND,
            confidence=min(0.9, max(top_match.score, self._ambiguous_threshold)),
            reason="Intent memory match resolved ambiguity",
            signals=signals,
        )
