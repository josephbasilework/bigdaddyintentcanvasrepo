"""Data models for context routing.

Defines the payloads and decision structures used by the context router.
"""

from dataclasses import dataclass


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
    """

    handler: str
    confidence: float
    payload: ContextPayload
    reason: str

    def __post_init__(self) -> None:
        """Validate routing decision."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0 and 1")
