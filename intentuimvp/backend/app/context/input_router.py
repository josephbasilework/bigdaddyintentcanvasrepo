"""Input router that combines high-level classification with intent routing."""

from __future__ import annotations

import logging
import re

from app.api.assumption_store import get_assumption_store
from app.context.models import ContextPayload, RoutingDecision
from app.context.router import ContextRouter, get_context_router
from app.services.input_classifier import (
    InputClassificationType,
    InputClassifier,
)
from app.services.intent_memory import get_intent_memory_store

logger = logging.getLogger(__name__)

# Pattern to detect explicit rule teaching via "learn:" or "remember:" prefix
_LEARN_PREFIX_RE = re.compile(
    r"^(?:learn|remember|teach)\s*:\s*(?P<rule>.+)",
    re.I | re.DOTALL,
)


class InputRouter:
    """Routes inputs based on high-level classification."""

    def __init__(
        self,
        *,
        classifier: InputClassifier | None = None,
        context_router: ContextRouter | None = None,
    ) -> None:
        self._classifier = classifier or InputClassifier()
        self._context_router = context_router or get_context_router()

    async def route(
        self,
        payload: ContextPayload,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        workspace_id: str | int | None = None,
    ) -> RoutingDecision:
        """Route input using classification, falling back to intent routing for commands."""
        memory_store = None
        if user_id:
            try:
                memory_store = get_intent_memory_store()
            except Exception:
                memory_store = None

        # Check for explicit rule teaching via "learn:" prefix
        if memory_store and user_id:
            learn_match = _LEARN_PREFIX_RE.match(payload.text.strip())
            if learn_match:
                rule_text = learn_match.group("rule").strip()
                explicit_rule = memory_store.record_explicit_rule(
                    user_id=user_id,
                    text=rule_text,
                    workspace_id=workspace_id,
                    session_id=session_id,
                )
                if explicit_rule is not None:
                    ack_payload = ContextPayload(
                        text=explicit_rule.acknowledgement,
                        attachments=payload.attachments,
                        selection=payload.selection,
                    )
                    return RoutingDecision(
                        handler="chat_handler",
                        confidence=1.0,
                        payload=ack_payload,
                        reason="Intent memory rule stored via learn prefix",
                    )
                # If the rule didn't parse, give helpful feedback
                ack_payload = ContextPayload(
                    text=(
                        "I couldn't understand that rule. Try a format like:\n"
                        "learn: when I say [trigger], route to /[command]\n"
                        "learn: when I note [topic], suggest [action1] and [action2]"
                    ),
                    attachments=payload.attachments,
                    selection=payload.selection,
                )
                return RoutingDecision(
                    handler="chat_handler",
                    confidence=1.0,
                    payload=ack_payload,
                    reason="Learn prefix detected but rule not understood",
                )

        # Try natural language rule capture (without prefix)
        if memory_store and user_id:
            explicit_rule = memory_store.record_explicit_rule(
                user_id=user_id,
                text=payload.text,
                workspace_id=workspace_id,
                session_id=session_id,
            )
            if explicit_rule is not None:
                ack_payload = ContextPayload(
                    text=explicit_rule.acknowledgement,
                    attachments=payload.attachments,
                    selection=payload.selection,
                )
                return RoutingDecision(
                    handler="chat_handler",
                    confidence=1.0,
                    payload=ack_payload,
                    reason="Intent memory rule stored",
                )
            routing_match = memory_store.match_routing(
                user_id=user_id,
                text=payload.text,
                workspace_id=workspace_id,
                session_id=session_id,
            )
            if routing_match is not None:
                response = routing_match.entry.response or {}
                handler = None
                if isinstance(response, dict):
                    handler = response.get("handler")
                if handler:
                    memory_store.log_audit_event(
                        user_id,
                        "auto_route_applied",
                        {
                            "entry_id": routing_match.entry.entry_id,
                            "scope": routing_match.entry.scope.value,
                            "handler": handler,
                        },
                    )
                    return RoutingDecision(
                        handler=handler,
                        confidence=min(0.95, routing_match.score),
                        payload=payload,
                        reason="Intent memory routing rule matched",
                    )

        classification = await self._classifier.classify(
            payload,
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )

        if classification.input_type == InputClassificationType.COMMAND:
            handler_override = classification.signals.get("intent_memory_handler")
            if handler_override:
                return RoutingDecision(
                    handler=str(handler_override),
                    confidence=classification.confidence,
                    payload=payload,
                    reason="Intent memory rule matched",
                    assumptions=[],
                )
            decision = await self._context_router.route(payload)
            reason = (
                f"Input classified as command ({classification.confidence:.2f}). "
                f"{decision.reason}"
            )
            return RoutingDecision(
                handler=decision.handler,
                confidence=decision.confidence,
                payload=payload,
                reason=reason,
                assumptions=decision.assumptions,
            )

        handler = _handler_for_classification(classification.input_type)
        if (
            classification.input_type
            == InputClassificationType.CLARIFICATION_RESPONSE
            and session_id
        ):
            try:
                store = get_assumption_store()
                store.record_clarification(session_id, payload.text)
            except Exception:
                logger.warning("Failed to store clarification response", exc_info=True)

        return RoutingDecision(
            handler=handler,
            confidence=classification.confidence,
            payload=payload,
            reason=classification.reason,
        )


def _handler_for_classification(classification: InputClassificationType) -> str:
    if classification == InputClassificationType.QUESTION:
        return "chat_handler"
    if classification == InputClassificationType.NOTE:
        return "note_handler"
    if classification == InputClassificationType.CONFIGURATION:
        return "configuration_handler"
    if classification == InputClassificationType.CLARIFICATION_RESPONSE:
        return "clarification_response_handler"
    return ContextRouter.DISAMBIGUATION_HANDLER


_input_router: InputRouter | None = None


def get_input_router(
    *,
    classifier: InputClassifier | None = None,
    context_router: ContextRouter | None = None,
    force_new: bool = False,
) -> InputRouter:
    """Get singleton input router instance."""
    global _input_router
    if _input_router is None or force_new:
        _input_router = InputRouter(
            classifier=classifier,
            context_router=context_router,
        )
    return _input_router
