"""WebSocket endpoint for real-time updates."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.config import get_settings

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
        """Send a message to a specific WebSocket connection.

        Args:
            message: The message to send.
            websocket: The WebSocket connection to send the message to.
        """
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all active WebSocket connections.

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

    async def start_heartbeat(self) -> None:
        """Start the heartbeat task that sends ping messages every 30 seconds."""
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            return

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat messages to all connected clients."""
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if self.active_connections:
                await self.broadcast('{"type":"heartbeat"}')
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
    """WebSocket endpoint for real-time updates.

    Clients connect to this endpoint to receive real-time updates
    from the backend. The endpoint handles:
    - Connection acceptance with authentication
    - Message receiving from clients
    - Broadcasting updates to all connected clients
    - Heartbeat every 30 seconds

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

    # Start heartbeat if this is the first connection
    if len(manager.active_connections) == 1:
        await manager.start_heartbeat()

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            logger.debug(f"Received message: {data}")

            # Echo back for now (can be extended for bidirectional communication)
            await manager.send_personal_message(
                f'{{"type":"echo","message":"{data}"}}', websocket
            )

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
