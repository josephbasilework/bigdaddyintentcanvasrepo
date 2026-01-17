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

    async def classify(
        self,
        payload: ContextPayload,
        *,
        user_id: str | None = None,
        workspace_id: str | int | None = None,
        session_id: str | None = None,
    ) -> InputClassification:
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


@pytest.mark.asyncio
async def test_learn_prefix_creates_rule(tmp_path) -> None:
    """Test that 'learn:' prefix creates intent memory rule."""
    from app.services.intent_memory import IntentMemoryStore

    memory_store = IntentMemoryStore(base_path=str(tmp_path))

    # Patch get_intent_memory_store to return our test store
    import app.context.input_router as input_router_module

    original_get_store = input_router_module.get_intent_memory_store

    def mock_get_store():
        return memory_store

    input_router_module.get_intent_memory_store = mock_get_store

    try:
        classification = InputClassification(
            input_type=InputClassificationType.COMMAND,
            confidence=0.7,
            reason="Command",
        )
        router = InputRouter(
            classifier=FakeClassifier(classification),
            context_router=FakeContextRouter(),
        )

        decision = await router.route(
            ContextPayload(text="learn: when I say status, route to /dashboard"),
            user_id="test-user",
        )

        assert decision.handler == "chat_handler"
        assert "Intent memory rule stored" in decision.reason

        # Verify rule was created
        match = memory_store.match_routing(user_id="test-user", text="status")
        assert match is not None
        assert match.entry.response["handler"] == "dashboard_handler"
    finally:
        input_router_module.get_intent_memory_store = original_get_store


@pytest.mark.asyncio
async def test_learn_prefix_invalid_rule_gives_feedback(tmp_path) -> None:
    """Test that invalid 'learn:' rule gives helpful feedback."""
    from app.services.intent_memory import IntentMemoryStore

    memory_store = IntentMemoryStore(base_path=str(tmp_path))

    import app.context.input_router as input_router_module

    original_get_store = input_router_module.get_intent_memory_store

    def mock_get_store():
        return memory_store

    input_router_module.get_intent_memory_store = mock_get_store

    try:
        classification = InputClassification(
            input_type=InputClassificationType.COMMAND,
            confidence=0.7,
            reason="Command",
        )
        router = InputRouter(
            classifier=FakeClassifier(classification),
            context_router=FakeContextRouter(),
        )

        decision = await router.route(
            ContextPayload(text="learn: some gibberish that doesn't match pattern"),
            user_id="test-user",
        )

        assert decision.handler == "chat_handler"
        assert "couldn't understand" in decision.payload.text.lower()
    finally:
        input_router_module.get_intent_memory_store = original_get_store


@pytest.mark.asyncio
async def test_remember_prefix_creates_rule(tmp_path) -> None:
    """Test that 'remember:' prefix also creates intent memory rule."""
    from app.services.intent_memory import IntentMemoryStore

    memory_store = IntentMemoryStore(base_path=str(tmp_path))

    import app.context.input_router as input_router_module

    original_get_store = input_router_module.get_intent_memory_store

    def mock_get_store():
        return memory_store

    input_router_module.get_intent_memory_store = mock_get_store

    try:
        classification = InputClassification(
            input_type=InputClassificationType.COMMAND,
            confidence=0.7,
            reason="Command",
        )
        router = InputRouter(
            classifier=FakeClassifier(classification),
            context_router=FakeContextRouter(),
        )

        decision = await router.route(
            ContextPayload(text="remember: when I note ideas, suggest research"),
            user_id="test-user",
        )

        assert decision.handler == "chat_handler"
        assert "Intent memory rule stored" in decision.reason

        # Verify note suggestion rule was created
        suggestions = memory_store.suggest_for_note(
            user_id="test-user", text="Note: ideas"
        )
        assert "research" in suggestions
    finally:
        input_router_module.get_intent_memory_store = original_get_store


@pytest.mark.asyncio
async def test_routing_match_skips_classification(tmp_path) -> None:
    """Test that intent memory routing match bypasses classifier."""
    from app.services.intent_memory import IntentMemoryStore

    memory_store = IntentMemoryStore(base_path=str(tmp_path))

    # Create a routing rule
    memory_store.record_explicit_rule(
        user_id="test-user",
        text="When I say weekly update, route to /plan",
    )

    import app.context.input_router as input_router_module

    original_get_store = input_router_module.get_intent_memory_store

    def mock_get_store():
        return memory_store

    input_router_module.get_intent_memory_store = mock_get_store

    try:
        classification = InputClassification(
            input_type=InputClassificationType.AMBIGUOUS,
            confidence=0.3,
            reason="Ambiguous",
        )
        classifier = FakeClassifier(classification)
        router = InputRouter(
            classifier=classifier,
            context_router=FakeContextRouter(),
        )

        decision = await router.route(
            ContextPayload(text="weekly update"),
            user_id="test-user",
        )

        # Should route via intent memory, not classifier
        assert decision.handler == "plan_handler"
        assert "Intent memory routing" in decision.reason
        # Classifier should not be called
        assert classifier.calls == 0
    finally:
        input_router_module.get_intent_memory_store = original_get_store
