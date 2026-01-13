"""WebSocket endpoint for real-time updates using AG-UI protocol.

Implements NFR-OBS-004: WebSocket connection events, message counts
"""

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

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
)
from app.config import get_settings
from app.logging_config import get_correlation_id
from app.ws.dashboard_streaming import get_dashboard_streaming_service
from app.ws.state_manager import get_state_manager

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 30


class ConnectionManager:
    """Manages active WebSocket connections.

    Tracks connected clients and provides broadcast functionality
    for sending messages to all connected clients.

    Implements NFR-OBS-004: Logs WebSocket connection events and message counts.
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self.active_connections: set[WebSocket] = set()
        self._heartbeat_task: asyncio.Task[None] | None = None
        # Track message counts per connection (NFR-OBS-004)
        self._message_counts: dict[int, dict[str, int]] = defaultdict(
            lambda: {"sent": 0, "received": 0}
        )

    def _get_connection_id(self, websocket: WebSocket) -> int:
        """Get a unique ID for a WebSocket connection."""
        return id(websocket)

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

        self.active_connections.discard(websocket)

        # Log disconnection event with message counts (NFR-OBS-004)
        logger.info(
            "WebSocket disconnected",
            extra={
                "event": "websocket_connection",
                "action": "disconnected",
                "connection_id": conn_id,
                "active_connections": len(self.active_connections),
                "messages_sent": message_counts.get("sent", 0),
                "messages_received": message_counts.get("received", 0),
                "correlation_id": get_correlation_id(),
            },
        )

        # Clean up message counts
        self._message_counts.pop(conn_id, None)

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


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for AG-UI protocol real-time communication.

    Clients connect to this endpoint to exchange AG-UI protocol messages
    with the backend. The endpoint handles:
    - Connection acceptance with authentication
    - AG-UI message validation and routing
    - Broadcasting agent messages to connected clients
    - Heartbeat every 30 seconds using AG-UI notification messages

    Implements NFR-OBS-004: Logs WebSocket message receives.

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

    # Send welcome notification
    welcome_payload = AgentNotificationPayload(
        level="info",
        title="Connected",
        message="WebSocket connection established",
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
