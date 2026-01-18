"""Handler execution layer connecting context routing to agent tools.

This module provides:
- Handler implementations for routed commands
- Tool execution via ToolManager
- AG-UI event streaming for tool calls
- Integration with WebSocket manager for real-time updates
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.agents.tools import (
    CanvasNodePosition,
    get_tool_manager,
)
from app.agui import (
    AgentProgressMessage,
    ToolCallMessage,
    ToolCallPayload,
    ToolResultMessage,
    ToolResultPayload,
)
from app.agui.schemas import AgentProgressPayload as AgentProgressPayloadSchema
from app.context.assembly import get_context_assembler
from app.context.models import ContextPayload, RoutingDecision
from app.database import SessionLocal
from app.models.node import NodeType
from app.repositories.preferences import PreferencesRepository
from app.schemas.preferences import PreferencesData
from app.services.input_classifier import (
    extract_configuration_updates,
    strip_note_prefix,
)
from app.ws.websocket import manager as ws_manager

logger = logging.getLogger(__name__)

# Default user identifier for MVP flows
DEFAULT_USER_ID = "default_user"

# Default node position if not specified
DEFAULT_NODE_POSITION = CanvasNodePosition(x=100, y=100, z=0)


def _preview_text(text: str, limit: int = 120) -> str:
    """Create a short preview for user-facing acknowledgments."""
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: max(0, limit - 3)].rstrip()}..."


def _generate_call_id() -> str:
    """Generate a unique tool call identifier."""
    return f"call-{time.time()}-{uuid.uuid4().hex[:8]}"


class HandlerExecutionError(Exception):
    """Exception raised when handler execution fails."""

    def __init__(self, handler: str, reason: str, details: dict[str, Any] | None = None):
        self.handler = handler
        self.reason = reason
        self.details = details or {}
        super().__init__(f"Handler {handler} failed: {reason}")


@dataclass(frozen=True)
class HandlerContext:
    """Execution context for handlers (session, workspace, user)."""

    user_id: str | None = None
    session_id: str | None = None
    workspace_id: str | int | None = None


class HandlerExecutor:
    """Executes handlers based on routing decisions.

    Connects the context router to the tool layer, with AG-UI streaming.
    """

    def __init__(self) -> None:
        """Initialize the handler executor."""
        self._tool_manager = get_tool_manager()

    async def execute(
        self,
        decision: RoutingDecision,
        correlation_id: str | None = None,
        *,
        context: HandlerContext | None = None,
    ) -> dict[str, Any]:
        """Execute a handler based on routing decision.

        Args:
            decision: The routing decision from context router.
            correlation_id: Optional correlation ID for tracking.
            context: Optional execution context for session-aware handling.

        Returns:
            Handler execution result with tool outputs.

        Raises:
            HandlerExecutionError: If handler execution fails.
        """
        handler = decision.handler
        payload = decision.payload
        run_id = correlation_id or f"run-{time.time()}"

        logger.info(
            f"Executing handler: {handler}",
            extra={
                "handler": handler,
                "run_id": run_id,
                "confidence": decision.confidence,
                "assumptions_count": len(decision.assumptions),
            },
        )

        try:
            # Send initial progress
            await self._send_progress(
                run_id,
                handler,
                f"Executing {handler}",
                0.0,
            )

            # Route to appropriate handler
            match handler:
                case "create_handler":
                    result = await self._create_handler(payload, run_id)
                case "chat_handler":
                    result = await self._chat_handler(payload, run_id)
                case "note_handler":
                    result = await self._note_handler(payload, run_id)
                case "configuration_handler":
                    result = await self._configuration_handler(payload, run_id)
                case "clarification_handler":
                    result = await self._clarification_handler(payload, run_id)
                case "clarification_response_handler":
                    result = await self._clarification_response_handler(payload, run_id)
                case "research_handler":
                    result = await self._research_handler(payload, run_id)
                case "analyze_handler":
                    result = await self._analyze_handler(payload, run_id)
                case "plan_handler":
                    result = await self._plan_handler(payload, run_id, context)
                case "help_handler":
                    result = await self._help_handler(payload, run_id)
                case "clear_handler":
                    result = await self._clear_handler(payload, run_id)
                case "judge_handler":
                    result = await self._judge_handler(payload, run_id)
                case _:
                    # Default to chat handler for unknown handlers
                    logger.warning(f"Unknown handler {handler}, falling back to chat_handler")
                    result = await self._chat_handler(payload, run_id)

            # Send completion progress
            await self._send_progress(
                run_id,
                handler,
                "Complete",
                1.0,
            )

            return result

        except Exception as e:
            logger.error(
                f"Handler {handler} execution failed",
                exc_info=True,
                extra={"run_id": run_id, "handler": handler},
            )
            raise HandlerExecutionError(
                handler,
                str(e),
                {"run_id": run_id, "payload": payload.text},
            ) from e

    async def _execute_canvas_create_node(
        self,
        run_id: str,
        node_type: NodeType,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Helper to execute canvas_create_node tool with streaming.

        Args:
            run_id: Run identifier for tracking.
            node_type: Type of node to create.
            content: Node content.

        Returns:
            Result with node_id.

        Raises:
            HandlerExecutionError: If tool execution fails.
        """
        call_id = await self._send_tool_call(
            run_id,
            "canvas.create_node",
            {
                "type": node_type.value if isinstance(node_type, NodeType) else node_type,
                "content": content,
                "position": DEFAULT_NODE_POSITION.model_dump(),
                "metadata": metadata,
            },
        )

        result = await self._tool_manager.execute_tool(
            "canvas.create_node",
            {
                "type": node_type,
                "content": content,
                "position": DEFAULT_NODE_POSITION.model_dump(),
                "metadata": metadata,
            },
        )

        await self._send_tool_result(
            run_id,
            "canvas.create_node",
            call_id,
            result.output if result.success else None,
            result.error if not result.success else None,
        )

        if not result.success:
            raise HandlerExecutionError(
                "canvas_create_node",
                result.error or "Unknown tool execution error",
            )

        return {
            "handler": "canvas_create_node",
            "action": "node_created",
            "node_id": result.output.get("id") if result.output else None,
            "node_type": node_type.value if isinstance(node_type, NodeType) else node_type,
        }

    async def _create_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle create commands by creating a new node.

        Args:
            payload: The context payload with user input.
            run_id: Run identifier for tracking.

        Returns:
            Result with created node ID.
        """
        text = payload.text.strip()

        # Determine node type from command or default to text
        node_type = NodeType.TEXT
        if text.startswith("/plan"):
            node_type = NodeType.PLAN
        elif text.startswith("/research"):
            node_type = NodeType.DOCUMENT

        # Extract content (remove command prefix if present)
        content = text
        for prefix in ["/plan ", "/research ", "/create "]:
            if content.startswith(prefix):
                content = content[len(prefix) :].strip()
                break

        if not content:
            content = text

        # Execute canvas_create_node tool
        await self._send_progress(run_id, "create_handler", "Creating node...", 0.3)
        return await self._execute_canvas_create_node(run_id, node_type, content)

    async def _chat_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle general chat commands by creating a text node.

        Args:
            payload: The context payload with user input.
            run_id: Run identifier for tracking.

        Returns:
            Result with created node ID.
        """
        text = payload.text.strip()

        # Execute canvas_create_node tool
        await self._send_progress(run_id, "chat_handler", "Creating text node...", 0.3)
        return await self._execute_canvas_create_node(run_id, NodeType.TEXT, text)

    async def _note_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle note-style inputs by capturing a text node."""
        text = strip_note_prefix(payload.text)
        content = text if text else payload.text.strip()
        if not content:
            content = "Note"

        metadata = {"classification": "note"}
        await self._send_progress(run_id, "note_handler", "Capturing note...", 0.3)
        return await self._execute_canvas_create_node(
            run_id,
            NodeType.TEXT,
            content,
            metadata=metadata,
        )

    async def _configuration_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle configuration updates by applying preference changes."""
        text = payload.text.strip()
        updates, _signals = extract_configuration_updates(text)

        await self._send_progress(
            run_id,
            "configuration_handler",
            "Applying configuration...",
            0.3,
        )

        if not updates:
            message = (
                "No configuration updates recognized. Try 'set theme to dark' "
                "or 'zoom to 120%'."
            )
            return await self._execute_canvas_create_node(
                run_id,
                NodeType.TEXT,
                message,
                metadata={"classification": "configuration", "status": "no_updates"},
            )

        try:
            applied = self._apply_configuration_updates(updates)
            summary = ", ".join(f"{key}={value}" for key, value in applied.items())
            message = f"Updated preferences: {summary}"
            metadata = {"classification": "configuration", "updates": applied}
        except Exception as exc:
            logger.error("Configuration update failed", exc_info=True)
            message = f"Configuration update failed: {exc}"
            metadata = {"classification": "configuration", "status": "error"}

        return await self._execute_canvas_create_node(
            run_id,
            NodeType.TEXT,
            message,
            metadata=metadata,
        )

    async def _clarification_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle ambiguous inputs by asking for clarification."""
        preview = _preview_text(payload.text)
        message = "Can you clarify what you want to do?"
        if preview:
            message = f"Clarification needed for: {preview}. Can you clarify?"

        await self._send_progress(
            run_id,
            "clarification_handler",
            "Requesting clarification...",
            0.3,
        )

        return await self._execute_canvas_create_node(
            run_id,
            NodeType.TEXT,
            message,
            metadata={"classification": "ambiguous", "original_input": preview},
        )

    async def _clarification_response_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle clarification responses with acknowledgment."""
        preview = _preview_text(payload.text)
        message = "Clarification noted."
        if preview:
            message = f"Clarification noted: {preview}"

        await self._send_progress(
            run_id,
            "clarification_response_handler",
            "Recording clarification...",
            0.3,
        )

        return await self._execute_canvas_create_node(
            run_id,
            NodeType.TEXT,
            message,
            metadata={"classification": "clarification_response"},
        )

    async def _research_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle research commands by creating a document node.

        Args:
            payload: The context payload with user input.
            run_id: Run identifier for tracking.

        Returns:
            Result with created node ID.
        """
        text = payload.text.strip()
        # Remove /research prefix if present
        if text.startswith("/research"):
            text = text[9:].strip()

        if not text:
            text = "Research"

        await self._send_progress(run_id, "research_handler", "Creating research node...", 0.3)
        return await self._execute_canvas_create_node(
            run_id, NodeType.DOCUMENT, f"Research: {text}"
        )

    async def _analyze_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle analyze commands - for now creates a document node.

        Args:
            payload: The context payload with user input.
            run_id: Run identifier for tracking.

        Returns:
            Result with created node ID.
        """
        text = payload.text.strip()

        await self._send_progress(run_id, "analyze_handler", "Creating analysis node...", 0.3)
        return await self._execute_canvas_create_node(
            run_id, NodeType.DOCUMENT, f"Analysis: {text}"
        )

    async def _plan_handler(
        self,
        payload: ContextPayload,
        run_id: str,
        context: HandlerContext | None = None,
    ) -> dict[str, Any]:
        """Handle plan commands by creating a plan node.

        Args:
            payload: The context payload with user input.
            run_id: Run identifier for tracking.
            context: Execution context for assembling relevant nodes/turns.

        Returns:
            Result with created node ID.
        """
        text = payload.text.strip()
        # Remove /plan prefix if present
        if text.startswith("/plan"):
            text = text[5:].strip()

        if not text:
            text = "Plan"

        await self._send_progress(run_id, "plan_handler", "Generating structured plan...", 0.25)

        context_summary = ""
        job_user_id = DEFAULT_USER_ID
        if context is not None:
            try:
                if context.user_id:
                    job_user_id = context.user_id
                assembler = get_context_assembler()
                window = await assembler.assemble(
                    payload,
                    user_id=context.user_id,
                    session_id=context.session_id,
                    workspace_id=context.workspace_id,
                )
                context_summary = window.to_prompt()
            except Exception:
                logger.warning("Context assembly failed; continuing without it", exc_info=True)

        try:
            from app.jobs.worker import planner_job

            planner_result = await planner_job(
                {
                    "user_id": job_user_id,
                },
                goal=text,
                context=context_summary,
            )
        except Exception as exc:
            logger.error("Planner job failed; falling back to plan node only", exc_info=True)
            await self._send_progress(
                run_id,
                "plan_handler",
                "Planner failed; creating basic plan node.",
                0.4,
            )
            return await self._execute_canvas_create_node(
                run_id, NodeType.PLAN, f"Plan: {text}"
            )

        if not planner_result.success or not planner_result.data:
            await self._send_progress(
                run_id,
                "plan_handler",
                "Planner returned no data; creating basic plan node.",
                0.4,
            )
            return await self._execute_canvas_create_node(
                run_id, NodeType.PLAN, f"Plan: {text}"
            )

        result_data = planner_result.data
        plan_metadata = result_data.get("plan_metadata") or {}
        task_dag = result_data.get("task_dag") or {}
        execution_order = result_data.get("execution_order") or []
        source_references = result_data.get("source_references") or []
        reasoning = result_data.get("reasoning")
        job_id = result_data.get("job_id") or planner_result.metadata.get("job_id")

        plan_title = plan_metadata.get("goal") or text

        plan_metadata_payload = {
            "plan_metadata": plan_metadata,
            "execution_order": execution_order,
            "source_references": source_references,
            "reasoning": reasoning,
            "planner_job_id": job_id,
        }

        dag_metadata_payload = {
            "task_dag": task_dag,
            "execution_order": execution_order,
            "source_references": source_references,
            "planner_job_id": job_id,
        }

        await self._send_progress(
            run_id,
            "plan_handler",
            "Creating plan and task DAG nodes...",
            0.6,
        )
        plan_node = await self._execute_canvas_create_node(
            run_id, NodeType.PLAN, f"Plan: {plan_title}", metadata=plan_metadata_payload
        )
        dag_node = await self._execute_canvas_create_node(
            run_id, NodeType.DAG, f"Task DAG: {plan_title}", metadata=dag_metadata_payload
        )

        return {
            "handler": "plan_handler",
            "action": "plan_generated",
            "plan_node_id": plan_node.get("node_id"),
            "dag_node_id": dag_node.get("node_id"),
            "planner_job_id": job_id,
        }

    async def _help_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle help commands - returns help text.

        Args:
            payload: The context payload with user input.
            run_id: Run identifier for tracking.

        Returns:
            Help message.
        """
        await self._send_progress(run_id, "help_handler", "Generating help...", 0.5)

        help_text = """
