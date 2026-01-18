"""WebSocket endpoint for real-time updates using AG-UI protocol.

Implements NFR-OBS-004: WebSocket connection events, message counts
Implements Global Session Identity for persistent session across reconnects
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agui import (
    AgentNotificationMessage,
    AgentNotificationPayload,
    AgentToUIMessageType,
    AGUIEnvelope,
    DashboardSubscribeMessage,
    DashboardUnsubscribeMessage,
    StateSnapshotMessage,
    StateSnapshotPayload,
    StateSyncRequestMessage,
    UIResponseMessage,
)
from app.config import get_settings
from app.database import AsyncSessionLocal, get_async_db
from app.logging_config import get_correlation_id
from app.repositories.session_repo import AsyncSessionRepository
from app.models.intent import AssumptionResolutionDB
from app.models.turn import ResponseType, TurnActor, TurnType, resolve_response_type
from app.services.turns import (
    log_turn_with_new_async_session,
    log_turn_with_session_id_async,
)
from app.ws.dashboard_streaming import get_dashboard_streaming_service
from app.ws.state_manager import get_state_manager

logger = logging.getLogger(__name__)
settings = get_settings()


def _truncate_summary(text: str, limit: int = 160) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _build_turn_from_agui_message(
    message: AgentToUIMessageType,
) -> tuple[TurnActor, TurnType, str, dict[str, object]] | None:
    message_type = getattr(message, "type", None)
    if message_type == "notification":
        payload = message.payload
        if getattr(payload, "title", "") == "Heartbeat":
            return None
        summary = _truncate_summary(f"{payload.title}: {payload.message}")
        payload_data = payload.model_dump()
        payload_data["response_type"] = ResponseType.ACKNOWLEDGMENT.value
        return (
            TurnActor.SYSTEM,
            TurnType.SYSTEM_MESSAGE,
            summary,
            payload_data,
        )
    if message_type == "status":
        payload = message.payload
        summary = _truncate_summary(f"{payload.agent_name}: {payload.status}")
        payload_data = payload.model_dump()
        payload_data["response_type"] = ResponseType.ACKNOWLEDGMENT.value
        return (
            TurnActor.SYSTEM,
            TurnType.SYSTEM_MESSAGE,
            summary,
            payload_data,
        )
    if message_type == "error":
        payload = message.payload
        summary = _truncate_summary(f"Agent error: {payload.error}")
        payload_data = payload.model_dump()
        payload_data["response_type"] = ResponseType.ACKNOWLEDGMENT.value
        return (
            TurnActor.SYSTEM,
            TurnType.SYSTEM_MESSAGE,
            summary,
            payload_data,
        )
    if message_type == "request":
        payload = message.payload
        prompt = getattr(payload, "prompt", "")
        summary = _truncate_summary(f"Agent request: {prompt}")
        payload_data = payload.model_dump()
        request_type = payload_data.get("request_type")
        response_type = (
            ResponseType.PROPOSAL
            if request_type == "confirmation"
            else ResponseType.CLARIFICATION
        )
        payload_data["response_type"] = response_type.value
        return (
            TurnActor.AGENT,
            TurnType.AGENT_RESPONSE,
            summary,
            payload_data,
        )
    if message_type == "tool.call":
        payload = message.payload
        summary = _truncate_summary(f"Tool call: {payload.tool_name}")
        payload_data = payload.model_dump()
        payload_data["response_type"] = ResponseType.TOOL_INVOCATION.value
        return (
            TurnActor.MCP,
            TurnType.MCP_TOOL_INVOKED,
            summary,
            payload_data,
        )
    if message_type == "tool.result":
        payload = message.payload
        summary = _truncate_summary(f"Tool result: {payload.tool_name}")
        payload_data = payload.model_dump()
        payload_data["response_type"] = ResponseType.TOOL_INVOCATION.value
        return (
            TurnActor.MCP,
            TurnType.MCP_TOOL_RESULT,
            summary,
            payload_data,
        )
    if message_type in {"result", "run.end"}:
        payload = message.payload
        summary = _truncate_summary(
            f"Agent response: {getattr(payload, 'agent_id', 'agent')}"
        )
        payload_data = payload.model_dump()
        response_type = resolve_response_type(
            TurnType.AGENT_RESPONSE,
            TurnActor.AGENT,
            payload_data,
        )
        if response_type:
            payload_data["response_type"] = response_type.value
        return (
            TurnActor.AGENT,
            TurnType.AGENT_RESPONSE,
            summary,
            payload_data,
        )
    return None


@dataclass
class SessionContext:
    """Context for an active WebSocket session."""

    session_id: str
    user_id: str
    workspace_id: int
    is_new_session: bool

router = APIRouter()

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 30


class ConnectionManager:
    """Manages active WebSocket connections.

    Tracks connected clients and provides broadcast functionality
    for sending messages to all connected clients.

    Implements NFR-OBS-004: Logs WebSocket connection events and message counts.
    Implements Global Session Identity: Maps connections to session contexts.
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self.active_connections: set[WebSocket] = set()
        self._heartbeat_task: asyncio.Task[None] | None = None
        # Track message counts per connection (NFR-OBS-004)
        self._message_counts: dict[int, dict[str, int]] = defaultdict(
            lambda: {"sent": 0, "received": 0}
        )
        # Track session context per connection (Global Session Identity)
        self._session_contexts: dict[int, SessionContext] = {}

    def _get_connection_id(self, websocket: WebSocket) -> int:
        """Get a unique ID for a WebSocket connection."""
        return id(websocket)

    def get_session_context(self, websocket: WebSocket) -> SessionContext | None:
        """Get the session context for a WebSocket connection."""
        conn_id = self._get_connection_id(websocket)
        return self._session_contexts.get(conn_id)

    def set_session_context(
        self, websocket: WebSocket, context: SessionContext
    ) -> None:
        """Set the session context for a WebSocket connection."""
        conn_id = self._get_connection_id(websocket)
        self._session_contexts[conn_id] = context

    def get_connections_by_session(self, session_id: str) -> list[WebSocket]:
        """Get all WebSocket connections for a given session ID."""
        connections = []
        for ws in self.active_connections:
            ctx = self.get_session_context(ws)
            if ctx and ctx.session_id == session_id:
                connections.append(ws)
        return connections

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection.

        Implements NFR-OBS-004: Logs WebSocket connection event.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        conn_id = self._get_connection_id(websocket)

        # Log connection event (NFR-OBS-004)
        logger.info(
            "WebSocket connected",
            extra={
                "event": "websocket_connection",
                "action": "connected",
                "connection_id": conn_id,
                "active_connections": len(self.active_connections),
                "client_host": websocket.client.host if websocket.client else None,
                "correlation_id": get_correlation_id(),
            },
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from active connections.

        Implements NFR-OBS-004: Logs WebSocket disconnection event with message counts.

        Args:
            websocket: The WebSocket connection to remove.
        """
        conn_id = self._get_connection_id(websocket)
        message_counts = self._message_counts.get(conn_id, {})
        session_context = self._session_contexts.get(conn_id)

        self.active_connections.discard(websocket)

        # Log disconnection event with message counts (NFR-OBS-004)
        logger.info(
            "WebSocket disconnected",
            extra={
                "event": "websocket_connection",
                "action": "disconnected",
                "connection_id": conn_id,
                "session_id": session_context.session_id if session_context else None,
                "active_connections": len(self.active_connections),
                "messages_sent": message_counts.get("sent", 0),
                "messages_received": message_counts.get("received", 0),
                "correlation_id": get_correlation_id(),
            },
        )

        # Clean up message counts and session context
        self._message_counts.pop(conn_id, None)
        self._session_contexts.pop(conn_id, None)

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send a plain text message to a specific WebSocket connection.

        Args:
            message: The message to send.
            websocket: The WebSocket connection to send the message to.
        """
        conn_id = self._get_connection_id(websocket)
        try:
            await websocket.send_text(message)
            self._message_counts[conn_id]["sent"] += 1
        except Exception as e:
            logger.error(
                "Error sending personal message",
                extra={
                    "event": "websocket_error",
                    "connection_id": conn_id,
                    "error_type": type(e).__name__,
                    "correlation_id": get_correlation_id(),
                },
            )
            self.disconnect(websocket)

    async def send_agui_message(
        self, message: AgentToUIMessageType, websocket: WebSocket
    ) -> None:
        """Send an AG-UI protocol message to a specific WebSocket connection.

        Args:
            message: The AG-UI message to send.
            websocket: The WebSocket connection to send the message to.
        """
        conn_id = self._get_connection_id(websocket)
        try:
            await websocket.send_text(message.model_dump_json())
            self._message_counts[conn_id]["sent"] += 1
            ctx = self.get_session_context(websocket)
            if ctx:
                turn = _build_turn_from_agui_message(message)
                if turn:
                    actor, turn_type, summary, payload = turn
                    await log_turn_with_new_async_session(
                        session_id=ctx.session_id,
                        actor=actor,
                        turn_type=turn_type,
                        summary=summary,
                        payload=payload,
                    )
        except Exception as e:
            logger.error(
                "Error sending AG-UI message",
                extra={
                    "event": "websocket_error",
                    "connection_id": conn_id,
                    "error_type": type(e).__name__,
                    "correlation_id": get_correlation_id(),
                },
            )
            self.disconnect(websocket)

    async def broadcast(self, message: str) -> None:
        """Broadcast a plain text message to all active WebSocket connections.

        Args:
            message: The message to broadcast.
        """
        if not self.active_connections:
            return

        # Create a list of connected websockets to avoid modification during iteration
        connections = list(self.active_connections)
        sent_count = 0
        for connection in connections:
            conn_id = self._get_connection_id(connection)
            try:
                await connection.send_text(message)
                self._message_counts[conn_id]["sent"] += 1
                sent_count += 1
            except Exception as e:
                logger.error(
                    "Error broadcasting to connection",
                    extra={
                        "event": "websocket_error",
                        "connection_id": conn_id,
                        "error_type": type(e).__name__,
                        "correlation_id": get_correlation_id(),
                    },
                )
                self.disconnect(connection)

        # Log broadcast metrics (NFR-OBS-004)
        logger.debug(
            "Broadcast completed",
            extra={
                "event": "websocket_broadcast",
                "recipients": sent_count,
                "active_connections": len(self.active_connections),
                "correlation_id": get_correlation_id(),
            },
        )

    async def broadcast_agui(self, message: AgentToUIMessageType) -> None:
        """Broadcast an AG-UI protocol message to all active WebSocket connections.

        Args:
            message: The AG-UI message to broadcast.
        """
        if not self.active_connections:
            return

        message_json = message.model_dump_json()
        connections = list(self.active_connections)
        turn = _build_turn_from_agui_message(message)
        session_ids: set[str] = set()
        if turn:
            for connection in connections:
                ctx = self.get_session_context(connection)
                if ctx:
                    session_ids.add(ctx.session_id)
        sent_count = 0
        for connection in connections:
            conn_id = self._get_connection_id(connection)
            try:
                await connection.send_text(message_json)
                self._message_counts[conn_id]["sent"] += 1
                sent_count += 1
            except Exception as e:
                logger.error(
                    "Error broadcasting AG-UI message",
                    extra={
                        "event": "websocket_error",
                        "connection_id": conn_id,
                        "error_type": type(e).__name__,
                        "correlation_id": get_correlation_id(),
                    },
                )
                self.disconnect(connection)
        if turn and session_ids:
            actor, turn_type, summary, payload = turn
            for session_id in session_ids:
                await log_turn_with_new_async_session(
                    session_id=session_id,
                    actor=actor,
                    turn_type=turn_type,
                    summary=summary,
                    payload=payload,
                )

        # Log broadcast metrics (NFR-OBS-004)
        logger.debug(
            "Broadcast AG-UI completed",
            extra={
                "event": "websocket_broadcast",
                "message_type": type(message).__name__,
                "recipients": sent_count,
                "active_connections": len(self.active_connections),
                "correlation_id": get_correlation_id(),
            },
        )

    async def start_heartbeat(self) -> None:
        """Start the heartbeat task that sends ping messages every 30 seconds."""
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            return

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat AG-UI messages to all connected clients."""
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if self.active_connections:
                # Send heartbeat as AG-UI notification message
                payload = AgentNotificationPayload(
                    level="info",
                    title="Heartbeat",
                    message="Connection alive",
                )
                heartbeat_msg = AgentNotificationMessage(payload=payload)
                await self.broadcast_agui(heartbeat_msg)

                # Log heartbeat metrics (NFR-OBS-004)
                logger.debug(
                    "Heartbeat sent",
                    extra={
                        "event": "websocket_heartbeat",
                        "active_connections": len(self.active_connections),
                        "correlation_id": get_correlation_id(),
                    },
                )

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat task."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None


# Global connection manager instance
manager = ConnectionManager()


async def verify_websocket_auth(websocket: WebSocket) -> bool:
    """Verify WebSocket connection authentication.

    For now, this is a basic implementation that checks for a simple
    token in the query parameters. In production, this should use
    proper JWT validation.

    Args:
        websocket: The WebSocket connection to verify.

    Returns:
        True if authenticated, False otherwise.
    """
    # Basic authentication: check for a token in query params
    # For now, we accept all connections in dev mode
    if settings.debug:
        return True

    token = websocket.query_params.get("token")
    if not token:
        return False

    # TODO: Implement proper JWT validation
    # For now, accept any non-empty token
    return bool(token)


def get_websocket_user(websocket: WebSocket) -> str:
    """Extract user ID from WebSocket connection.

    For MVP, returns default_user. In production, extract from JWT token.

    Args:
        websocket: The WebSocket connection

    Returns:
        User ID string
    """
    # TODO: Extract user from JWT in query params or headers
    # For now, use default user like the REST API
    return "default_user"


async def establish_session(
    websocket: WebSocket, db: AsyncSession
) -> SessionContext | None:
    """Establish or resume a workspace session for the WebSocket connection.

    Extracts session_id from query params. If provided, attempts to resume
    the existing session. If not provided or invalid, creates a new session.

    Args:
        websocket: The WebSocket connection
        db: Async database session

    Returns:
        SessionContext with session details, or None if session could not be established
    """
    from sqlalchemy import select

    from app.models.canvas import Canvas

    user_id = get_websocket_user(websocket)
    session_id = websocket.query_params.get("session_id")

    # Get or create canvas for user (matches workspace API behavior)
    result = await db.execute(
        select(Canvas)
        .filter(Canvas.user_id == user_id)
        .order_by(Canvas.updated_at.desc())
        .limit(1)
    )
    canvas = result.scalar_one_or_none()

    if canvas is None:
        # Create a default canvas for the user
        canvas = Canvas(user_id=user_id, name="default")
        db.add(canvas)
        await db.commit()
        await db.refresh(canvas)
        logger.info(f"Created default canvas {canvas.id} for user {user_id}")

    # Get or create session
    session_repo = AsyncSessionRepository(db)
    session, is_new = await session_repo.get_or_create_session(
        user_id=user_id,
        workspace_id=canvas.id,
        session_id=session_id,
    )

    return SessionContext(
        session_id=session.session_id,
        user_id=user_id,
        workspace_id=canvas.id,
        is_new_session=is_new,
    )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for AG-UI protocol real-time communication.

    Clients connect to this endpoint to exchange AG-UI protocol messages
    with the backend. The endpoint handles:
    - Connection acceptance with authentication
    - Session establishment/resumption (Global Session Identity)
    - AG-UI message validation and routing
    - Broadcasting agent messages to connected clients
    - Heartbeat every 30 seconds using AG-UI notification messages

    Query Parameters:
        session_id (optional): Session ID to resume an existing session

    Implements NFR-OBS-004: Logs WebSocket message receives.
    Implements Global Session Identity for persistent sessions across reconnects.

    Args:
        websocket: The WebSocket connection.
    """
    conn_id = id(websocket)

    # Verify authentication before accepting
    if not await verify_websocket_auth(websocket):
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed"
        )
        # Log authentication failure (NFR-OBS-004, NFR-OBS-005)
        logger.warning(
            "WebSocket authentication failed",
            extra={
                "event": "websocket_connection",
                "action": "auth_failed",
                "connection_id": conn_id,
                "client_host": websocket.client.host if websocket.client else None,
                "correlation_id": get_correlation_id(),
            },
        )
        return

    await manager.connect(websocket)

    # Establish or resume session (Global Session Identity)
    session_context: SessionContext | None = None
    async for db in get_async_db():
        try:
            session_context = await establish_session(websocket, db)
            if session_context:
                manager.set_session_context(websocket, session_context)
                logger.info(
                    "Session established",
                    extra={
                        "event": "session_established",
                        "session_id": session_context.session_id,
                        "workspace_id": session_context.workspace_id,
                        "is_new_session": session_context.is_new_session,
                        "connection_id": conn_id,
                        "correlation_id": get_correlation_id(),
                    },
                )
        except Exception as e:
            logger.error(f"Failed to establish session: {e}", exc_info=True)
        break

    # Send welcome notification with session info
    if session_context:
        welcome_payload = AgentNotificationPayload(
            level="info",
            title="Connected",
            message=f"Session {'resumed' if not session_context.is_new_session else 'created'}: {session_context.session_id[:8]}...",
        )
    else:
        welcome_payload = AgentNotificationPayload(
            level="info",
            title="Connected",
            message="WebSocket connection established (no session)",
        )
    welcome_msg = AgentNotificationMessage(payload=welcome_payload)
    await manager.send_agui_message(welcome_msg, websocket)

    # Start heartbeat if this is the first connection
    if len(manager.active_connections) == 1:
        await manager.start_heartbeat()

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()

            # Track received message count (NFR-OBS-004)
            manager._message_counts[conn_id]["received"] += 1

            logger.debug(f"Received raw message: {data}")

            # Parse and validate as AG-UI message
            try:
                message_data = json.loads(data)

                # Validate envelope structure
                envelope = AGUIEnvelope(**message_data)

                # For UI -> Agent messages, validate the specific message type
                if envelope.source == "ui" and envelope.target == "agent":
                    message_type = message_data.get('type')

                    # Handle state sync requests
                    if message_type == "state.sync_request":
                        try:
                            # Validate the state sync request message
                            StateSyncRequestMessage(**message_data)
                            state_manager = get_state_manager()

                            # Get full state snapshot
                            seq, state, checksum = await state_manager.create_snapshot()

                            # Send state snapshot
                            snapshot_payload = StateSnapshotPayload(
                                sequence=seq,
                                state=state,
                                checksum=checksum,
                            )
                            snapshot_msg = StateSnapshotMessage(
                                payload=snapshot_payload,
                                correlation_id=envelope.message_id,
                            )
                            await manager.send_agui_message(snapshot_msg, websocket)

                            logger.info(
                                f"Sent state snapshot: sequence={seq}, "
                                f"state_keys={list(state.keys())}"
                            )
                        except ValidationError as e:
                            logger.error(f"State sync request validation failed: {e}")
                            error_payload = AgentNotificationPayload(
                                level="warning",
                                title="Invalid Sync Request",
                                message=str(e),
                            )
                            error_msg = AgentNotificationMessage(payload=error_payload)
                            await manager.send_agui_message(error_msg, websocket)
                        except Exception as e:
                            logger.error(f"Error handling state sync request: {e}")
                            error_payload = AgentNotificationPayload(
                                level="warning",
                                title="Sync Error",
                                message="Failed to generate state snapshot",
                            )
                            error_msg = AgentNotificationMessage(payload=error_payload)
                            await manager.send_agui_message(error_msg, websocket)

                    # Handle dashboard subscribe requests
                    elif message_type == "dashboard.subscribe":
                        try:
                            subscribe_msg = DashboardSubscribeMessage(**message_data)
                            dashboard_service = get_dashboard_streaming_service()
                            subscriptions = await dashboard_service.subscribe(
                                websocket,
                                subscribe_msg.payload.dashboard_node_id,
                                subscribe_msg.payload.canvas_id,
                            )
                            # Send confirmation with active subscriptions
                            await dashboard_service.send_subscribed_confirmation(
                                websocket,
                                subscribe_msg.payload.dashboard_node_id,
                                subscriptions,
                            )
                            logger.info(
                                f"Dashboard subscribed: node_id="
                                f"{subscribe_msg.payload.dashboard_node_id}"
                            )
                        except ValidationError as e:
                            logger.error(f"Dashboard subscribe validation failed: {e}")
                            error_payload = AgentNotificationPayload(
                                level="warning",
                                title="Invalid Subscribe Request",
                                message=str(e),
                            )
                            error_msg = AgentNotificationMessage(payload=error_payload)
                            await manager.send_agui_message(error_msg, websocket)
                        except Exception as e:
                            logger.error(f"Error handling dashboard subscribe: {e}")
                            error_payload = AgentNotificationPayload(
                                level="warning",
                                title="Subscribe Error",
                                message="Failed to subscribe to dashboard",
                            )
                            error_msg = AgentNotificationMessage(payload=error_payload)
                            await manager.send_agui_message(error_msg, websocket)

                    # Handle dashboard unsubscribe requests
                    elif message_type == "dashboard.unsubscribe":
                        try:
                            unsubscribe_msg = DashboardUnsubscribeMessage(**message_data)
                            dashboard_service = get_dashboard_streaming_service()
                            await dashboard_service.unsubscribe(
                                websocket,
                                unsubscribe_msg.payload.dashboard_node_id,
                            )
                            # Send acknowledgment
                            ack_payload = AgentNotificationPayload(
                                level="info",
                                title="Unsubscribed",
                                message=f"Unsubscribed from dashboard "
                                f"{unsubscribe_msg.payload.dashboard_node_id}",
                            )
                            ack_msg = AgentNotificationMessage(
                                payload=ack_payload,
                                correlation_id=envelope.message_id,
                            )
                            await manager.send_agui_message(ack_msg, websocket)
                            logger.info(
                                f"Dashboard unsubscribed: node_id="
                                f"{unsubscribe_msg.payload.dashboard_node_id}"
                            )
                        except ValidationError as e:
                            logger.error(
                                f"Dashboard unsubscribe validation failed: {e}"
                            )
                            error_payload = AgentNotificationPayload(
                                level="warning",
                                title="Invalid Unsubscribe Request",
                                message=str(e),
                            )
                            error_msg = AgentNotificationMessage(payload=error_payload)
                            await manager.send_agui_message(error_msg, websocket)
                        except Exception as e:
                            logger.error(f"Error handling dashboard unsubscribe: {e}")
                            error_payload = AgentNotificationPayload(
                                level="warning",
                                title="Unsubscribe Error",
                                message="Failed to unsubscribe from dashboard",
                            )
                            error_msg = AgentNotificationMessage(payload=error_payload)
                            await manager.send_agui_message(error_msg, websocket)

                    # Handle UI response messages (assumption reconciliation)
                    elif message_type == "response":
                        try:
                            response_msg = UIResponseMessage(**message_data)
                            session_id = response_msg.payload.request_id
                            response_payload = response_msg.payload.response

                            from app.api.assumption_store import get_assumption_store

                            store = get_assumption_store()
                            resolutions: list[dict[str, object]] = []
                            if isinstance(response_payload, list):
                                resolutions = [
                                    item for item in response_payload if isinstance(item, dict)
                                ]
                            elif isinstance(response_payload, dict):
                                if isinstance(response_payload.get("resolutions"), list):
                                    resolutions = [
                                        item
                                        for item in response_payload.get("resolutions", [])
                                        if isinstance(item, dict)
                                    ]

                            if session_id and resolutions:
                                resolved_results = []
                                for resolution in resolutions:
                                    action = resolution.get("action")
                                    assumption_id = resolution.get("assumption_id")
                                    if not action or not assumption_id:
                                        continue
                                    original_text = resolution.get("original_text")
                                    if not isinstance(original_text, str):
                                        original_text = "[original text not available]"
                                    category = resolution.get("category")
                                    if not isinstance(category, str):
                                        category = "unknown"
                                    edited_text = resolution.get("edited_text")
                                    feedback = resolution.get("feedback")
                                    resolved = store.resolve_assumption(
                                        session_id=session_id,
                                        assumption_id=str(assumption_id),
                                        action=str(action),
                                        original_text=original_text,
                                        category=category,
                                        edited_text=edited_text
                                        if isinstance(edited_text, str)
                                        else None,
                                        feedback=feedback if isinstance(feedback, str) else None,
                                    )
                                    resolved_results.append(resolved)

                                async with AsyncSessionLocal() as session:
                                    db_records = [
                                        AssumptionResolutionDB(
                                            session_id=session_id,
                                            assumption_id=result["assumption_id"],
                                            action=result["action"],
                                            original_text=result["original_text"],
                                            final_text=result["final_text"],
                                            category=result["category"],
                                        )
                                        for result in resolved_results
                                    ]
                                    if db_records:
                                        session.add_all(db_records)
                                        await session.commit()

                                    for result in resolved_results:
                                        action = result["action"]
                                        turn_type = {
                                            "accept": TurnType.ASSUMPTION_CONFIRMED,
                                            "reject": TurnType.ASSUMPTION_REJECTED,
                                            "edit": TurnType.ASSUMPTION_MODIFIED,
                                        }.get(action)
                                        if turn_type is None:
                                            continue
                                        await log_turn_with_session_id_async(
                                            session,
                                            session_id=session_id,
                                            actor=TurnActor.USER,
                                            turn_type=turn_type,
                                            summary=f"Assumption {action}",
                                            payload={
                                                "assumption_id": result["assumption_id"],
                                                "action": result["action"],
                                                "original_text": result["original_text"],
                                                "final_text": result["final_text"],
                                                "category": result["category"],
                                                "feedback": result.get("feedback"),
                                            },
                                        )

                            if (
                                isinstance(response_payload, dict)
                                and response_payload.get("complete")
                                and session_id
                            ):
                                store.mark_complete(session_id)

                            ack_payload = AgentNotificationPayload(
                                level="info",
                                title="Response Received",
                                message="Processed response message",
                            )
                            ack_msg = AgentNotificationMessage(
                                payload=ack_payload,
                                correlation_id=envelope.message_id,
                            )
                            await manager.send_agui_message(ack_msg, websocket)
                        except ValidationError as e:
                            logger.error(f"Response message validation failed: {e}")
                            error_payload = AgentNotificationPayload(
                                level="warning",
                                title="Invalid Response",
                                message=str(e),
                            )
                            error_msg = AgentNotificationMessage(payload=error_payload)
                            await manager.send_agui_message(error_msg, websocket)
                        except Exception as e:
                            logger.error(f"Error handling response message: {e}")
                            error_payload = AgentNotificationPayload(
                                level="warning",
                                title="Response Error",
                                message="Failed to process response message",
                            )
                            error_msg = AgentNotificationMessage(payload=error_payload)
                            await manager.send_agui_message(error_msg, websocket)

                    else:
                        # Try to validate as UIToAgentMessageType
                        # This is a placeholder - actual routing would be handled here
                        logger.info(
                            f"Received UI->Agent message: type={message_type}"
                        )

                        # For now, send acknowledgment
                        ack_payload = AgentNotificationPayload(
                            level="info",
                            title="Message Received",
                            message=f"Processed {message_type or 'unknown'} message",
                        )
                        ack_msg = AgentNotificationMessage(
                            payload=ack_payload,
                            correlation_id=envelope.message_id,
                        )
                        await manager.send_agui_message(ack_msg, websocket)

                else:
                    logger.warning(
                        f"Invalid message direction: source={envelope.source}, target={envelope.target}"
                    )

            except ValidationError as e:
                logger.error(f"AG-UI message validation failed: {e}")
                # Send error notification
                error_payload = AgentNotificationPayload(
                    level="warning",
                    title="Invalid Message",
                    message="Message does not conform to AG-UI protocol",
                )
                error_msg = AgentNotificationMessage(payload=error_payload)
                await manager.send_agui_message(error_msg, websocket)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message as JSON: {e}")
                error_payload = AgentNotificationPayload(
                    level="warning",
                    title="Invalid JSON",
                    message="Message must be valid JSON",
                )
                error_msg = AgentNotificationMessage(payload=error_payload)
                await manager.send_agui_message(error_msg, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # Clean up dashboard subscriptions
        dashboard_service = get_dashboard_streaming_service()
        await dashboard_service.disconnect(websocket)
        logger.info("WebSocket client disconnected")

        # Stop heartbeat if no more connections
        if not manager.active_connections:
            await manager.stop_heartbeat()

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        # Clean up dashboard subscriptions
        dashboard_service = get_dashboard_streaming_service()
        await dashboard_service.disconnect(websocket)

        # Stop heartbeat if no more connections
        if not manager.active_connections:
            await manager.stop_heartbeat()
