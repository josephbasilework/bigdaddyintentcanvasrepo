"""Context routing pipeline.

Routes user input to appropriate handlers based on slash commands,
LLM classification, or fallback behavior.
"""

import logging
import re

from app.agents.intent_decipherer import IntentDeciphererAgent, get_intent_decipherer
from app.context.models import Assumption, ContextPayload, RoutingDecision

logger = logging.getLogger(__name__)

# Known slash commands and their handlers
SLASH_COMMANDS = {
    "/research": "research_handler",
    "/help": "help_handler",
    "/clear": "clear_handler",
}

# Pattern to match slash commands at the start of input
SLASH_PATTERN = re.compile(r"^(/[\w-]+)\s*")


class ContextRouter:
    """Routes user context to appropriate handlers.

    Priority order:
    1. Slash commands (exact match at start of input)
    2. LLM classification (for natural language intent)
    3. Fallback to default handler
    """

    # Intent to handler mapping
    INTENT_HANDLERS = {
        "research": "research_handler",
        "chat": "chat_handler",
        "create": "create_handler",
        "analyze": "analyze_handler",
        "help": "help_handler",
        "clear": "clear_handler",
    }

    def __init__(self, intent_decipherer: IntentDeciphererAgent | None = None) -> None:
        """Initialize the context router.

        Args:
            intent_decipherer: Optional Intent Decipherer Agent instance.
                            If None, uses singleton.
        """
        self._use_llm_classification: bool = True
        self._intent_decipherer = intent_decipherer

    async def route(self, payload: ContextPayload) -> RoutingDecision:
        """Route the context payload to an appropriate handler.

        Args:
            payload: User context from the frontend.

        Returns:
            RoutingDecision with handler identifier and reasoning.
        """
        text = payload.text.strip()

        # 1. Check for slash commands first (highest priority)
        if text.startswith("/"):
            return self._route_slash_command(payload)

        # 2. LLM classification (future enhancement)
        # For now, skip LLM classification to avoid unnecessary latency
        if self._use_llm_classification:
            return await self._route_via_llm(payload)

        # 3. Fallback to default handler
        return self._route_fallback(payload)

    def _route_slash_command(self, payload: ContextPayload) -> RoutingDecision:
        """Route based on slash command at the start of input.

        Args:
            payload: User context containing the slash command.

        Returns:
            RoutingDecision for the slash command handler.
        """
        text = payload.text.strip()
        match = SLASH_PATTERN.match(text)

        if match:
            command = match.group(1)  # Already includes the slash, e.g. "/research"

            if command in SLASH_COMMANDS:
                handler = SLASH_COMMANDS[command]
                logger.info(
                    f"Slash command routed: {command} -> {handler}",
                    extra={"command": command, "handler": handler},
                )
                return RoutingDecision(
                    handler=handler,
                    confidence=1.0,
                    payload=payload,
                    reason=f"Matched slash command: {command}",
                )

        # Unknown slash command
        logger.warning(f"Unknown slash command: {text[:50]}")
        return RoutingDecision(
            handler="help_handler",
            confidence=0.5,
            payload=payload,
            reason="Unknown command, routing to help",
        )

    async def _route_via_llm(self, payload: ContextPayload) -> RoutingDecision:
        """Route using LLM classification via Intent Decipherer Agent.

        Analyzes user input to:
        - Classify the primary intent
        - Extract assumptions that need confirmation
        - Map intent to appropriate handler
        - Provide confidence scoring

        Args:
            payload: User context to classify.

        Returns:
            RoutingDecision based on LLM classification with assumptions.
        """
        if self._intent_decipherer is None:
            self._intent_decipherer = get_intent_decipherer()

        try:
            result = await self._intent_decipherer.decipher(payload.text)

            # Map intent to handler
            intent_name = result.primary_intent.name.lower()
            handler = self.INTENT_HANDLERS.get(intent_name, "chat_handler")

            # Convert assumption dicts to Assumption objects
            assumptions = [
                Assumption(
                    id=a.get("id", ""),
                    text=a.get("text", ""),
                    confidence=a.get("confidence", 0.5),
                    category=a.get("category", "other"),
                    explanation=a.get("explanation"),
                )
                for a in result.assumptions
            ]

            # Filter to only include assumptions below confidence threshold
            # These need user confirmation
            assumptions_needing_confirmation = [
                a for a in assumptions if a.confidence < self._intent_decipherer.confidence_threshold
            ]

            logger.info(
                f"LLM routed: {intent_name} -> {handler} (confidence: {result.primary_intent.confidence:.2f})",
                extra={
                    "intent": intent_name,
                    "handler": handler,
                    "confidence": result.primary_intent.confidence,
                    "assumptions_count": len(assumptions_needing_confirmation),
                    "should_auto_execute": result.should_auto_execute,
                },
            )

            return RoutingDecision(
                handler=handler,
                confidence=result.primary_intent.confidence,
                payload=payload,
                reason=result.reasoning,
                assumptions=assumptions_needing_confirmation,
            )

        except Exception as e:
            logger.error(f"LLM classification failed: {e}", exc_info=True)
            # Fall back to default handler on error
            return self._route_fallback(payload)

    def _route_fallback(self, payload: ContextPayload) -> RoutingDecision:
        """Default fallback routing for unrecognized input.

        Args:
            payload: User context that couldn't be classified.

        Returns:
            RoutingDecision for the default/chat handler.
        """
        logger.info("Routing to default chat handler")
        return RoutingDecision(
            handler="chat_handler",
            confidence=0.3,
            payload=payload,
            reason="No specific intent detected, using default chat handler",
        )


# Singleton instance
_router: ContextRouter | None = None


def get_context_router(
    intent_decipherer: IntentDeciphererAgent | None = None,
    force_new: bool = False,
) -> ContextRouter:
    """Get the singleton context router instance.

    Args:
        intent_decipherer: Optional Intent Decipherer Agent to inject.
        force_new: Force creation of a new instance.

    Returns:
        Context router instance.
    """
    global _router
    if _router is None or force_new:
        _router = ContextRouter(intent_decipherer=intent_decipherer)
    return _router
