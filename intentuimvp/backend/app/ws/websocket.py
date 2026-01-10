"""WebSocket endpoint for real-time updates using AG-UI protocol."""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.agui import (
    AgentNotificationMessage,
    AgentNotificationPayload,
    AgentToUIMessageType,
    AGUIEnvelope,
    StateSnapshotMessage,
    StateSnapshotPayload,
    StateSyncRequestMessage,
)
from app.config import get_settings
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
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self.active_connections: set[WebSocket] = set()
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(
            f"WebSocket connected. Total active connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from active connections.

        Args:
            websocket: The WebSocket connection to remove.
        """
        self.active_connections.discard(websocket)
        logger.info(
            f"WebSocket disconnected. Total active connections: {len(self.active_connections)}"
        )

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send a plain text message to a specific WebSocket connection.

        Args:
            message: The message to send.
            websocket: The WebSocket connection to send the message to.
        """
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def send_agui_message(
        self, message: AgentToUIMessageType, websocket: WebSocket
    ) -> None:
        """Send an AG-UI protocol message to a specific WebSocket connection.

        Args:
            message: The AG-UI message to send.
            websocket: The WebSocket connection to send the message to.
        """
        try:
            await websocket.send_text(message.model_dump_json())
        except Exception as e:
            logger.error(f"Error sending AG-UI message: {e}")
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
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                self.disconnect(connection)

    async def broadcast_agui(self, message: AgentToUIMessageType) -> None:
        """Broadcast an AG-UI protocol message to all active WebSocket connections.

        Args:
            message: The AG-UI message to broadcast.
        """
        if not self.active_connections:
            return

        message_json = message.model_dump_json()
        connections = list(self.active_connections)
        for connection in connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting AG-UI message: {e}")
                self.disconnect(connection)

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
                logger.debug("Heartbeat sent to all connections")

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

    Args:
        websocket: The WebSocket connection.
    """
    # Verify authentication before accepting
    if not await verify_websocket_auth(websocket):
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed"
        )
        logger.warning("WebSocket connection rejected: authentication failed")
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
        logger.info("WebSocket client disconnected")

        # Stop heartbeat if no more connections
        if not manager.active_connections:
            await manager.stop_heartbeat()

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

        # Stop heartbeat if no more connections
        if not manager.active_connections:
            await manager.stop_heartbeat()
