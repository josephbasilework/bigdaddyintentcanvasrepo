"""Command submission endpoint for routing user commands."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.context.input_router import get_input_router
from app.context.models import ContextPayload, SelectionScope
from app.database import get_db
from app.models.intent import AttachmentDB
from app.models.turn import TurnActor, TurnType
from app.services.turns import log_turn_for_user_sync

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_COMMAND_LENGTH = 10000
ROUTING_HANDOFF_TIMEOUT_S = 30.0  # Increased for LLM-based routing


class CommandSubmissionRequest(BaseModel):
    """Request payload for submitting a command."""

    command: str | None = Field(default=None, description="Command text")
    attachments: list[str] | None = Field(default=None, description="Attachment IDs")
    selection: SelectionScope | None = Field(
        default=None, description="Selection scope for the command"
    )
    session_id: str | None = Field(
        default=None, description="Optional session ID for turn logging"
    )
    client_request_id: str | None = Field(
        default=None, description="Optional client request ID for idempotent replay"
    )
    skip_routing: bool = Field(
        default=False, description="Skip routing and only log the command"
    )
    command_key: str | None = Field(
        default=None, description="Optional canonical command key for UI commands"
    )


class CommandSubmissionResponse(BaseModel):
    """Response payload for a submitted command."""

    correlation_id: str
    status: str
    turnId: int | None = None
    sequenceNumber: int | None = None


@dataclass(frozen=True)
class CommandSubmission:
    """Normalized command submission for routing."""

    correlation_id: str
    command: str
    attachments: list[str]
    selection: SelectionScope | None = None
    session_id: str | None = None


def _validate_command(command: str) -> None:
    """Validate incoming command payloads."""
    if not command:
        raise HTTPException(status_code=400, detail="Command field cannot be empty")

    if len(command) > MAX_COMMAND_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Command exceeds maximum length of {MAX_COMMAND_LENGTH} characters",
        )


def enqueue_command(submission: CommandSubmission) -> None:
    """Enqueue command submission for routing in the background."""
    asyncio.create_task(_route_command_submission(submission))


async def _route_command_submission(submission: CommandSubmission) -> None:
    """Route a command submission through the context router and execute handler."""
    from app.handlers import HandlerContext, get_handler_executor

    router = get_input_router()
    executor = get_handler_executor()
    payload = ContextPayload(
        text=submission.command,
        attachments=submission.attachments,
        selection=submission.selection,
    )

    try:
        decision = await asyncio.wait_for(
            router.route(
                payload,
                user_id="default_user",
                session_id=submission.session_id,
            ),
            timeout=ROUTING_HANDOFF_TIMEOUT_S,
        )
        logger.info(
            "Command routed",
            extra={
                "correlation_id": submission.correlation_id,
                "handler": decision.handler,
                "confidence": decision.confidence,
                "assumptions_count": len(decision.assumptions),
            },
        )

        # Execute the handler
        context = HandlerContext(
            user_id="default_user",
            session_id=submission.session_id,
            workspace_id=None,
        )
        result = await executor.execute(
            decision,
            correlation_id=submission.correlation_id,
            context=context,
        )
        logger.info(
            "Handler executed",
            extra={
                "correlation_id": submission.correlation_id,
                "handler": decision.handler,
                "result": result,
            },
        )

    except TimeoutError:
        logger.warning(
            "Command routing timed out",
            extra={"correlation_id": submission.correlation_id},
        )
    except Exception:
        logger.error(
            "Command routing failed",
            extra={"correlation_id": submission.correlation_id},
            exc_info=True,
        )


@router.post(
    "/api/commands",
    response_model=CommandSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_command(
    payload: CommandSubmissionRequest,
    db: Session = Depends(get_db),
) -> CommandSubmissionResponse:
    """Submit a command for routing."""
    command = (payload.command or "").strip()
    _validate_command(command)

    correlation_id = str(uuid.uuid4())
    submission = CommandSubmission(
        correlation_id=correlation_id,
        command=command,
        attachments=payload.attachments or [],
        selection=payload.selection,
        session_id=payload.session_id,
    )

    if not payload.skip_routing:
        enqueue_command(submission)

    summary_preview = command[:120]
    summary_prefix = "UI command" if payload.skip_routing else "User input submitted"
    summary = (
        f"{summary_prefix}: {summary_preview}" if summary_preview else summary_prefix
    )
    log_payload: dict[str, Any] = {
        "command": command,
        "attachments": payload.attachments or [],
        "selection": payload.selection.model_dump() if payload.selection else None,
        "correlation_id": correlation_id,
    }
    if payload.command_key:
        log_payload["command_key"] = payload.command_key
    if payload.skip_routing:
        log_payload["routing_skipped"] = True
    turn = log_turn_for_user_sync(
        db,
        user_id="default_user",
        session_id=payload.session_id,
        actor=TurnActor.USER,
        turn_type=TurnType.USER_INPUT,
        summary=summary,
        payload=log_payload,
        client_request_id=payload.client_request_id,
    )
    if turn and payload.attachments:
        try:
            updates: dict[str, Any] = {
                "turn_id": turn.id,
                "session_id": turn.session_id,
                "context_id": turn.session_id,
            }
            primary_node_id = (
                payload.selection.primary_node_id
                if payload.selection is not None
                else None
            )
            if primary_node_id and str(primary_node_id).isdigit():
                updates["node_id"] = int(str(primary_node_id))

            (
                db.query(AttachmentDB)
                .filter(AttachmentDB.id.in_(payload.attachments))
                .update(updates, synchronize_session=False)
            )
            db.commit()
        except Exception:
            logger.warning(
                "Failed to link attachments to turn %s",
                turn.id,
                exc_info=True,
            )

    return CommandSubmissionResponse(
        correlation_id=correlation_id,
        status="logged" if payload.skip_routing else "queued",
        turnId=turn.id if turn else None,
        sequenceNumber=turn.sequence_number if turn else None,
    )
