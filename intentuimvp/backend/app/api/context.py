"""Context submission endpoint for routing user input and assumption reconciliation."""

import logging
import uuid
from typing import Any, Literal, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.intent_decipherer import IntentDeciphererAgent, get_intent_decipherer
from app.api.assumption_store import get_assumption_store
from app.context.models import ContextPayload
from app.context.router import get_context_router
from app.database import get_db
from app.models.intent import AssumptionResolutionDB

router = APIRouter()
logger = logging.getLogger(__name__)


def get_decipherer() -> IntentDeciphererAgent:
    """Get the intent decipherer instance for dependency injection."""
    return get_intent_decipherer()


def _validate_text(text: str) -> None:
    """Validate incoming text payloads."""
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text field cannot be empty")

    max_text_length = 10000
    if len(text) > max_text_length:
        raise HTTPException(
            status_code=400,
            detail=f"Text exceeds maximum length of {max_text_length} characters",
        )


def _raise_internal_error(message: str, error: Exception) -> NoReturn:
    """Raise a 500 HTTPException with a correlation ID for tracing."""
    correlation_id = str(uuid.uuid4())
    logger.error(
        message,
        extra={"correlation_id": correlation_id},
        exc_info=True,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"message": message, "correlation_id": correlation_id},
    ) from error


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


class AssumptionGenerationRequest(BaseModel):
    """Request model for generating assumptions from user input."""

    text: str
    attachments: list[str] | None = None


class IntentAlternative(BaseModel):
    """Alternative intent classification for ambiguity handling."""

    name: str
    confidence: float
    description: str


class AssumptionSetResponse(BaseModel):
    """Response model for generated assumptions and intent options."""

    intent: str
    intent_description: str | None = None
    confidence: float
    alternatives: list[IntentAlternative]
    assumptions: list[AssumptionResponse]
    reasoning: str
    should_auto_execute: bool
    session_id: str | None = None


class AssumptionResolutionPayload(BaseModel):
    """Payload for a single assumption resolution."""

    assumption_id: str
    action: Literal["accept", "reject", "edit"]
    edited_text: str | None = None
    original_text: str | None = None
    category: str | None = None
    feedback: str | None = None


class AssumptionResolutionRequest(BaseModel):
    """Request model for resolving a single assumption."""

    assumption_id: str
    action: Literal["accept", "reject", "edit"]
    edited_text: str | None = None
    original_text: str | None = None
    category: str | None = None
    feedback: str | None = None
    session_id: str | None = None


class BatchAssumptionResolutionRequest(BaseModel):
    """Request model for resolving multiple assumptions at once."""

    session_id: str | None = None
    resolutions: list[AssumptionResolutionPayload]


class ResolvedAssumption(BaseModel):
    """Model for a resolved assumption."""

    assumption_id: str
    action: Literal["accept", "reject", "edit"]
    original_text: str
    final_text: str
    category: str
    timestamp: str
    feedback: str | None = None


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
    _validate_text(payload.text)

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


@router.post("/api/context/assumptions", response_model=AssumptionSetResponse)
async def generate_assumptions(
    payload: AssumptionGenerationRequest,
    decipherer: IntentDeciphererAgent = Depends(get_decipherer),
) -> AssumptionSetResponse:
    """Generate assumptions and intent alternatives for HITL confirmation."""
    _validate_text(payload.text)

    try:
        result = await decipherer.decipher(payload.text)

        alternatives = [
            IntentAlternative(
                name=alt.name,
                confidence=alt.confidence,
                description=alt.description,
            )
            for alt in result.alternative_intents
        ]

        assumption_responses = []
        for assumption in result.assumptions:
            assumption_id = assumption.get("id") or str(uuid.uuid4())
            assumption_responses.append(
                AssumptionResponse(
                    id=assumption_id,
                    text=assumption.get("text", ""),
                    confidence=assumption.get("confidence", 0.5),
                    category=assumption.get("category", "other"),
                    explanation=assumption.get("explanation"),
                )
            )

        assumptions_needing_confirmation = [
            a
            for a in assumption_responses
            if a.confidence < decipherer.confidence_threshold
        ]

        session_id = None
        if assumptions_needing_confirmation:
            store = get_assumption_store()
            session_id = store.create_session()

        should_auto_execute = bool(result.should_auto_execute) and not assumptions_needing_confirmation

        return AssumptionSetResponse(
            intent=result.primary_intent.name,
            intent_description=result.primary_intent.description,
            confidence=result.primary_intent.confidence,
            alternatives=alternatives,
            assumptions=assumptions_needing_confirmation,
            reasoning=result.reasoning,
            should_auto_execute=should_auto_execute,
            session_id=session_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        _raise_internal_error("Failed to generate assumptions", e)


@router.post("/api/context/assumptions/resolve")
async def resolve_assumption(
    request: AssumptionResolutionRequest,
    db: Session = Depends(get_db),
) -> ResolvedAssumption:
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
                detail="edited_text is required when action is 'edit'",
            )

        original_text = request.original_text or "[original text not available]"
        category = request.category or "unknown"

        resolution = store.resolve_assumption(
            session_id=request.session_id or "default",
            assumption_id=request.assumption_id,
            action=request.action,
            original_text=original_text,
            category=category,
            edited_text=request.edited_text,
            feedback=request.feedback,
        )

        db_record = AssumptionResolutionDB(
            session_id=request.session_id or "default",
            assumption_id=request.assumption_id,
            action=request.action,
            original_text=original_text,
            final_text=resolution["final_text"],
            category=category,
        )
        db.add(db_record)
        db.commit()

        return ResolvedAssumption(
            assumption_id=resolution["assumption_id"],
            action=resolution["action"],
            original_text=resolution["original_text"],
            final_text=resolution["final_text"],
            category=resolution["category"],
            timestamp=str(resolution["timestamp"]),
            feedback=resolution.get("feedback"),
        )

    except HTTPException:
        raise
    except Exception as e:
        _raise_internal_error("Failed to resolve assumption", e)


@router.post("/api/context/assumptions/batch-resolve")
async def batch_resolve_assumptions(
    request: BatchAssumptionResolutionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
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
        db_records = []
        for resolution in request.resolutions:
            if resolution.action == "edit" and not resolution.edited_text:
                raise HTTPException(
                    status_code=400,
                    detail="edited_text is required when action is 'edit'",
                )
            original_text = resolution.original_text or "[not available]"
            category = resolution.category or "unknown"
            result = store.resolve_assumption(
                session_id=session_id,
                assumption_id=resolution.assumption_id,
                action=resolution.action,
                original_text=original_text,
                category=category,
                edited_text=resolution.edited_text,
                feedback=resolution.feedback,
            )
            results.append(result)
            db_records.append(
                AssumptionResolutionDB(
                    session_id=session_id,
                    assumption_id=resolution.assumption_id,
                    action=resolution.action,
                    original_text=original_text,
                    final_text=result["final_text"],
                    category=category,
                )
            )

        if db_records:
            db.add_all(db_records)
            db.commit()

        return {
            "session_id": session_id,
            "resolved_count": len(results),
            "resolutions": results,
        }

    except Exception as e:
        _raise_internal_error("Failed to resolve assumptions", e)


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
