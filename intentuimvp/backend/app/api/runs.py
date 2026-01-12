"""RunAgentInput handler for AG-UI run lifecycle.

This endpoint accepts RunAgentInput requests and orchestrates agent execution
with real-time AG-UI event streaming via WebSocket.
"""

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.agents.intent_decipherer import IntentDeciphererAgent, get_intent_decipherer
from app.agui import (
    AgentProgressMessage,
    RunEndMessage,
    RunEndPayload,
    RunStartMessage,
    RunStartPayload,
)
from app.agui.schemas import AgentProgressPayload as AgentProgressPayloadSchema
from app.ws.websocket import manager

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Schemas
# ============================================================================


class RunAgentInput(BaseModel):
    """Input for an agent run following AG-UI protocol.

    Contains minimal messages, shared state snapshot, and available tools.
    """

    messages: list[dict[str, Any]] = Field(
        ..., description="Chat messages for the agent (OpenAI format)"
    )
    state: dict[str, Any] = Field(
        default_factory=dict,
        description="Shared state snapshot (canvas, selection, viewport, etc.)",
    )
    tools: list[str] = Field(
        default_factory=list,
        description="List of available tools for this run",
    )
    agent_id: str | None = Field(
        default="intent_decipherer",
        description="Target agent ID (defaults to intent_decipherer)",
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Additional UI context (user input, selection, etc.)",
    )


class RunAgentResponse(BaseModel):
    """Response for a RunAgentInput request.

    Returns immediately with run_id; actual results stream via WebSocket.
    """

    run_id: str = Field(..., description="Unique run identifier")
    status: str = Field(..., description="Run status: 'running', 'queued', etc.")
    message: str = Field(..., description="Status message")


# ============================================================================
# Run Orchestrator
# ============================================================================


class RunOrchestrator:
    """Orchestrates agent runs with AG-UI event streaming."""

    # Agent metadata for run lifecycle events
    AGENT_METADATA: dict[str, dict[str, str]] = {
        "intent_decipherer": {
            "agent_id": "intent_decipherer",
            "agent_name": "Intent Decipherer",
        }
    }

    def __init__(self, ws_manager: Any = manager) -> None:
        """Initialize the orchestrator.

        Args:
            ws_manager: WebSocket connection manager for broadcasting events.
        """
        self.ws_manager = ws_manager
        self._active_runs: dict[str, Any] = {}

    async def run_agent(
        self,
        input_data: RunAgentInput,
        agent: IntentDeciphererAgent,
    ) -> str:
        """Run an agent with AG-UI event streaming.

        Args:
            input_data: The RunAgentInput request.
            agent: The agent instance to run.

        Returns:
            The run_id for tracking.

        Raises:
            HTTPException: If the run fails.
        """
        run_id = f"run-{time.time()}-{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        agent_id = input_data.agent_id or "intent_decipherer"

        try:
            # Send run.start event
            await self._send_run_start(run_id, input_data, agent_id)

            # Execute the agent with progress streaming
            result = await self._execute_with_streaming(
                run_id, input_data, agent, start_time, agent_id
            )

            # Send run.end event on success
            await self._send_run_end(
                run_id,
                agent_id,
                "success",
                result=result,
                start_time=start_time,
            )

            return run_id

        except Exception as e:
            logger.error(f"Agent run {run_id} failed: {e}", exc_info=True)
            # Send run.end event on error
            await self._send_run_end(
                run_id,
                agent_id,
                "error",
                error=str(e),
                start_time=start_time,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent run failed: {e}",
            ) from e

    async def _send_run_start(
        self, run_id: str, input_data: RunAgentInput, agent_id: str
    ) -> None:
        """Send run.start event via WebSocket."""
        metadata = self.AGENT_METADATA.get(
            agent_id, {"agent_id": agent_id, "agent_name": agent_id}
        )
        payload = RunStartPayload(
            run_id=run_id,
            agent_id=metadata["agent_id"],
            agent_name=metadata["agent_name"],
            input_data={
                "messages": input_data.messages,
                "context": input_data.context,
            },
            tools=input_data.tools,
        )
        message = RunStartMessage(payload=payload)
        await self.ws_manager.broadcast_agui(message)
        logger.info(f"Sent run.start for {run_id}")

    async def _send_run_end(
        self,
        run_id: str,
        agent_id: str,
        run_status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        start_time: float | None = None,
    ) -> None:
        """Send run.end event via WebSocket."""
        duration_ms = None
        if start_time:
            duration_ms = (time.time() - start_time) * 1000

        payload = RunEndPayload(
            run_id=run_id,
            agent_id=agent_id,
            status=run_status,  # type: ignore
            result=result,
            error=error,
            duration_ms=duration_ms,
        )
        message = RunEndMessage(payload=payload)
        await self.ws_manager.broadcast_agui(message)
        logger.info(f"Sent run.end for {run_id}: status={run_status}")

    async def _execute_with_streaming(
        self,
        run_id: str,
        input_data: RunAgentInput,
        agent: IntentDeciphererAgent,
        start_time: float,
        agent_id: str,
    ) -> dict[str, Any]:
        """Execute the agent with progress streaming.

        Args:
            run_id: The run identifier.
            input_data: The RunAgentInput request.
            agent: The agent instance.
            start_time: Run start time for duration calculation.
            agent_id: The agent identifier.

        Returns:
            The agent result.
        """
        # Send initial progress
        await self._send_progress(
            run_id,
            agent_id,
            "Processing input",
            0.0,
        )

        # Extract user text from messages
        user_text = ""
        for msg in input_data.messages:
            if msg.get("role") == "user":
                user_text = msg.get("content", "")
                break

        if user_text:
            # Send progress update
            await self._send_progress(
                run_id,
                agent_id,
                "Deciphering intent",
                0.3,
            )

            # Run the agent via the run method
            result = await agent.run({"text": user_text})

            # Send final progress
            await self._send_progress(
                run_id,
                agent_id,
                "Complete",
                1.0,
            )

            return result

        # Fallback: return minimal result
        return {"status": "complete", "message": "No input provided"}

    async def _send_progress(
        self,
        run_id: str,
        agent_id: str,
        message: str,
        progress: float,
    ) -> None:
        """Send progress update via WebSocket."""
        payload = AgentProgressPayloadSchema(
            agent_id=agent_id,
            operation="run",
            progress=progress,
            message=message,
        )
        msg = AgentProgressMessage(payload=payload)
        await self.ws_manager.broadcast_agui(msg)


