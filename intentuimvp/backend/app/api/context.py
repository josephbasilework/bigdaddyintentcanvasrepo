"""Context submission endpoint for routing user input."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.context.models import ContextPayload
from app.context.router import get_context_router

router = APIRouter()
logger = logging.getLogger(__name__)


class AssumptionResponse(BaseModel):
    """Response model for an assumption."""

    id: str
    text: str
    confidence: float
    category: str
    explanation: str | None = None


class ContextResponse(BaseModel):
    """Response model for context routing."""

    handler: str
    confidence: float
    reason: str
    assumptions: list[AssumptionResponse]
    status: str


class AssumptionResolutionRequest(BaseModel):
    """Request model for resolving assumptions."""

    assumption_id: str
    accepted: bool


@router.post("/api/context", response_model=ContextResponse)
async def submit_context(payload: ContextPayload) -> ContextResponse:
    """Submit user context for routing.

    Accepts user text input and optional attachments, routes them
    through the context router, and returns the routing decision
    including any assumptions that need user confirmation.

    Args:
        payload: User context with text and optional attachments.

    Returns:
        Response with handler, confidence, reasoning, and assumptions.

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
                "assumptions_count": len(decision.assumptions),
            },
        )

        # Convert assumptions to response format
        assumption_responses = [
            AssumptionResponse(
                id=a.id,
                text=a.text,
                confidence=a.confidence,
                category=a.category,
                explanation=a.explanation,
            )
            for a in decision.assumptions
        ]

        return ContextResponse(
            handler=decision.handler,
            confidence=decision.confidence,
            reason=decision.reason,
            assumptions=assumption_responses,
            status="routed" if not decision.assumptions else "awaiting_assumptions",
        )

    except Exception as e:
        logger.error(f"Context routing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal routing error") from e


@router.post("/api/context/assumptions/resolve")
async def resolve_assumption(request: AssumptionResolutionRequest) -> dict[str, str]:
    """Resolve an assumption by accepting or rejecting it.

    This endpoint allows the frontend to send user decisions about
    assumptions. The resolution can be stored for later use in
    action execution.

    Args:
        request: The assumption resolution request with ID and decision.

    Returns:
        Confirmation message.

    Raises:
        HTTPException: If resolution fails.
    """
    try:
        logger.info(
            f"Assumption {request.assumption_id} resolved: {'accepted' if request.accepted else 'rejected'}"
        )

        # TODO: Store assumption resolution for later use in execution
        # For now, just log and return success

        return {
            "status": "resolved",
            "assumption_id": request.assumption_id,
            "decision": "accepted" if request.accepted else "rejected",
        }

    except Exception as e:
        logger.error(f"Assumption resolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resolve assumption") from e
