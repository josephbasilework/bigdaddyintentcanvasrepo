"""Context submission endpoint for routing user input and assumption reconciliation."""

import asyncio
import logging
import uuid
from typing import Any, Literal, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.intent_decipherer import IntentDeciphererAgent, get_intent_decipherer
from app.api.assumption_store import get_assumption_store
from app.context.assembly import get_context_assembler
from app.context.models import ContextPayload, SelectionScope, parse_assumption
from app.context.router import ContextRouter, get_context_router
from app.database import AsyncSessionLocal, get_db
from app.models.intent import AssumptionResolutionDB
from app.models.turn import ResponseType, TurnActor, TurnType
from app.repositories.intent_repo import IntentRepository
from app.services.turns import (
    log_turn_with_new_async_session,
    log_turn_with_session_id_sync,
)

router = APIRouter()
logger = logging.getLogger(__name__)
AUTO_EXECUTE_CONFIDENCE_THRESHOLD = (
    IntentDeciphererAgent.DEFAULT_AUTO_EXECUTE_CONFIDENCE_THRESHOLD
)


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


def _validate_preview_text(text: str | None) -> str:
    """Validate preview text payloads (allowing empty input)."""
    if text is None:
        return ""
    max_text_length = 10000
    if len(text) > max_text_length:
        raise HTTPException(
            status_code=400,
            detail=f"Text exceeds maximum length of {max_text_length} characters",
        )
    return text


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
    status: Literal["pending", "accepted", "rejected"]


class ContextResponse(BaseModel):
    """Response model for context routing."""

    handler: str
    confidence: float
    reason: str
    assumptions: list[AssumptionResponse]
    status: str
    session_id: str | None = None
    should_auto_execute: bool = False


class ContextPreviewRequest(BaseModel):
    """Request model for context preview."""

    text: str | None = None
    attachments: list[str] | None = None
    selection: SelectionScope | None = None
    session_id: str | None = None
    workspace_id: int | str | None = None


class ContextNodeResponse(BaseModel):
    """Response model for a scored context node."""

    id: str
    title: str
    node_type: str
    score: float
    reasons: list[str]
    is_primary: bool
    similarity: float | None = None
    recency: float | None = None
    reason_scores: dict[str, float] | None = None
    content: str | None = None
    metadata: dict[str, Any] | None = None


class ContextTurnResponse(BaseModel):
    """Response model for a scored context turn."""

    id: int
    sequence_number: int
    summary: str
    actor: str
    turn_type: str
    timestamp: str
    score: float
    reasons: list[str]
    similarity: float | None = None
    recency: float | None = None
    reason_scores: dict[str, float] | None = None


class ContextAttachmentResponse(BaseModel):
    """Response model for attachment metadata in context preview."""

    id: str
    filename: str
    attachment_type: str
    mime_type: str
    size_bytes: int
    text_content: str | None = None
    transcription: str | None = None
    description: str | None = None
    status: str | None = None


class ContextPreviewResponse(BaseModel):
    """Response model for context preview."""

    input_text: str
    prompt: str
    nodes: list[ContextNodeResponse]
    turns: list[ContextTurnResponse]
    attachments: list[ContextAttachmentResponse]
    selection: dict[str, Any] | None = None
    explicit_node_refs: list[str]
    explicit_turn_refs: list[int]


class AssumptionGenerationRequest(BaseModel):
    """Request model for generating assumptions from user input."""

    text: str
    attachments: list[str] | None = None


class IntentAlternative(BaseModel):
    """Alternative intent classification for ambiguity handling."""

    name: str
    confidence: float
    description: str


