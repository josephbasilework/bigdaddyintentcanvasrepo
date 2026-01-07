"""Context submission endpoint for routing user input."""

import logging

from fastapi import APIRouter, HTTPException

from app.context.models import ContextPayload
from app.context.router import get_context_router

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/context")
async def submit_context(payload: ContextPayload) -> dict[str, object]:
    """Submit user context for routing.

    Accepts user text input and optional attachments, routes them
    through the context router, and returns the routing decision.

    Args:
        payload: User context with text and optional attachments.

    Returns:
        Response with handler, confidence, and reasoning.

    Raises:
        HTTPException: If routing fails or input is invalid.
    """
    # Validate input
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text field cannot be empty")

    # Sanitize input (basic length check)
    max_text_length = 10000
    if len(payload.text) > max_text_length:
        raise HTTPException(
            status_code=400,
            detail=f"Text exceeds maximum length of {max_text_length} characters",
        )

    try:
        # Route through context router
        context_router = get_context_router()
        decision = await context_router.route(payload)

        logger.info(
            f"Context routed to {decision.handler}",
            extra={
                "handler": decision.handler,
                "confidence": decision.confidence,
            },
        )

        return {
            "handler": decision.handler,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "status": "routed",
        }

    except Exception as e:
        logger.error(f"Context routing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal routing error") from e
