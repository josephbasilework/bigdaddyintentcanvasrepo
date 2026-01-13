"""Tests for dashboard state streaming service.

Tests for FR-015: Dashboards (Live State Visualization)
"""

from __future__ import annotations

from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest

from app.agui.schemas import (
    DashboardSubscribedMessage,
    DashboardSubscribedPayload,
    DashboardSubscribeMessage,
    DashboardSubscribePayload,
    DashboardUnsubscribeMessage,
    DashboardUnsubscribePayload,
    DashboardUpdateMessage,
    DashboardUpdatePayload,
)
from app.models.dashboard_subscription import DashboardSubscriptionTarget
from app.ws.dashboard_streaming import (
    DashboardStreamingService,
    get_dashboard_streaming_service,
)


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self, client_id: int | None = None) -> None:
        """Initialize mock WebSocket."""
        self._id = client_id or id(self)
        self.sent_messages: list[str] = []
        self.closed = False

    async def send_text(self, data: str) -> None:
        """Mock send_text method."""
        if self.closed:
            raise RuntimeError("WebSocket is closed")
        self.sent_messages.append(data)

    async def close(self) -> None:
        """Mock close method."""
        self.closed = True


@pytest.fixture
def streaming_service() -> DashboardStreamingService:
    """Create a fresh DashboardStreamingService for testing."""
    # Reset the singleton for testing
    DashboardStreamingService._instance = None
    service = DashboardStreamingService()
    return service


@pytest.fixture
def mock_websocket() -> Any:
    """Create a mock WebSocket for testing.

    Returns Any to bypass type checking - MockWebSocket implements
    the WebSocket interface for testing purposes.
    """
    return MockWebSocket()


class TestDashboardStreamingSchemas:
    """Tests for dashboard streaming AG-UI schemas."""

    def test_dashboard_subscribe_message_validates(self) -> None:
        """Test DashboardSubscribeMessage validation."""
        msg = DashboardSubscribeMessage(
            payload=DashboardSubscribePayload(
                dashboard_node_id=1,
                canvas_id=10,
            )
        )
        assert msg.type == "dashboard.subscribe"
        assert msg.payload.dashboard_node_id == 1
        assert msg.payload.canvas_id == 10
        assert msg.source == "ui"
        assert msg.target == "agent"

    def test_dashboard_unsubscribe_message_validates(self) -> None:
        """Test DashboardUnsubscribeMessage validation."""
        msg = DashboardUnsubscribeMessage(
            payload=DashboardUnsubscribePayload(dashboard_node_id=1)
        )
        assert msg.type == "dashboard.unsubscribe"
        assert msg.payload.dashboard_node_id == 1
        assert msg.source == "ui"
        assert msg.target == "agent"

    def test_dashboard_update_message_validates(self) -> None:
        """Test DashboardUpdateMessage validation."""
        msg = DashboardUpdateMessage(
            payload=DashboardUpdatePayload(
                dashboard_node_id=1,
                subscription_target="node",
                source_id="node-123",
                change_type="updated",
                data={"name": "Test Node"},
            )
        )
        assert msg.type == "dashboard.update"
        assert msg.payload.dashboard_node_id == 1
        assert msg.payload.subscription_target == "node"
        assert msg.payload.source_id == "node-123"
        assert msg.payload.change_type == "updated"
        assert msg.payload.data == {"name": "Test Node"}
        assert msg.source == "agent"
        assert msg.target == "ui"

    def test_dashboard_subscribed_message_validates(self) -> None:
        """Test DashboardSubscribedMessage validation."""
        msg = DashboardSubscribedMessage(
            payload=DashboardSubscribedPayload(
                dashboard_node_id=1,
                subscriptions=[
                    {"id": 1, "subscription_target": "node", "source_id": "123"}
                ],
            )
        )
        assert msg.type == "dashboard.subscribed"
        assert msg.payload.dashboard_node_id == 1
        assert len(msg.payload.subscriptions) == 1

    def test_dashboard_update_change_types(self) -> None:
        """Test DashboardUpdateMessage accepts all change types."""
        change_types: list[Literal["created", "updated", "deleted"]] = [
            "created",
            "updated",
            "deleted",
        ]
        for change_type in change_types:
            msg = DashboardUpdateMessage(
                payload=DashboardUpdatePayload(
                    dashboard_node_id=1,
                    subscription_target="node",
                    change_type=change_type,
                    data={},
                )
            )
            assert msg.payload.change_type == change_type


