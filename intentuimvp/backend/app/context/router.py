"""Context routing pipeline.

Routes user input to appropriate handlers based on slash commands,
LLM classification, or fallback behavior.
"""

import logging
import re

from app.context.models import ContextPayload, RoutingDecision

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

    def __init__(self) -> None:
        """Initialize the context router."""
        # LLM classifier could be injected here for future use
        self._use_llm_classification: bool = False

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
        """Route using LLM classification.

        This is a placeholder for future LLM-based classification.
        When implemented, it will:
        - Call the Gateway with the user input
        - Classify the intent (research, chat, code, etc.)
        - Return the appropriate handler

        Args:
            payload: User context to classify.

        Returns:
            RoutingDecision based on LLM classification.
        """
        # TODO: Implement LLM classification via Gateway
        # For now, fall through to default
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


def get_context_router() -> ContextRouter:
    """Get the singleton context router instance.

    Returns:
        Context router instance.
    """
    global _router
    if _router is None:
        _router = ContextRouter()
    return _router
