"""Data models for context routing.

Defines the payloads and decision structures used by the context router.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, cast


class AssumptionCategory(str, Enum):
    """Categories of assumptions extracted by agents."""

    CONTEXT = "context"
    INTENT = "intent"
    PARAMETER = "parameter"
    OTHER = "other"


@dataclass
class Assumption:
    """An assumption extracted by an agent that needs user confirmation.

    Attributes:
        id: Unique identifier for this assumption.
        text: The assumption text extracted by the agent.
        confidence: Confidence score (0-1) for this assumption.
        category: The category/type of assumption.
        explanation: Optional explanation of why this assumption was made.
    """

    id: str
    text: str
    confidence: float
    category: Literal["context", "intent", "parameter", "other"]
    explanation: str | None = None

    def __post_init__(self) -> None:
        """Validate assumption data."""
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Assumption id cannot be empty")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Assumption text cannot be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0 and 1")
        if not isinstance(self.category, str):
            raise ValueError("Assumption category must be a string")
        if self.category not in {category.value for category in AssumptionCategory}:
            raise ValueError("Assumption category must be a supported value")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "text": self.text,
            "confidence": self.confidence,
            "category": self.category,
            "explanation": self.explanation,
        }


def parse_assumption(payload: Mapping[str, Any]) -> Assumption:
    """Parse and validate a raw assumption payload."""
    if not isinstance(payload, Mapping):
        raise ValueError("Assumption payload must be a mapping")

    raw_id = payload.get("id")
    assumption_id = raw_id if raw_id is not None else str(uuid.uuid4())
    raw_text = payload.get("text")
    text = raw_text if raw_text is not None else ""
    raw_confidence = payload.get("confidence", 0.5)

    raw_category = payload.get("category")
    if raw_category is None:
        category = AssumptionCategory.OTHER.value
    elif isinstance(raw_category, AssumptionCategory):
        category = raw_category.value
    else:
        category = str(raw_category).strip().lower()

    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError("Confidence must be between 0 and 1") from exc

    explanation = payload.get("explanation")
    if explanation is not None and not isinstance(explanation, str):
        explanation = str(explanation)

    category_value = cast(
        Literal["context", "intent", "parameter", "other"],
        category,
    )

    return Assumption(
        id=str(assumption_id).strip(),
        text=str(text).strip(),
        confidence=confidence,
        category=category_value,
        explanation=explanation,
    )


@dataclass
class ContextPayload:
    """User input context from the frontend.

    Attributes:
        text: The user's text input.
        attachments: Optional list of attachment identifiers.
    """

    text: str
    attachments: list[str] | None = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.attachments is None:
            self.attachments = []


@dataclass
class RoutingDecision:
    """Decision from the context router.

    Attributes:
        handler: Identifier for the handler that should process this request.
        confidence: Confidence score for this routing decision (0-1).
        payload: The original context payload plus any routing metadata.
        reason: Human-readable explanation for the routing decision.
        assumptions: Optional list of assumptions that need user confirmation.
    """

    handler: str
    confidence: float
    payload: ContextPayload
    reason: str
    assumptions: list[Assumption] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate routing decision."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0 and 1")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "handler": self.handler,
            "confidence": self.confidence,
            "payload": {
                "text": self.payload.text,
                "attachments": self.payload.attachments,
            },
            "reason": self.reason,
            "assumptions": [a.to_dict() for a in self.assumptions],
        }
