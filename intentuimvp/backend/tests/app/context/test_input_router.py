"""Tests for input router."""

import pytest

from app.context.input_router import InputRouter
from app.context.models import ContextPayload, RoutingDecision
from app.services.input_classifier import InputClassification, InputClassificationType


class FakeClassifier:
    """Fake classifier that returns a preset result."""

    def __init__(self, result: InputClassification) -> None:
        self.result = result
        self.calls = 0

    async def classify(self, payload: ContextPayload, *, user_id: str | None = None) -> InputClassification:
        self.calls += 1
        return self.result


class FakeContextRouter:
    """Fake context router for command routing."""

    def __init__(self) -> None:
        self.calls = 0

    async def route(self, payload: ContextPayload) -> RoutingDecision:
        self.calls += 1
        return RoutingDecision(
            handler="plan_handler",
            confidence=0.88,
            payload=payload,
            reason="LLM plan",
        )


@pytest.mark.asyncio
async def test_route_command_uses_context_router() -> None:
    classification = InputClassification(
        input_type=InputClassificationType.COMMAND,
        confidence=0.7,
        reason="Command",
    )
    classifier = FakeClassifier(classification)
    context_router = FakeContextRouter()
    router = InputRouter(classifier=classifier, context_router=context_router)

    payload = ContextPayload(text="Plan Q2 roadmap")
    decision = await router.route(payload)

    assert decision.handler == "plan_handler"
    assert context_router.calls == 1
    assert classifier.calls == 1
    assert "Input classified as command" in decision.reason


@pytest.mark.asyncio
async def test_route_question_maps_to_chat() -> None:
    classification = InputClassification(
        input_type=InputClassificationType.QUESTION,
        confidence=0.8,
        reason="Question",
    )
    router = InputRouter(classifier=FakeClassifier(classification), context_router=FakeContextRouter())

    decision = await router.route(ContextPayload(text="How does this work?"))

    assert decision.handler == "chat_handler"
    assert decision.confidence == 0.8


@pytest.mark.asyncio
async def test_route_note_maps_to_note_handler() -> None:
    classification = InputClassification(
        input_type=InputClassificationType.NOTE,
        confidence=0.7,
        reason="Note",
    )
    router = InputRouter(classifier=FakeClassifier(classification), context_router=FakeContextRouter())

    decision = await router.route(ContextPayload(text="Note: follow up"))

    assert decision.handler == "note_handler"


@pytest.mark.asyncio
async def test_route_configuration_maps_to_configuration_handler() -> None:
    classification = InputClassification(
        input_type=InputClassificationType.CONFIGURATION,
        confidence=0.7,
        reason="Config",
    )
    router = InputRouter(classifier=FakeClassifier(classification), context_router=FakeContextRouter())

    decision = await router.route(ContextPayload(text="Set theme to dark"))

    assert decision.handler == "configuration_handler"


@pytest.mark.asyncio
async def test_route_ambiguous_maps_to_clarification() -> None:
    classification = InputClassification(
        input_type=InputClassificationType.AMBIGUOUS,
        confidence=0.2,
        reason="Ambiguous",
    )
    router = InputRouter(classifier=FakeClassifier(classification), context_router=FakeContextRouter())

    decision = await router.route(ContextPayload(text="maybe"))

    assert decision.handler == "clarification_handler"


@pytest.mark.asyncio
async def test_route_clarification_response_maps_to_response_handler() -> None:
    classification = InputClassification(
        input_type=InputClassificationType.CLARIFICATION_RESPONSE,
        confidence=0.75,
        reason="Clarification response",
    )
    router = InputRouter(classifier=FakeClassifier(classification), context_router=FakeContextRouter())

    decision = await router.route(ContextPayload(text="Actually, use Q2 data"))

    assert decision.handler == "clarification_response_handler"
