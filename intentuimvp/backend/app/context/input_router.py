"""Input router that combines high-level classification with intent routing."""

from __future__ import annotations

import logging

from app.api.assumption_store import get_assumption_store
from app.context.models import ContextPayload, RoutingDecision
from app.context.router import ContextRouter, get_context_router
from app.services.input_classifier import (
    InputClassificationType,
    InputClassifier,
)

logger = logging.getLogger(__name__)


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
    ) -> RoutingDecision:
        """Route input using classification, falling back to intent routing for commands."""
        classification = await self._classifier.classify(payload, user_id=user_id)

        if classification.input_type == InputClassificationType.COMMAND:
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