class ProposalResponse(BaseModel):
    """Response model for a proposal with assumptions."""

    action: str
    confidence: float
    alternatives: list[IntentAlternative]
    assumptions: list[AssumptionResponse]


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
    proposal: ProposalResponse


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
            session_id = store.create_session(
                original_text=payload.text,
                handler=decision.handler,
            )

        # Determine if auto-execute is appropriate using the confidence threshold.
        if (
            decision.confidence >= AUTO_EXECUTE_CONFIDENCE_THRESHOLD
            and not decision.assumptions
        ):
            should_auto_execute = True

        # Convert assumptions to response format
        assumption_responses = [
            AssumptionResponse(
                id=a.id,
                text=a.text,
                confidence=a.confidence,
                category=a.category,
                explanation=a.explanation,
                status=a.status,
            )
            for a in decision.assumptions
        ]

        status_value = "routed"
        if decision.handler == ContextRouter.DISAMBIGUATION_HANDLER:
            status_value = "clarification_required"
        elif decision.assumptions:
            status_value = "awaiting_assumptions"

        return ContextResponse(
            handler=decision.handler,
            confidence=decision.confidence,
            reason=decision.reason,
            assumptions=assumption_responses,
            status=status_value,
            session_id=session_id,
            should_auto_execute=should_auto_execute,
        )

    except Exception as e:
        logger.error(f"Context routing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal routing error") from e


