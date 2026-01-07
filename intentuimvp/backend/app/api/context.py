"""Context submission endpoint for routing user input and assumption reconciliation."""

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.assumption_store import get_assumption_store
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
    session_id: str | None = None
    should_auto_execute: bool = False


class AssumptionResolutionRequest(BaseModel):
    """Request model for resolving a single assumption."""

    assumption_id: str
    action: Literal["accept", "reject", "edit"]
    edited_text: str | None = None
    session_id: str | None = None


class BatchAssumptionResolutionRequest(BaseModel):
    """Request model for resolving multiple assumptions at once."""

    session_id: str | None = None
    resolutions: list[dict]  # Each dict has assumption_id, action, edited_text


class ResolvedAssumption(BaseModel):
    """Model for a resolved assumption."""

    assumption_id: str
    action: Literal["accept", "reject", "edit"]
    original_text: str
    final_text: str
    category: str
    timestamp: str


@router.post("/api/context", response_model=ContextResponse)
async def submit_context(payload: ContextPayload) -> ContextResponse:
    """Submit user context for routing.

    Accepts user text input and optional attachments, routes them
    through the context router, and returns the routing decision
    including any assumptions that need user confirmation.

    If assumptions are present, creates a session for tracking
    assumption resolutions.

    Args:
        payload: User context with text and optional attachments.

    Returns:
        Response with handler, confidence, reasoning, assumptions,
        session_id, and auto-execute flag.

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

        # Create session if assumptions exist
        session_id = None
        should_auto_execute = False

        if decision.assumptions:
            store = get_assumption_store()
            session_id = store.create_session()

        # Determine if auto-execute is appropriate
        # (This would come from the IntentDecipherer in a full implementation)
        if decision.confidence >= 0.8 and not decision.assumptions:
            should_auto_execute = True

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
            session_id=session_id,
            should_auto_execute=should_auto_execute,
        )

    except Exception as e:
        logger.error(f"Context routing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal routing error") from e


@router.post("/api/context/assumptions/resolve")
async def resolve_assumption(request: AssumptionResolutionRequest) -> ResolvedAssumption:
    """Resolve a single assumption by accepting, rejecting, or editing it.

    This endpoint allows the frontend to send user decisions about
    assumptions. The resolution is stored and can be retrieved later
    for use in action execution.

    Args:
        request: The assumption resolution request.

    Returns:
        The recorded resolution.

    Raises:
        HTTPException: If resolution fails or request is invalid.
    """
    try:
        store = get_assumption_store()

        # Validate edit action has edited_text
        if request.action == "edit" and not request.edited_text:
            raise HTTPException(
                status_code=400,
                detail="edited_text is required when action is 'edit'"
            )

        # For now, we don't have the original assumption text
        # In a full implementation, this would be fetched from the session
        # or passed along with the original request
        original_text = "[original text not available]"

        resolution = store.resolve_assumption(
            session_id=request.session_id or "default",
            assumption_id=request.assumption_id,
            action=request.action,
            original_text=original_text,
            category="unknown",
            edited_text=request.edited_text,
        )

        return ResolvedAssumption(
            assumption_id=resolution["assumption_id"],
            action=resolution["action"],
            original_text=resolution["original_text"],
            final_text=resolution["final_text"],
            category=resolution["category"],
            timestamp=str(resolution["timestamp"]),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assumption resolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resolve assumption") from e


@router.post("/api/context/assumptions/batch-resolve")
async def batch_resolve_assumptions(request: BatchAssumptionResolutionRequest) -> dict[str, Any]:
    """Resolve multiple assumptions at once.

    This batch endpoint allows efficient resolution of multiple assumptions
    in a single request.

    Args:
        request: Batch resolution request with session and resolutions list.

    Returns:
        Summary of resolved assumptions.

    Raises:
        HTTPException: If resolution fails.
    """
    try:
        store = get_assumption_store()
        session_id = request.session_id or "default"

        results = []
        for resolution in request.resolutions:
            result = store.resolve_assumption(
                session_id=session_id,
                assumption_id=resolution.get("assumption_id", ""),
                action=resolution.get("action", "accept"),
                original_text=resolution.get("original_text", "[not available]"),
                category=resolution.get("category", "unknown"),
                edited_text=resolution.get("edited_text"),
            )
            results.append(result)

        return {
            "session_id": session_id,
            "resolved_count": len(results),
            "resolutions": results,
        }

    except Exception as e:
        logger.error(f"Batch assumption resolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resolve assumptions") from e


@router.get("/api/context/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """Get a session's assumption resolutions.

    Args:
        session_id: The session ID.

    Returns:
        Session data with resolved assumptions.

    Raises:
        HTTPException: If session not found.
    """
    store = get_assumption_store()
    session = store.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session["id"],
        "created_at": session["created_at"],
        "resolved_assumptions": session["resolved_assumptions"],
        "is_complete": session["is_complete"],
    }


@router.post("/api/context/sessions/{session_id}/complete")
async def complete_session(session_id: str) -> dict[str, str]:
    """Mark a session as complete.

    This indicates the user has finished reviewing assumptions
    and the action can proceed with the resolved values.

    Args:
        session_id: The session ID.

    Returns:
        Confirmation message.

    Raises:
        HTTPException: If session not found.
    """
    store = get_assumption_store()

    if not store.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    store.mark_complete(session_id)

    return {
        "status": "completed",
        "session_id": session_id,
    }