# Global orchestrator instance
_orchestrator: RunOrchestrator | None = None


def get_orchestrator() -> RunOrchestrator:
    """Get the global RunOrchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = RunOrchestrator()
    return _orchestrator


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/run", response_model=RunAgentResponse)
async def run_agent(
    input_data: RunAgentInput,
    agent: IntentDeciphererAgent = Depends(get_intent_decipherer),
    orchestrator: RunOrchestrator = Depends(get_orchestrator),
) -> RunAgentResponse:
    """Execute an agent run with AG-UI event streaming.

    This endpoint accepts RunAgentInput and orchestrates agent execution.
    Results are streamed in real-time via WebSocket using AG-UI protocol:
    - run.start: Signals run start
    - progress: Progress updates during execution
    - tool.call: When agent calls a tool
    - tool.result: When tool execution completes
    - run.end: Signals run completion

    The response returns immediately with run_id for tracking.

    Args:
        input_data: The RunAgentInput request.
        agent: The agent instance (dependency injected).
        orchestrator: The run orchestrator (dependency injected).

    Returns:
        RunAgentResponse with run_id and initial status.
    """
    try:
        # Start the run in the background
        run_id = await orchestrator.run_agent(input_data, agent)

        return RunAgentResponse(
            run_id=run_id,
            status="running",
            message="Agent run started, events streaming via WebSocket",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start agent run: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start agent run: {e}",
        ) from e


@router.get("/runs/{run_id}")
async def get_run_status(run_id: str) -> dict[str, Any]:
    """Get the status of an agent run.

    Args:
        run_id: The run identifier.

    Returns:
        Run status information.
    """
    # For now, return a simple status
    # In the future, this would query a run store/database
    return {
        "run_id": run_id,
        "status": "unknown",
        "message": "Run status tracking not yet implemented",
    }