@router.post("/api/context/preview", response_model=ContextPreviewResponse)
async def preview_context(request: ContextPreviewRequest) -> ContextPreviewResponse:
    """Preview the assembled context window with explainability data."""
    try:
        text = _validate_preview_text(request.text)
        payload = ContextPayload(
            text=text,
            attachments=request.attachments,
            selection=request.selection,
        )
        assembler = get_context_assembler()
        window = await assembler.assemble(
            payload,
            user_id="default_user",
            session_id=request.session_id,
            workspace_id=request.workspace_id,
        )
        return ContextPreviewResponse(**window.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        _raise_internal_error("Failed to assemble context preview", e)


@router.post("/api/context/assumptions", response_model=AssumptionSetResponse)
async def generate_assumptions(
    payload: AssumptionGenerationRequest,
    decipherer: IntentDeciphererAgent = Depends(get_decipherer),
) -> AssumptionSetResponse:
    """Generate assumptions and intent alternatives for HITL confirmation."""
    _validate_text(payload.text)

    try:
        result = await decipherer.decipher(payload.text)

        logger.info(f"DEBUG: Raw LLM assumptions: {result.assumptions}")
        logger.info(f"DEBUG: Assumption threshold: {decipherer.assumption_confidence_threshold}")

        alternatives = [
            IntentAlternative(
                name=alt.name,
                confidence=alt.confidence,
                description=alt.description,
            )
            for alt in result.alternative_intents
        ]

        assumption_responses = []
        for assumption_payload in result.assumptions:
            try:
                assumption = parse_assumption(assumption_payload)
            except ValueError as exc:
                logger.warning(
                    "Skipping invalid assumption payload from LLM",
                    extra={"error": str(exc)},
                )
                continue
            assumption_responses.append(
                AssumptionResponse(
                    id=assumption.id,
                    text=assumption.text,
                    confidence=assumption.confidence,
                    category=assumption.category,
                    explanation=assumption.explanation,
                    status=assumption.status,
                )
            )

        logger.info(f"DEBUG: Parsed assumption_responses: {assumption_responses}")

        # Show ALL assumptions to user, not just low-confidence ones
        assumptions_needing_confirmation = assumption_responses

        session_id = None
        if assumptions_needing_confirmation:
            store = get_assumption_store()
            session_id = store.create_session(
                assumptions=[assumption.model_dump() for assumption in assumption_responses],
                original_text=payload.text,
                handler=result.primary_intent.name,
                user_id="default",
            )
            auto_confirmed, remaining = store.apply_auto_confirm(session_id)
            if auto_confirmed:
                remaining_ids = {
                    str(item.get("id", "")).strip() for item in remaining if item.get("id")
                }
                assumptions_needing_confirmation = [
                    assumption
                    for assumption in assumption_responses
                    if assumption.id in remaining_ids
                ]

        should_auto_execute = (
            bool(result.should_auto_execute)
            and result.primary_intent.confidence >= AUTO_EXECUTE_CONFIDENCE_THRESHOLD
            and not assumptions_needing_confirmation
        )

        if session_id and assumptions_needing_confirmation:
            await log_turn_with_new_async_session(
                session_id=session_id,
                actor=TurnActor.AGENT,
                turn_type=TurnType.ASSUMPTION_PRESENTED,
                summary=(
                    f"Proposal requires confirmation for {result.primary_intent.name}"
                ),
                payload={
                    "intent": result.primary_intent.name,
                    "confidence": result.primary_intent.confidence,
                    "assumptions": [
                        assumption.model_dump()
                        for assumption in assumptions_needing_confirmation
                    ],
                    "alternatives": [
                        alt.model_dump() for alt in alternatives
                    ],
                    "reasoning": result.reasoning,
                    "response_type": ResponseType.PROPOSAL.value,
                },
            )

        proposal = ProposalResponse(
            action=result.primary_intent.name,
            confidence=result.primary_intent.confidence,
            alternatives=alternatives,
            assumptions=assumptions_needing_confirmation,
        )

        return AssumptionSetResponse(
            intent=result.primary_intent.name,
            intent_description=result.primary_intent.description,
            confidence=result.primary_intent.confidence,
            alternatives=alternatives,
            assumptions=assumptions_needing_confirmation,
            reasoning=result.reasoning,
            should_auto_execute=should_auto_execute,
            session_id=session_id,
            proposal=proposal,
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

        turn_type = {
            "accept": TurnType.ASSUMPTION_CONFIRMED,
            "reject": TurnType.ASSUMPTION_REJECTED,
            "edit": TurnType.ASSUMPTION_MODIFIED,
        }[request.action]
        log_turn_with_session_id_sync(
            db,
            session_id=request.session_id or "default",
            actor=TurnActor.USER,
            turn_type=turn_type,
            summary=f"Assumption {request.action}",
            payload={
                "assumption_id": resolution["assumption_id"],
                "action": resolution["action"],
                "original_text": resolution["original_text"],
                "final_text": resolution["final_text"],
                "category": resolution["category"],
                "feedback": resolution.get("feedback"),
            },
        )

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

        for result in results:
            turn_type = {
                "accept": TurnType.ASSUMPTION_CONFIRMED,
                "reject": TurnType.ASSUMPTION_REJECTED,
                "edit": TurnType.ASSUMPTION_MODIFIED,
            }.get(result["action"])
            if turn_type is None:
                continue
            log_turn_with_session_id_sync(
                db,
                session_id=session_id,
                actor=TurnActor.USER,
                turn_type=turn_type,
                summary=f"Assumption {result['action']}",
                payload={
                    "assumption_id": result["assumption_id"],
                    "action": result["action"],
                    "original_text": result["original_text"],
                    "final_text": result["final_text"],
                    "category": result["category"],
                    "feedback": result.get("feedback"),
                },
            )

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
        "clarifications": session.get("clarifications", []),
    }


@router.post("/api/context/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Mark a session as complete and save intent to index.

    This indicates the user has finished reviewing assumptions
    and the action can proceed with the resolved values.
    Also saves the approved intent to the Intent Index per PRD §15.2.

    Args:
        session_id: The session ID.

    Returns:
        Confirmation message.

    Raises:
        HTTPException: If session not found.
    """
    store = get_assumption_store()

    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    store.mark_complete(session_id)

    # Save approved intent to Intent Index (PRD §15.2)
    original_text = session.get("original_text")
    handler = session.get("handler")
    if original_text and handler:
        try:
            # Use async approach via asyncio.run
            async def save_intent() -> None:
                async with AsyncSessionLocal() as async_db:
                    repo = IntentRepository(async_db)
                    # Build resolution from approved assumptions
                    resolution = {
                        "action": handler,
                        "assumptions": [
                            {
                                "id": r["assumption_id"],
                                "action": r["action"],
                                "original_text": r["original_text"],
                                "final_text": r["final_text"],
                            }
                            for r in session.get("resolved_assumptions", [])
                        ],
                    }
                    # Insert intent with auto-generated embedding
                    await repo.insert_intent(
                        user_id="default",  # TODO: Get from auth context
                        intent_text=original_text,
                        intent_type=handler,
                        confidence=0.95,  # User approved assumptions = high confidence
                        resolution=resolution,
                        handler=handler,
                    )

            asyncio.run(save_intent())
            logger.info(f"Saved intent to index for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to save intent to index: {e}", exc_info=True)

    return {
        "status": "completed",
        "session_id": session_id,
    }
