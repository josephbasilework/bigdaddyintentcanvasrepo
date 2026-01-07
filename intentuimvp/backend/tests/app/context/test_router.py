"""Tests for context router."""

import pytest

from app.context.models import ContextPayload, RoutingDecision
from app.context.router import ContextRouter


@pytest.fixture
def router() -> ContextRouter:
    """Get a fresh context router instance for testing."""
    return ContextRouter()


class TestContextRouter:
    """Test suite for ContextRouter."""

    @pytest.mark.asyncio
    async def test_route_slash_command_research(self, router: ContextRouter) -> None:
        """Test routing /research slash command."""
        payload = ContextPayload(text="/research AI trends in 2024")
        decision = await router.route(payload)

        assert decision.handler == "research_handler"
        assert decision.confidence == 1.0
        assert "research" in decision.reason.lower()
        assert decision.payload == payload

    @pytest.mark.asyncio
    async def test_route_slash_command_help(self, router: ContextRouter) -> None:
        """Test routing /help slash command."""
        payload = ContextPayload(text="/help")
        decision = await router.route(payload)

        assert decision.handler == "help_handler"
        assert decision.confidence == 1.0
        assert decision.payload == payload

    @pytest.mark.asyncio
    async def test_route_slash_command_clear(self, router: ContextRouter) -> None:
        """Test routing /clear slash command."""
        payload = ContextPayload(text="/clear")
        decision = await router.route(payload)

        assert decision.handler == "clear_handler"
        assert decision.confidence == 1.0

    @pytest.mark.asyncio
    async def test_route_slash_command_with_args(self, router: ContextRouter) -> None:
        """Test routing slash command with arguments."""
        payload = ContextPayload(text="/help with some extra text")
        decision = await router.route(payload)

        assert decision.handler == "help_handler"
        assert decision.confidence == 1.0

    @pytest.mark.asyncio
    async def test_route_unknown_slash_command(self, router: ContextRouter) -> None:
        """Test routing unknown slash command falls back to help."""
        payload = ContextPayload(text="/unknown_command")
        decision = await router.route(payload)

        # Unknown commands route to help_handler
        assert decision.handler == "help_handler"
        assert decision.confidence == 0.5
        assert "unknown" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_route_fallback_plain_text(self, router: ContextRouter) -> None:
        """Test routing plain text without slash command.

        Now uses LLM classification (Intent Decipherer) by default.
        When LLM fails (no gateway available), falls back to chat_handler
        with confidence 0.5 from Intent Decipherer's fallback.
        """
        payload = ContextPayload(text="Hello, how are you?")
        decision = await router.route(payload)

        assert decision.handler == "chat_handler"
        # LLM classification is enabled, so confidence comes from Intent Decipherer
        # When LLM fails, Intent Decipherer fallback returns 0.5
        assert decision.confidence == 0.5

    @pytest.mark.asyncio
    async def test_route_fallback_question(self, router: ContextRouter) -> None:
        """Test routing a question to default chat handler.

        Now uses LLM classification (Intent Decipherer) by default.
        """
        payload = ContextPayload(text="What is the capital of France?")
        decision = await router.route(payload)

        assert decision.handler == "chat_handler"
        # LLM classification returns 0.5 when it falls back
        assert decision.confidence == 0.5

    @pytest.mark.asyncio
    async def test_route_with_attachments(self, router: ContextRouter) -> None:
        """Test routing with attachments list."""
        payload = ContextPayload(
            text="/research", attachments=["file1.txt", "file2.pdf"]
        )
        decision = await router.route(payload)

        assert decision.handler == "research_handler"
        assert decision.payload.attachments == ["file1.txt", "file2.pdf"]

    @pytest.mark.asyncio
    async def test_route_empty_attachments(self, router: ContextRouter) -> None:
        """Test routing with empty attachments defaults to empty list."""
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
