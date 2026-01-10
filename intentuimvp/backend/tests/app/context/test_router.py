"""Tests for context router."""

import asyncio

import pytest

from app.agents.intent_decipherer import IntentClassification, IntentDecipheringResult
from app.context.models import ContextPayload, RoutingDecision
from app.context.router import ContextRouter


class FakeIntentDecipherer:
    """Stub intent decipherer for deterministic routing tests."""

    def __init__(
        self,
        result: IntentDecipheringResult | None = None,
        *,
        delay: float = 0.0,
        raises: bool = False,
    ) -> None:
        self.result = result
        self.delay = delay
        self.raises = raises
        self.calls = 0
        self.confidence_threshold = 0.8

    async def decipher(self, text: str) -> IntentDecipheringResult:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raises:
            raise RuntimeError("boom")
        if self.result is None:
            raise RuntimeError("no result configured")
        return self.result


def build_result(
    intent_name: str,
    confidence: float,
    *,
    alternatives: list[IntentClassification] | None = None,
    reasoning: str = "LLM ok",
) -> IntentDecipheringResult:
    """Helper to create an IntentDecipheringResult for tests."""
    primary = IntentClassification(
        name=intent_name,
        confidence=confidence,
        description=f"{intent_name} intent",
    )
    return IntentDecipheringResult(
        primary_intent=primary,
        alternative_intents=alternatives or [],
        should_auto_execute=False,
        reasoning=reasoning,
    )


class TestContextRouter:
    """Test suite for ContextRouter."""

    @pytest.mark.asyncio
    async def test_route_slash_command_research(self) -> None:
        """Test routing /research slash command."""
        fake = FakeIntentDecipherer(result=build_result("chat", 0.5))
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(text="/research AI trends in 2024")
        decision = await router.route(payload)

        assert decision.handler == "research_handler"
        assert decision.confidence == 1.0
        assert "research" in decision.reason.lower()
        assert decision.payload == payload
        assert fake.calls == 0

    @pytest.mark.asyncio
    async def test_route_slash_command_help(self) -> None:
        """Test routing /help slash command."""
        fake = FakeIntentDecipherer(result=build_result("chat", 0.5))
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(text="/help")
        decision = await router.route(payload)

        assert decision.handler == "help_handler"
        assert decision.confidence == 1.0
        assert decision.payload == payload
        assert fake.calls == 0

    @pytest.mark.asyncio
    async def test_route_slash_command_clear(self) -> None:
        """Test routing /clear slash command."""
        fake = FakeIntentDecipherer(result=build_result("chat", 0.5))
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(text="/clear")
        decision = await router.route(payload)

        assert decision.handler == "clear_handler"
        assert decision.confidence == 1.0
        assert fake.calls == 0

    @pytest.mark.asyncio
    async def test_route_unknown_slash_command(self) -> None:
        """Test routing unknown slash command falls back to help."""
        fake = FakeIntentDecipherer(result=build_result("chat", 0.5))
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(text="/unknown_command")
        decision = await router.route(payload)

        # Unknown commands route to help_handler
        assert decision.handler == "help_handler"
        assert decision.confidence == 0.5
        assert "unknown" in decision.reason.lower()
        assert fake.calls == 0

    @pytest.mark.asyncio
    async def test_route_llm_highest_confidence_wins(self) -> None:
        """Test higher confidence intent wins within LLM priority."""
        alternatives = [
            IntentClassification(
                name="research",
                confidence=0.8,
                description="research intent",
            )
        ]
        fake = FakeIntentDecipherer(
            result=build_result("create", 0.6, alternatives=alternatives)
        )
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(text="Find sources and create a summary")
        decision = await router.route(payload)

        assert decision.handler == "research_handler"
        assert decision.confidence == 0.8
        assert fake.calls == 1

    @pytest.mark.asyncio
    async def test_route_llm_tie_requires_disambiguation(self) -> None:
        """Test tie in confidence prompts disambiguation."""
        alternatives = [
            IntentClassification(
                name="research",
                confidence=0.75,
                description="research intent",
            )
        ]
        fake = FakeIntentDecipherer(
            result=build_result("create", 0.75, alternatives=alternatives)
        )
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(text="Create and research a topic")
        decision = await router.route(payload)

        assert decision.handler == "clarification_handler"
        assert decision.confidence == 0.75
        assert "ambiguous" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_route_keyword_fallback_on_llm_error(self) -> None:
        """Test keyword fallback when LLM fails."""
        fake = FakeIntentDecipherer(raises=True)
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(text="Please research AI safety")
        decision = await router.route(payload)

        assert decision.handler == "research_handler"
        assert decision.confidence == 0.6
        assert "keyword" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_route_keyword_fallback_on_timeout(self) -> None:
        """Test keyword fallback when LLM times out."""
        fake = FakeIntentDecipherer(
            result=build_result("chat", 0.5),
            delay=0.05,
        )
        router = ContextRouter(
            intent_decipherer=fake,
            classification_timeout=0.01,
        )
        payload = ContextPayload(text="Plan the project milestones")
        decision = await router.route(payload)

        assert decision.handler == "plan_handler"
        assert decision.confidence == 0.55
        assert "timed out" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_route_circuit_breaker_opens_after_failures(self) -> None:
        """Test circuit breaker bypasses LLM after consecutive failures."""
        fake = FakeIntentDecipherer(raises=True)
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(text="Analyze quarterly data")

        for _ in range(3):
            decision = await router.route(payload)
            assert decision.handler == "analyze_handler"

        assert fake.calls == 3

        decision = await router.route(payload)
        assert decision.handler == "analyze_handler"
        assert fake.calls == 3
        assert "circuit breaker" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_route_keyword_fallback_no_match(self) -> None:
        """Test clarification response when keyword fallback finds no match."""
        fake = FakeIntentDecipherer(raises=True)
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(text="Hello there")
        decision = await router.route(payload)

        assert decision.handler == "clarification_handler"
        assert decision.confidence == 0.2
        assert "clarification" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_route_with_attachments(self) -> None:
        """Test routing with attachments list."""
        fake = FakeIntentDecipherer(result=build_result("chat", 0.5))
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(
            text="/research", attachments=["file1.txt", "file2.pdf"]
        )
        decision = await router.route(payload)

        assert decision.handler == "research_handler"
        assert decision.payload.attachments == ["file1.txt", "file2.pdf"]

    @pytest.mark.asyncio
    async def test_route_empty_attachments(self) -> None:
        """Test routing with empty attachments defaults to empty list."""
        fake = FakeIntentDecipherer(result=build_result("chat", 0.5))
        router = ContextRouter(intent_decipherer=fake)
        payload = ContextPayload(text="test")
        decision = await router.route(payload)

        assert decision.payload.attachments == []


