"""Tests for input classification utilities."""

import pytest

from app.context.models import ContextPayload
from app.services.input_classifier import (
    InputClassificationType,
    InputClassifier,
    extract_configuration_updates,
    strip_note_prefix,
)


class FakeIntentIndexLookup:
    """Fake intent memory lookup for classification tests."""

    def __init__(self, score: float = 0.8, resolution: str = "plan") -> None:
        self.score = score
        self.resolution = resolution

    async def lookup(self, user_id: str, input_text: str):
        return [
            type(
                "Match",
                (),
                {
                    "resolution": self.resolution,
                    "score": self.score,
                },
            )()
        ]


@pytest.mark.asyncio
async def test_classify_question() -> None:
    classifier = InputClassifier(intent_index_lookup=None)
    payload = ContextPayload(text="How does this work?")
    result = await classifier.classify(payload)

    assert result.input_type == InputClassificationType.QUESTION
    assert result.confidence >= 0.65


@pytest.mark.asyncio
async def test_classify_command() -> None:
    classifier = InputClassifier(intent_index_lookup=None)
    payload = ContextPayload(text="/plan Build Q2 roadmap")
    result = await classifier.classify(payload)

    assert result.input_type == InputClassificationType.COMMAND
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_classify_note() -> None:
    classifier = InputClassifier(intent_index_lookup=None)
    payload = ContextPayload(text="Note: revisit onboarding flow")
    result = await classifier.classify(payload)

    assert result.input_type == InputClassificationType.NOTE
    assert result.confidence >= 0.65


@pytest.mark.asyncio
async def test_classify_clarification_response() -> None:
    classifier = InputClassifier(intent_index_lookup=None)
    payload = ContextPayload(text="Actually, use Q2 data instead")
    result = await classifier.classify(payload)

    assert result.input_type == InputClassificationType.CLARIFICATION_RESPONSE
    assert result.confidence >= 0.65


@pytest.mark.asyncio
async def test_classify_configuration() -> None:
    classifier = InputClassifier(intent_index_lookup=None)
    payload = ContextPayload(text="Set theme to dark and zoom to 120%")
    result = await classifier.classify(payload)

    assert result.input_type == InputClassificationType.CONFIGURATION
    assert "configuration_updates" in result.signals


@pytest.mark.asyncio
async def test_classify_ambiguous() -> None:
    classifier = InputClassifier(intent_index_lookup=None)
    payload = ContextPayload(text="maybe later")
    result = await classifier.classify(payload)

    assert result.input_type == InputClassificationType.AMBIGUOUS


@pytest.mark.asyncio
async def test_ambiguous_uses_intent_memory() -> None:
    classifier = InputClassifier(intent_index_lookup=FakeIntentIndexLookup())
    payload = ContextPayload(text="ok")
    result = await classifier.classify(payload, user_id="default_user")

    assert result.input_type == InputClassificationType.COMMAND
    assert result.signals["intent_memory_resolution"] == "plan"


def test_strip_note_prefix() -> None:
    assert strip_note_prefix("note: follow up") == "follow up"
    assert strip_note_prefix("Idea revisit KPIs") == "revisit KPIs"


def test_extract_configuration_updates() -> None:
    updates, signals = extract_configuration_updates("Set theme to dark, zoom to 125%")

    assert updates["theme"] == "dark"
    assert updates["zoom_level"] == 1.25
    assert set(signals) == {"theme", "zoom_level"}
