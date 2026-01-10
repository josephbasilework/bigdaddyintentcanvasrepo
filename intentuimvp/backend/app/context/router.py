"""Context routing pipeline.

Routes user input to appropriate handlers using a three-level priority:
1) Exact slash command matching
2) LLM intent classification
3) Keyword fallback patterns
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Protocol, TypeAlias

from app.agents.intent_decipherer import (
    IntentDeciphererAgent,
    IntentDecipheringResult,
    get_intent_decipherer,
)
from app.context.models import Assumption, ContextPayload, RoutingDecision, parse_assumption

logger = logging.getLogger(__name__)

# Known slash commands and their handlers
SLASH_COMMANDS = {
    "/research": "research_handler",
    "/help": "help_handler",
    "/clear": "clear_handler",
    "/plan": "plan_handler",
    "/judge": "judge_handler",
    "/dashboard": "dashboard_handler",
    "/graph": "graph_handler",
    "/export": "export_handler",
    "/calendar": "calendar_handler",
}

# Pattern to match slash commands at the start of input
SLASH_PATTERN = re.compile(r"^(/[\w-]+)\s*")

# Keyword fallback patterns for common phrases
KEYWORD_PATTERNS: list[tuple[re.Pattern[str], str, float, str]] = [
    (
        re.compile(r"\b(research|look up|find sources|investigate)\b", re.I),
        "research_handler",
        0.6,
        "research",
    ),
    (
        re.compile(r"\b(plan|outline|roadmap)\b", re.I),
        "plan_handler",
        0.55,
        "plan",
    ),
    (
        re.compile(r"\b(judge|evaluate|critique)\b", re.I),
        "judge_handler",
        0.55,
        "judge",
    ),
    (
        re.compile(r"\b(analy[sz]e|analysis|summarize|summarise|compare)\b", re.I),
        "analyze_handler",
        0.55,
        "analyze",
    ),
    (
        re.compile(r"\b(create|add|make|draft|generate)\b", re.I),
        "create_handler",
        0.52,
        "create",
    ),
    (
        re.compile(r"\b(clear|reset|start over)\b", re.I),
        "clear_handler",
        0.6,
        "clear",
    ),
    (
        re.compile(r"\b(help|what can you do|how do i)\b", re.I),
        "help_handler",
        0.6,
        "help",
    ),
]


class LLMRoutingError(RuntimeError):
    """Raised when LLM routing fails and should fall back to keywords."""


class IntentDeciphererProtocol(Protocol):
    """Protocol for intent decipherer implementations used by the router."""

    confidence_threshold: float
    assumption_confidence_threshold: float

    async def decipher(self, text: str) -> IntentDecipheringResult: ...


IntentDecipherer: TypeAlias = IntentDeciphererAgent | IntentDeciphererProtocol


@dataclass
class _RoutingCandidate:
    handler: str
    confidence: float
    reason: str
    assumptions: list[Assumption] = field(default_factory=list)


def _is_llm_failure(reason: str) -> bool:
    """Detect LLM failure from intent decipherer reasoning."""
    return reason.lower().startswith("intent deciphering encountered an error")


class ContextRouter:
    """Routes user context to appropriate handlers.

    Priority order:
    1. Slash commands (exact match at start of input)
    2. LLM classification (for natural language intent)
    3. Keyword fallback patterns
    """

    # Intent to handler mapping
    INTENT_HANDLERS = {
        "research": "research_handler",
        "chat": "chat_handler",
        "create": "create_handler",
        "analyze": "analyze_handler",
        "help": "help_handler",
        "clear": "clear_handler",
        "plan": "plan_handler",
        "judge": "judge_handler",
        "dashboard": "dashboard_handler",
        "graph": "graph_handler",
        "export": "export_handler",
        "calendar": "calendar_handler",
    }

    DEFAULT_HANDLER = "chat_handler"
    DISAMBIGUATION_HANDLER = "clarification_handler"
    DEFAULT_CLARIFICATION_CONFIDENCE_THRESHOLD = (
        IntentDeciphererAgent.DEFAULT_ASSUMPTION_CONFIDENCE_THRESHOLD
    )

    def __init__(
        self,
        intent_decipherer: IntentDecipherer | None = None,
        *,
        classification_timeout: float = 0.5,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_window: float = 30.0,
        clarification_confidence_threshold: float = DEFAULT_CLARIFICATION_CONFIDENCE_THRESHOLD,
    ) -> None:
        """Initialize the context router.

        Args:
            intent_decipherer: Optional Intent Decipherer Agent instance.
                            If None, uses singleton.
            classification_timeout: Max seconds to wait for LLM classification.
            circuit_breaker_threshold: Consecutive failures before opening the circuit.
            circuit_breaker_window: Duration in seconds to keep circuit open.
        """
        self._use_llm_classification: bool = True
        self._intent_decipherer = intent_decipherer
        self._classification_timeout = classification_timeout
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._circuit_breaker_window = circuit_breaker_window
        self._clarification_confidence_threshold = clarification_confidence_threshold
        self._consecutive_failures = 0
        self._circuit_open_until: float | None = None

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

        # 2. LLM classification (with timeout + circuit breaker)
        if self._use_llm_classification:
            if self._is_circuit_open():
                logger.warning("Circuit breaker open; bypassing LLM classification")
                return self._route_keyword_fallback(
                    payload, reason_prefix="Circuit breaker open"
                )

            try:
                decision = await asyncio.wait_for(
                    self._route_via_llm(payload),
                    timeout=self._classification_timeout,
                )
                self._record_success()
                return decision
            except TimeoutError:
                self._record_failure()
                logger.warning("LLM classification timed out; falling back to keywords")
                return self._route_keyword_fallback(
                    payload, reason_prefix="LLM classification timed out"
                )
            except LLMRoutingError as e:
                self._record_failure()
                logger.warning(f"LLM classification failed: {e}")
                return self._route_keyword_fallback(payload, reason_prefix=str(e))
            except Exception as e:
                self._record_failure()
                logger.error(f"LLM classification failed: {e}", exc_info=True)
                return self._route_keyword_fallback(
                    payload, reason_prefix="LLM classification failed"
                )

        # 3. Fallback to keyword patterns when LLM is disabled
        return self._route_keyword_fallback(payload, reason_prefix="LLM disabled")

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

        result = await self._intent_decipherer.decipher(payload.text)
        if _is_llm_failure(result.reasoning):
            raise LLMRoutingError("LLM classification error")

        # Convert assumption dicts to Assumption objects
        assumptions = []
        for assumption_payload in result.assumptions:
            try:
                assumptions.append(parse_assumption(assumption_payload))
            except ValueError as exc:
                logger.warning(
                    "Skipping invalid assumption payload from LLM",
                    extra={"error": str(exc)},
                )

        # Filter to only include assumptions below confidence threshold
        # These need user confirmation
        assumption_threshold = self._intent_decipherer.assumption_confidence_threshold
        assumptions_needing_confirmation = [
            a for a in assumptions if a.confidence < assumption_threshold
        ]

        intents = [result.primary_intent, *result.alternative_intents]
        candidates: list[_RoutingCandidate] = []
        for intent in intents:
            intent_name = intent.name.lower()
            handler = self.INTENT_HANDLERS.get(intent_name, self.DEFAULT_HANDLER)
            reason = f"LLM intent '{intent_name}' ({intent.confidence:.2f})"
            if result.reasoning:
                reason = f"{reason}. {result.reasoning}"
            candidates.append(
                _RoutingCandidate(
                    handler=handler,
                    confidence=float(intent.confidence),
                    reason=reason,
                    assumptions=assumptions_needing_confirmation,
                )
            )

        if not candidates:
            raise LLMRoutingError("LLM classification returned no routable intents")

        decision = self._select_candidate(
            candidates,
            payload,
            priority_label="LLM",
        )

        if decision.confidence < self._clarification_confidence_threshold:
            reason = (
                f"LLM confidence {decision.confidence:.2f} below threshold "
                f"{self._clarification_confidence_threshold:.2f}; request clarification. "
                f"{decision.reason}"
            )
            logger.info(
                "LLM confidence below threshold; requesting clarification",
                extra={
                    "handler": self.DISAMBIGUATION_HANDLER,
                    "confidence": decision.confidence,
                    "assumptions_count": len(decision.assumptions),
                    "should_auto_execute": result.should_auto_execute,
                },
            )
            return RoutingDecision(
                handler=self.DISAMBIGUATION_HANDLER,
                confidence=decision.confidence,
                payload=payload,
                reason=reason,
                assumptions=decision.assumptions,
            )

        logger.info(
            f"LLM routed -> {decision.handler} (confidence: {decision.confidence:.2f})",
            extra={
                "handler": decision.handler,
                "confidence": decision.confidence,
                "assumptions_count": len(decision.assumptions),
                "should_auto_execute": result.should_auto_execute,
            },
        )

        return decision

    def _route_keyword_fallback(
        self,
        payload: ContextPayload,
        *,
        reason_prefix: str | None = None,
    ) -> RoutingDecision:
        """Route using keyword fallback patterns.

        Args:
            payload: User context for matching.
            reason_prefix: Optional prefix to include in routing reason.

        Returns:
            RoutingDecision for keyword match or clarification.
        """
        text = payload.text.strip()
        candidates: list[_RoutingCandidate] = []
        for pattern, handler, confidence, label in KEYWORD_PATTERNS:
            if pattern.search(text):
                candidates.append(
                    _RoutingCandidate(
                        handler=handler,
                        confidence=confidence,
                        reason=f"Keyword match: {label}",
                    )
                )

        if not candidates:
            reason = "No keyword matches; request clarification"
            if reason_prefix:
                reason = f"{reason_prefix}. {reason}"
            return RoutingDecision(
                handler=self.DISAMBIGUATION_HANDLER,
                confidence=0.2,
                payload=payload,
                reason=reason,
            )

        return self._select_candidate(
            candidates,
            payload,
            priority_label="keyword",
            reason_prefix=reason_prefix,
        )

    def _select_candidate(
        self,
        candidates: list[_RoutingCandidate],
        payload: ContextPayload,
        *,
        priority_label: str,
        reason_prefix: str | None = None,
    ) -> RoutingDecision:
        """Select the best candidate by confidence, handling ties."""
        max_confidence = max(candidate.confidence for candidate in candidates)
        top = [
            candidate
            for candidate in candidates
            if math.isclose(candidate.confidence, max_confidence, rel_tol=1e-6, abs_tol=1e-6)
        ]
        handlers = {candidate.handler for candidate in top}

        if len(handlers) > 1:
            options = ", ".join(sorted(handlers))
            reason = (
                f"Ambiguous {priority_label} match at confidence "
                f"{max_confidence:.2f}; need disambiguation ({options})"
            )
            if reason_prefix:
                reason = f"{reason_prefix}. {reason}"
            return RoutingDecision(
                handler=self.DISAMBIGUATION_HANDLER,
                confidence=max_confidence,
                payload=payload,
                reason=reason,
            )

        selected = top[0]
        reason = selected.reason
        if reason_prefix:
            reason = f"{reason_prefix}. {reason}"
        return RoutingDecision(
            handler=selected.handler,
            confidence=selected.confidence,
            payload=payload,
            reason=reason,
            assumptions=selected.assumptions,
        )

    def _is_circuit_open(self) -> bool:
        """Return True if the circuit breaker is open."""
        if self._circuit_open_until is None:
            return False
        if time.monotonic() >= self._circuit_open_until:
            self._circuit_open_until = None
            self._consecutive_failures = 0
            return False
        return True

    def _record_failure(self) -> None:
        """Record a failure and open the circuit breaker if needed."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_breaker_threshold:
            self._circuit_open_until = time.monotonic() + self._circuit_breaker_window
            self._consecutive_failures = 0
            logger.warning(
                "Circuit breaker opened for %.0fs", self._circuit_breaker_window
            )

    def _record_success(self) -> None:
        """Reset failure counters after successful classification."""
        self._consecutive_failures = 0


# Singleton instance
_router: ContextRouter | None = None


def get_context_router(
    intent_decipherer: IntentDecipherer | None = None,
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