class TestDashboardStreamingService:
    """Tests for DashboardStreamingService."""

    @pytest.mark.asyncio
    async def test_subscribe_adds_connection(
        self,
        streaming_service: DashboardStreamingService,
        mock_websocket: Any,
    ) -> None:
        """Test that subscribe adds connection to tracking."""
        with patch.object(
            streaming_service,
            "_get_dashboard_subscriptions",
            return_value=[],
        ):
            await streaming_service.subscribe(mock_websocket, 1, 10)

        assert streaming_service.get_subscribed_dashboard_count(mock_websocket) == 1

    @pytest.mark.asyncio
    async def test_subscribe_multiple_dashboards(
        self,
        streaming_service: DashboardStreamingService,
        mock_websocket: Any,
    ) -> None:
        """Test subscribing to multiple dashboards."""
        with patch.object(
            streaming_service,
            "_get_dashboard_subscriptions",
            return_value=[],
        ):
            await streaming_service.subscribe(mock_websocket, 1, 10)
            await streaming_service.subscribe(mock_websocket, 2, 10)

        assert streaming_service.get_subscribed_dashboard_count(mock_websocket) == 2

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_connection(
        self,
        streaming_service: DashboardStreamingService,
        mock_websocket: Any,
    ) -> None:
        """Test that unsubscribe removes connection from tracking."""
        with patch.object(
            streaming_service,
            "_get_dashboard_subscriptions",
            return_value=[],
        ):
            await streaming_service.subscribe(mock_websocket, 1, 10)

        await streaming_service.unsubscribe(mock_websocket, 1)

        assert streaming_service.get_subscribed_dashboard_count(mock_websocket) == 0

    @pytest.mark.asyncio
    async def test_disconnect_clears_all_subscriptions(
        self,
        streaming_service: DashboardStreamingService,
        mock_websocket: Any,
    ) -> None:
        """Test that disconnect clears all subscriptions."""
        with patch.object(
            streaming_service,
            "_get_dashboard_subscriptions",
            return_value=[],
        ):
            await streaming_service.subscribe(mock_websocket, 1, 10)
            await streaming_service.subscribe(mock_websocket, 2, 10)

        await streaming_service.disconnect(mock_websocket)

        assert streaming_service.get_subscribed_dashboard_count(mock_websocket) == 0

    @pytest.mark.asyncio
    async def test_send_subscribed_confirmation(
        self,
        streaming_service: DashboardStreamingService,
        mock_websocket: Any,
    ) -> None:
        """Test sending subscription confirmation."""
        subscriptions = [
            {"id": 1, "subscription_target": "node", "source_id": "123"}
        ]
        await streaming_service.send_subscribed_confirmation(
            mock_websocket, 1, subscriptions
        )

        assert len(mock_websocket.sent_messages) == 1
        import json

        msg = json.loads(mock_websocket.sent_messages[0])
        assert msg["type"] == "dashboard.subscribed"
        assert msg["payload"]["dashboard_node_id"] == 1

    @pytest.mark.asyncio
    async def test_send_subscribed_confirmation_handles_closed_socket(
        self,
        streaming_service: DashboardStreamingService,
        mock_websocket: Any,
    ) -> None:
        """Test that confirmation handles closed WebSocket gracefully."""
        mock_websocket.closed = True

        # Should not raise
        await streaming_service.send_subscribed_confirmation(mock_websocket, 1, [])

    @pytest.mark.asyncio
    async def test_multiple_connections_same_dashboard(
        self,
        streaming_service: DashboardStreamingService,
    ) -> None:
        """Test multiple connections subscribing to the same dashboard."""
        ws1: Any = MockWebSocket(1)
        ws2: Any = MockWebSocket(2)

        with patch.object(
            streaming_service,
            "_get_dashboard_subscriptions",
            return_value=[],
        ):
            await streaming_service.subscribe(ws1, 1, 10)
            await streaming_service.subscribe(ws2, 1, 10)

        assert streaming_service.get_subscribed_dashboard_count(ws1) == 1
        assert streaming_service.get_subscribed_dashboard_count(ws2) == 1


