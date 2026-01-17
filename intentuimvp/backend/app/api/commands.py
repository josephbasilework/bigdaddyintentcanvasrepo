"""Command submission endpoint for routing user commands."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.context.models import ContextPayload, SelectionScope
from app.context.router import get_context_router

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


class CommandSubmissionResponse(BaseModel):
    """Response payload for a submitted command."""

    correlation_id: str
    status: str


@dataclass(frozen=True)
class CommandSubmission:
    """Normalized command submission for routing."""

    correlation_id: str
    command: str
    attachments: list[str]
    selection: SelectionScope | None = None


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
    from app.handlers import get_handler_executor

    router = get_context_router()
    executor = get_handler_executor()
    payload = ContextPayload(
        text=submission.command,
        attachments=submission.attachments,
        selection=submission.selection,
    )

    try:
        decision = await asyncio.wait_for(
            router.route(payload),
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
        result = await executor.execute(decision, correlation_id=submission.correlation_id)
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
    )

    enqueue_command(submission)

    return CommandSubmissionResponse(correlation_id=correlation_id, status="queued")
