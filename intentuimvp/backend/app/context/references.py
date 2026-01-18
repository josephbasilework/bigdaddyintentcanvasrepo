"""Explicit reference parsing utilities for context routing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_NODE_REF_RE = re.compile(r"\bnode\s*#?\s*([a-z0-9_-]+)\b", re.I)
_NODE_HANDLE_RE = re.compile(r"(?<!\w)@([a-z0-9][\w-]{1,64})", re.I)
_TURN_REF_RE = re.compile(r"\bturn\s*#?\s*(\d+)\b", re.I)
_NAMED_ENTITY_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9]{1,})(?:\s+[A-Z][A-Za-z0-9]{1,}){0,3}\b"
)

_ENTITY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "node",
    "nodes",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "turn",
    "turns",
    "with",
    "you",
}


@dataclass(frozen=True)
class ParsedReferences:
    """Parsed explicit references from input text."""

    node_ids: set[str] = field(default_factory=set)
    node_handles: set[str] = field(default_factory=set)
    turn_numbers: set[int] = field(default_factory=set)
    named_entities: set[str] = field(default_factory=set)


def parse_references(text: str) -> ParsedReferences:
    """Parse explicit references from user input."""
    if not text:
        return ParsedReferences()

    node_ids = {match.group(1) for match in _NODE_REF_RE.finditer(text)}
    node_handles = {match.group(1) for match in _NODE_HANDLE_RE.finditer(text)}
    turn_numbers = {int(match.group(1)) for match in _TURN_REF_RE.finditer(text)}
    named_entities = _extract_named_entities(text)

    return ParsedReferences(
        node_ids=node_ids,
        node_handles=node_handles,
        turn_numbers=turn_numbers,
        named_entities=named_entities,
    )


def has_explicit_reference(text: str) -> bool:
    """Return True when text includes explicit turn/node references."""
    parsed = parse_references(text)
    return bool(parsed.node_ids or parsed.node_handles or parsed.turn_numbers)


def _extract_named_entities(text: str) -> set[str]:
    entities: set[str] = set()
    for match in _NAMED_ENTITY_RE.finditer(text):
        phrase = match.group(0).strip()
        if not phrase:
            continue
        if _should_skip_entity(phrase):
            continue
        entities.add(phrase)
    return entities


def _should_skip_entity(phrase: str) -> bool:
    normalized = phrase.strip().lower()
    if not normalized:
        return True
    if normalized in _ENTITY_STOPWORDS:
        return True
    if len(normalized) < 3:
        return True
    return False
