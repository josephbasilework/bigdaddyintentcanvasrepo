"""Dashboard state streaming service for real-time updates.

This module provides:
- WebSocket connection tracking for dashboard subscriptions
- Publishing updates when dashboard-subscribed entities change
- Integration with the DashboardSubscription model

Implements FR-015: Dashboards (Live State Visualization)
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import select

from app.agui import (
    DashboardSubscribedMessage,
    DashboardSubscribedPayload,
    DashboardUpdateMessage,
    DashboardUpdatePayload,
)
from app.database import AsyncSessionLocal
from app.logging_config import get_correlation_id
from app.models.dashboard_subscription import (
    DashboardSubscription,
    DashboardSubscriptionTarget,
)

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = logging.getLogger(__name__)


class DashboardStreamingService:
    """Service for streaming dashboard state updates to WebSocket clients.

    This service manages:
    - Mapping of WebSocket connections to dashboard node subscriptions
    - Publishing updates when entities matching subscriptions change
    - Sending targeted updates to subscribed clients

    Thread Safety:
        All public methods are async and use locks for thread-safe access
        to internal state.
    """

    _instance: DashboardStreamingService | None = None
    _lock: asyncio.Lock

    def __new__(cls) -> DashboardStreamingService:
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the streaming service (only once)."""
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._lock = asyncio.Lock()

        # Maps dashboard_node_id to set of subscribed WebSocket connections
        self._subscriptions: dict[int, set[WebSocket]] = defaultdict(set)

        # Maps WebSocket connection to set of subscribed dashboard_node_ids
        self._connection_dashboards: dict[int, set[int]] = defaultdict(set)

        # Maps WebSocket connection id to WebSocket instance
        self._connections: dict[int, WebSocket] = {}
        self._dashboard_canvas_ids: dict[int, int] = {}

    def _get_connection_id(self, websocket: WebSocket) -> int:
        """Get a unique ID for a WebSocket connection."""
        return id(websocket)

    async def subscribe(
        self,
        websocket: WebSocket,
        dashboard_node_id: int,
        canvas_id: int,
        targets: list[DashboardSubscriptionTarget] | None = None,
    ) -> list[dict[str, Any]]:
        """Subscribe a WebSocket connection to a dashboard node's updates.

        Args:
            websocket: The WebSocket connection to subscribe.
            dashboard_node_id: The dashboard node to subscribe to.
            canvas_id: The canvas containing the dashboard node.

        Returns:
            List of active subscriptions for the dashboard node.
        """
        conn_id = self._get_connection_id(websocket)

        async with self._lock:
            self._subscriptions[dashboard_node_id].add(websocket)
            self._connection_dashboards[conn_id].add(dashboard_node_id)
            self._connections[conn_id] = websocket
            self._dashboard_canvas_ids[dashboard_node_id] = canvas_id

        # Fetch active subscriptions from database
        subscriptions = await self._get_dashboard_subscriptions(
            dashboard_node_id, canvas_id, targets
        )
        if subscriptions:
            from app.services.external_state import get_external_state_manager

            external_manager = get_external_state_manager()
            await external_manager.attach_dashboard(
                dashboard_node_id, canvas_id, subscriptions
            )

        logger.info(
            "Dashboard subscription added",
            extra={
                "event": "dashboard_streaming",
                "action": "subscribe",
                "dashboard_node_id": dashboard_node_id,
                "canvas_id": canvas_id,
                "connection_id": conn_id,
                "subscription_count": len(subscriptions),
                "correlation_id": get_correlation_id(),
            },
        )

        return subscriptions

    async def unsubscribe(
        self,
        websocket: WebSocket,
        dashboard_node_id: int,
    ) -> None:
        """Unsubscribe a WebSocket connection from a dashboard node.

        Args:
            websocket: The WebSocket connection to unsubscribe.
            dashboard_node_id: The dashboard node to unsubscribe from.
        """
        conn_id = self._get_connection_id(websocket)

        canvas_id: int | None = None
        async with self._lock:
            self._subscriptions[dashboard_node_id].discard(websocket)
            if not self._subscriptions[dashboard_node_id]:
                del self._subscriptions[dashboard_node_id]
                canvas_id = self._dashboard_canvas_ids.pop(dashboard_node_id, None)

            self._connection_dashboards[conn_id].discard(dashboard_node_id)
            if not self._connection_dashboards[conn_id]:
                del self._connection_dashboards[conn_id]
                self._connections.pop(conn_id, None)

        if canvas_id is not None:
            from app.services.external_state import get_external_state_manager

            external_manager = get_external_state_manager()
            await external_manager.detach_dashboard(dashboard_node_id, canvas_id)

        logger.info(
            "Dashboard subscription removed",
            extra={
                "event": "dashboard_streaming",
                "action": "unsubscribe",
                "dashboard_node_id": dashboard_node_id,
                "connection_id": conn_id,
                "correlation_id": get_correlation_id(),
            },
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove all subscriptions for a disconnected WebSocket.

        Args:
            websocket: The disconnected WebSocket connection.
        """
        conn_id = self._get_connection_id(websocket)

        dashboards_to_detach: list[tuple[int, int]] = []
        async with self._lock:
            dashboard_ids = list(self._connection_dashboards.get(conn_id, set()))
            for dashboard_id in dashboard_ids:
                self._subscriptions[dashboard_id].discard(websocket)
                if not self._subscriptions[dashboard_id]:
                    del self._subscriptions[dashboard_id]
                    canvas_id = self._dashboard_canvas_ids.pop(dashboard_id, None)
                    if canvas_id is not None:
                        dashboards_to_detach.append((dashboard_id, canvas_id))

            self._connection_dashboards.pop(conn_id, None)
            self._connections.pop(conn_id, None)

        if dashboard_ids:
            logger.info(
                "Dashboard subscriptions cleared on disconnect",
                extra={
                    "event": "dashboard_streaming",
                    "action": "disconnect",
                    "connection_id": conn_id,
                    "cleared_dashboards": len(dashboard_ids),
                    "correlation_id": get_correlation_id(),
                },
            )

        if dashboards_to_detach:
            from app.services.external_state import get_external_state_manager

            external_manager = get_external_state_manager()
            for dashboard_id, canvas_id in dashboards_to_detach:
                await external_manager.detach_dashboard(dashboard_id, canvas_id)

    async def publish_update(
        self,
        canvas_id: int,
        target: DashboardSubscriptionTarget,
        source_id: str | None,
        change_type: Literal["created", "updated", "deleted"],
        data: dict[str, Any],
    ) -> int:
        """Publish an update to all dashboards subscribed to the changed entity.

        Args:
            canvas_id: The canvas where the change occurred.
            target: The type of entity that changed.
            source_id: The ID of the changed entity (optional for workspace-wide).
            change_type: The type of change (created, updated, deleted).
            data: The updated entity data.

        Returns:
            Number of dashboard nodes that received the update.
        """
        # Find matching subscriptions in the database
        matching_subscriptions = await self._find_matching_subscriptions(
            canvas_id, target, source_id
        )

        if not matching_subscriptions:
            return 0

        # Group by dashboard_node_id
        dashboard_node_ids = {sub.dashboard_node_id for sub in matching_subscriptions}

        update_count = 0
        all_disconnected: list[WebSocket] = []

        async with self._lock:
            for dashboard_node_id in dashboard_node_ids:
                websockets = self._subscriptions.get(dashboard_node_id, set())
                if not websockets:
                    continue

                # Create update message
                payload = DashboardUpdatePayload(
                    dashboard_node_id=dashboard_node_id,
                    subscription_target=target.value,
                    source_id=source_id,
                    change_type=change_type,
                    data=data,
                    timestamp=datetime.now(UTC),
                )
                message = DashboardUpdateMessage(payload=payload)

                # Send to all subscribed connections
                for ws in websockets:
                    try:
                        from app.ws.websocket import manager

                        await manager.send_agui_message(message, ws)
                        update_count += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to send dashboard update: {e}",
                            extra={
                                "event": "dashboard_streaming",
                                "action": "send_failed",
                                "dashboard_node_id": dashboard_node_id,
                                "error": str(e),
                                "correlation_id": get_correlation_id(),
                            },
                        )
                        all_disconnected.append(ws)

        # Clean up disconnected connections (outside the lock to avoid deadlock)
        for ws in all_disconnected:
            await self.disconnect(ws)

        if update_count > 0:
            logger.debug(
                "Dashboard updates sent",
                extra={
                    "event": "dashboard_streaming",
                    "action": "publish",
                    "target": target.value,
                    "source_id": source_id,
                    "change_type": change_type,
                    "dashboards_notified": len(dashboard_node_ids),
                    "connections_notified": update_count,
                    "correlation_id": get_correlation_id(),
                },
            )

        return update_count

    async def send_subscribed_confirmation(
        self,
        websocket: WebSocket,
        dashboard_node_id: int,
        subscriptions: list[dict[str, Any]],
    ) -> None:
        """Send a confirmation message when a client subscribes to a dashboard.

        Args:
            websocket: The WebSocket connection.
            dashboard_node_id: The dashboard node ID.
            subscriptions: The active subscriptions for the dashboard.
        """
        payload = DashboardSubscribedPayload(
            dashboard_node_id=dashboard_node_id,
            subscriptions=subscriptions,
        )
        message = DashboardSubscribedMessage(payload=payload)
        try:
            from app.ws.websocket import manager

            await manager.send_agui_message(message, websocket)
        except Exception as e:
            logger.warning(
                f"Failed to send subscription confirmation: {e}",
                extra={
                    "event": "dashboard_streaming",
                    "action": "confirmation_failed",
                    "dashboard_node_id": dashboard_node_id,
                    "error": str(e),
                    "correlation_id": get_correlation_id(),
                },
            )

    async def _get_dashboard_subscriptions(
        self,
        dashboard_node_id: int,
        canvas_id: int,
        targets: list[DashboardSubscriptionTarget] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch active subscriptions for a dashboard node from the database.

        Args:
            dashboard_node_id: The dashboard node ID.
            canvas_id: The canvas ID.

        Returns:
            List of subscription dictionaries.
        """
        async with AsyncSessionLocal() as db:
            stmt = select(DashboardSubscription).where(
                DashboardSubscription.dashboard_node_id == dashboard_node_id,
                DashboardSubscription.canvas_id == canvas_id,
                DashboardSubscription.is_active.is_(True),
            )
            if targets:
                normalized_targets = [
                    target.value if isinstance(target, DashboardSubscriptionTarget) else str(target)
                    for target in targets
                ]
                stmt = stmt.where(
                    DashboardSubscription.subscription_target.in_(normalized_targets)
                )
            result = await db.execute(stmt)
            subscriptions = result.scalars().all()
            return [sub.to_dict() for sub in subscriptions]

    async def _find_matching_subscriptions(
        self,
        canvas_id: int,
        target: DashboardSubscriptionTarget,
        source_id: str | None,
    ) -> list[DashboardSubscription]:
        """Find dashboard subscriptions matching the changed entity.

        Args:
            canvas_id: The canvas where the change occurred.
            target: The type of entity that changed.
            source_id: The ID of the changed entity.

        Returns:
            List of matching DashboardSubscription objects.
        """
        async with AsyncSessionLocal() as db:
            # Build query for matching subscriptions
            stmt = select(DashboardSubscription).where(
                DashboardSubscription.canvas_id == canvas_id,
                DashboardSubscription.subscription_target == target,
                DashboardSubscription.is_active.is_(True),
            )

            # If source_id is provided, match either:
            # 1. Subscriptions with no source_id (subscribe to all of this type)
            # 2. Subscriptions with matching source_id
            if source_id is not None:
                from sqlalchemy import or_

                stmt = stmt.where(
                    or_(
                        DashboardSubscription.source_id.is_(None),
                        DashboardSubscription.source_id == source_id,
                    )
                )

            result = await db.execute(stmt)
            return list(result.scalars().all())

    def get_subscribed_dashboard_count(self, websocket: WebSocket) -> int:
        """Get the number of dashboards a connection is subscribed to.

        Args:
            websocket: The WebSocket connection.

        Returns:
            Number of subscribed dashboards.
        """
        conn_id = self._get_connection_id(websocket)
        return len(self._connection_dashboards.get(conn_id, set()))


# Global singleton instance
_dashboard_streaming_service: DashboardStreamingService | None = None


def get_dashboard_streaming_service() -> DashboardStreamingService:
    """Get the global dashboard streaming service instance.

    Returns:
        The global DashboardStreamingService instance.
    """
    global _dashboard_streaming_service
    if _dashboard_streaming_service is None:
        _dashboard_streaming_service = DashboardStreamingService()
    return _dashboard_streaming_service


# ============================================================================
# Helper Functions for Publishing Updates
# ============================================================================

# These convenience functions are called by other parts of the codebase
# (API endpoints, repositories, jobs) to notify subscribed dashboards
# when entities change.


async def publish_node_update(
    canvas_id: int,
    node_id: int,
    change_type: Literal["created", "updated", "deleted"],
    node_data: dict[str, Any],
) -> int:
    """Publish a node change to subscribed dashboards.

    Args:
        canvas_id: The canvas where the node change occurred.
        node_id: The ID of the node that changed.
        change_type: The type of change (created, updated, deleted).
        node_data: The node data to include in the update.

    Returns:
        Number of dashboard connections that received the update.
    """
    service = get_dashboard_streaming_service()
    return await service.publish_update(
        canvas_id=canvas_id,
        target=DashboardSubscriptionTarget.NODE,
        source_id=str(node_id),
        change_type=change_type,
        data=node_data,
    )


async def publish_edge_update(
    canvas_id: int,
    edge_id: int,
    change_type: Literal["created", "updated", "deleted"],
    edge_data: dict[str, Any],
) -> int:
    """Publish an edge change to subscribed dashboards.

    Args:
        canvas_id: The canvas where the edge change occurred.
        edge_id: The ID of the edge that changed.
        change_type: The type of change (created, updated, deleted).
        edge_data: The edge data to include in the update.

    Returns:
        Number of dashboard connections that received the update.
    """
    service = get_dashboard_streaming_service()
    return await service.publish_update(
        canvas_id=canvas_id,
        target=DashboardSubscriptionTarget.EDGE,
        source_id=str(edge_id),
        change_type=change_type,
        data=edge_data,
    )


async def publish_job_update(
    canvas_id: int,
    job_id: str,
    change_type: Literal["created", "updated", "deleted"],
    job_data: dict[str, Any],
) -> int:
    """Publish a job change to subscribed dashboards.

    Args:
        canvas_id: The canvas where the job change occurred.
        job_id: The ID of the job that changed.
        change_type: The type of change (created, updated, deleted).
        job_data: The job data to include in the update.

    Returns:
        Number of dashboard connections that received the update.
    """
    service = get_dashboard_streaming_service()
    return await service.publish_update(
        canvas_id=canvas_id,
        target=DashboardSubscriptionTarget.JOB,
        source_id=job_id,
        change_type=change_type,
        data=job_data,
    )


async def publish_artifact_update(
    canvas_id: int,
    artifact_id: str,
    change_type: Literal["created", "updated", "deleted"],
    artifact_data: dict[str, Any],
) -> int:
    """Publish an artifact change to subscribed dashboards.

    Args:
        canvas_id: The canvas where the artifact change occurred.
        artifact_id: The ID of the artifact that changed.
        change_type: The type of change (created, updated, deleted).
        artifact_data: The artifact data to include in the update.

    Returns:
        Number of dashboard connections that received the update.
    """
    service = get_dashboard_streaming_service()
    return await service.publish_update(
        canvas_id=canvas_id,
        target=DashboardSubscriptionTarget.ARTIFACT,
        source_id=artifact_id,
        change_type=change_type,
        data=artifact_data,
    )


async def publish_workspace_state_update(
    canvas_id: int,
    change_type: Literal["created", "updated", "deleted"],
    state_data: dict[str, Any],
) -> int:
    """Publish a workspace state change to subscribed dashboards.

    Args:
        canvas_id: The canvas where the state change occurred.
        change_type: The type of change (created, updated, deleted).
        state_data: The state data to include in the update.

    Returns:
        Number of dashboard connections that received the update.
    """
    service = get_dashboard_streaming_service()
    return await service.publish_update(
        canvas_id=canvas_id,
        target=DashboardSubscriptionTarget.WORKSPACE_STATE,
        source_id=None,
        change_type=change_type,
        data=state_data,
    )