Available commands:
- /research <topic> - Create a research document node
- /plan <description> - Create a plan node
- /analyze <topic> - Create an analysis document node
- /judge <topic> - Create a judgment document node
- /help - Show this help message
- /clear - Clear the canvas (not implemented yet)

You can also type natural language commands and I'll do my best to understand.
"""

        return {
            "handler": "help_handler",
            "action": "help_shown",
            "help_text": help_text.strip(),
        }

    async def _clear_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle clear commands - not yet implemented.

        Args:
            payload: The context payload with user input.
            run_id: Run identifier for tracking.

        Returns:
            Placeholder result.
        """
        await self._send_progress(run_id, "clear_handler", "Clear not implemented", 0.5)

        return {
            "handler": "clear_handler",
            "action": "not_implemented",
            "message": "Clear canvas is not yet implemented.",
        }

    async def _judge_handler(
        self,
        payload: ContextPayload,
        run_id: str,
    ) -> dict[str, Any]:
        """Handle judge commands by creating a document node.

        Args:
            payload: The context payload with user input.
            run_id: Run identifier for tracking.

        Returns:
            Result with created node ID.
        """
        text = payload.text.strip()
        # Remove /judge prefix if present
        if text.startswith("/judge"):
            text = text[6:].strip()

        if not text:
            text = "Judgment"

        await self._send_progress(run_id, "judge_handler", "Creating judgment node...", 0.3)
        return await self._execute_canvas_create_node(
            run_id, NodeType.DOCUMENT, f"Judgment: {text}"
        )

    def _apply_configuration_updates(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Apply preference updates and return the normalized values."""
        with SessionLocal() as db:
            repo = PreferencesRepository(db)
            prefs = repo.get_by_user(DEFAULT_USER_ID)
            base = prefs.preferences if prefs else PreferencesData().model_dump()
            merged = dict(base)
            merged.update(updates)
            validated = PreferencesData(**merged)
            repo.upsert_preferences(DEFAULT_USER_ID, validated.model_dump())
        normalized = validated.model_dump()
        return {key: normalized.get(key) for key in updates}

    async def _send_progress(
        self,
        run_id: str,
        agent_id: str,
        message: str,
        progress: float,
    ) -> None:
        """Send progress update via WebSocket.

        Args:
            run_id: Run identifier.
            agent_id: Agent/handler identifier.
            message: Progress message.
            progress: Progress value (0.0 to 1.0).
        """
        try:
            payload = AgentProgressPayloadSchema(
                agent_id=agent_id,
                operation="handler",
                progress=progress,
                message=message,
            )
            msg = AgentProgressMessage(payload=payload, correlation_id=run_id)
            await ws_manager.broadcast_agui(msg)
        except Exception:
            logger.warning("Failed to send progress update", exc_info=True)

    async def _send_tool_call(
        self,
        run_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """Send tool call event via WebSocket.

        Args:
            run_id: Run identifier.
            tool_name: Name of the tool being called.
            arguments: Tool arguments.

        Returns:
            The call_id for this tool call.
        """
        call_id = _generate_call_id()
        try:
            payload = ToolCallPayload(
                run_id=run_id,
                tool_name=tool_name,
                tool_args=arguments,
                call_id=call_id,
            )
            msg = ToolCallMessage(payload=payload, correlation_id=run_id)
            await ws_manager.broadcast_agui(msg)
        except Exception:
            logger.warning("Failed to send tool call event", exc_info=True)
        return call_id

    async def _send_tool_result(
        self,
        run_id: str,
        tool_name: str,
        call_id: str,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """Send tool result event via WebSocket.

        Args:
            run_id: Run identifier.
            tool_name: Name of the tool that was called.
            call_id: Tool call identifier.
            result: Tool result output.
            error: Tool error if any.
        """
        try:
            payload = ToolResultPayload(
                run_id=run_id,
                call_id=call_id,
                tool_name=tool_name,
                success=error is None,
                result=result,
                error=error,
            )
            msg = ToolResultMessage(payload=payload, correlation_id=run_id)
            await ws_manager.broadcast_agui(msg)
        except Exception:
            logger.warning("Failed to send tool result event", exc_info=True)


# Global executor instance
_executor: HandlerExecutor | None = None


def get_handler_executor() -> HandlerExecutor:
    """Get the global handler executor instance.

    Returns:
        HandlerExecutor instance.
    """
    global _executor
    if _executor is None:
        _executor = HandlerExecutor()
    return _executor