class TestContextPayload:
    """Test suite for ContextPayload model."""

    def test_payload_with_text_only(self) -> None:
        """Test creating payload with just text."""
        payload = ContextPayload(text="Hello world")
        assert payload.text == "Hello world"
        assert payload.attachments == []

    def test_payload_with_attachments(self) -> None:
        """Test creating payload with text and attachments."""
        payload = ContextPayload(
            text="Check these files", attachments=["file1.txt"]
        )
        assert payload.text == "Check these files"
        assert payload.attachments == ["file1.txt"]

    def test_payload_with_none_attachments(self) -> None:
        """Test that None attachments defaults to empty list."""
        payload = ContextPayload(text="test", attachments=None)
        assert payload.attachments == []


class TestRoutingDecision:
    """Test suite for RoutingDecision model."""

    def test_routing_decision_valid(self) -> None:
        """Test creating a valid routing decision."""
        payload = ContextPayload(text="test")
        decision = RoutingDecision(
            handler="test_handler",
            confidence=0.8,
            payload=payload,
            reason="Test reason",
        )
        assert decision.handler == "test_handler"
        assert decision.confidence == 0.8

    def test_routing_decision_confidence_too_high(self) -> None:
        """Test that confidence > 1.0 raises error."""
        payload = ContextPayload(text="test")
        with pytest.raises(ValueError, match="Confidence"):
            RoutingDecision(
                handler="test_handler",
                confidence=1.5,
                payload=payload,
                reason="Test",
            )

    def test_routing_decision_confidence_negative(self) -> None:
        """Test that negative confidence raises error."""
        payload = ContextPayload(text="test")
        with pytest.raises(ValueError, match="Confidence"):
            RoutingDecision(
                handler="test_handler",
                confidence=-0.1,
                payload=payload,
                reason="Test",
            )

    def test_routing_decision_confidence_bounds(self) -> None:
        """Test that confidence bounds 0.0 and 1.0 are valid."""
        payload = ContextPayload(text="test")

        decision_min = RoutingDecision(
            handler="test_handler", confidence=0.0, payload=payload, reason="Test"
        )
        assert decision_min.confidence == 0.0

        decision_max = RoutingDecision(
            handler="test_handler", confidence=1.0, payload=payload, reason="Test"
        )
        assert decision_max.confidence == 1.0