class TestDashboardStreamingServicePublish:
    """Tests for DashboardStreamingService publish functionality."""

    @pytest.fixture
    def mock_subscription(self) -> MagicMock:
        """Create a mock DashboardSubscription."""
        sub = MagicMock()
        sub.dashboard_node_id = 1
        sub.subscription_target = DashboardSubscriptionTarget.NODE
        sub.source_id = "node-123"
        sub.is_active = True
        return sub

    @pytest.mark.asyncio
    async def test_publish_update_sends_to_subscribers(
        self,
        streaming_service: DashboardStreamingService,
        mock_subscription: MagicMock,
    ) -> None:
        """Test that publish_update sends to subscribed connections."""
        ws: Any = MockWebSocket()

        with patch.object(
            streaming_service,
            "_get_dashboard_subscriptions",
            return_value=[],
        ):
            await streaming_service.subscribe(ws, 1, 10)

        with patch.object(
            streaming_service,
            "_find_matching_subscriptions",
            return_value=[mock_subscription],
        ):
            count = await streaming_service.publish_update(
                canvas_id=10,
                target=DashboardSubscriptionTarget.NODE,
                source_id="node-123",
                change_type="updated",
                data={"name": "Test"},
            )

        assert count == 1
        assert len(ws.sent_messages) == 1
        import json

        msg = json.loads(ws.sent_messages[0])
        assert msg["type"] == "dashboard.update"
        assert msg["payload"]["change_type"] == "updated"

    @pytest.mark.asyncio
    async def test_publish_update_no_matching_subscriptions(
        self,
        streaming_service: DashboardStreamingService,
    ) -> None:
        """Test publish_update returns 0 when no matching subscriptions."""
        with patch.object(
            streaming_service,
            "_find_matching_subscriptions",
            return_value=[],
        ):
            count = await streaming_service.publish_update(
                canvas_id=10,
                target=DashboardSubscriptionTarget.NODE,
                source_id="node-999",
                change_type="created",
                data={},
            )

        assert count == 0

    @pytest.mark.asyncio
    async def test_publish_update_handles_disconnected_socket(
        self,
        streaming_service: DashboardStreamingService,
        mock_subscription: MagicMock,
    ) -> None:
        """Test publish_update handles disconnected sockets gracefully."""
        ws: Any = MockWebSocket()

        with patch.object(
            streaming_service,
            "_get_dashboard_subscriptions",
            return_value=[],
        ):
            await streaming_service.subscribe(ws, 1, 10)

        # Mark socket as closed
        ws.closed = True

        with patch.object(
            streaming_service,
            "_find_matching_subscriptions",
            return_value=[mock_subscription],
        ):
            count = await streaming_service.publish_update(
                canvas_id=10,
                target=DashboardSubscriptionTarget.NODE,
                source_id="node-123",
                change_type="updated",
                data={},
            )

        # Should handle error and disconnect the socket
        assert count == 0


class TestGetDashboardStreamingService:
    """Tests for the global singleton getter."""

    def test_returns_singleton_instance(self) -> None:
        """Test that get_dashboard_streaming_service returns singleton."""
        # Reset singleton
        import app.ws.dashboard_streaming as ds_module

        ds_module._dashboard_streaming_service = None

        service1 = get_dashboard_streaming_service()
        service2 = get_dashboard_streaming_service()

        assert service1 is service2

    def test_singleton_maintains_state(self) -> None:
        """Test that singleton maintains state across calls."""
        import app.ws.dashboard_streaming as ds_module

        ds_module._dashboard_streaming_service = None

        service1 = get_dashboard_streaming_service()
        # Modify internal state
        service1._connections[999] = MagicMock()

        service2 = get_dashboard_streaming_service()
        assert 999 in service2._connections
