"""WebSocket package for real-time communication."""

from app.ws.dashboard_streaming import (
    DashboardStreamingService,
    get_dashboard_streaming_service,
    publish_artifact_update,
    publish_edge_update,
    publish_job_update,
    publish_node_update,
    publish_workspace_state_update,
)
from app.ws.websocket import router

__all__ = [
    "router",
    "DashboardStreamingService",
    "get_dashboard_streaming_service",
    # Dashboard publishing helpers
    "publish_node_update",
    "publish_edge_update",
    "publish_job_update",
    "publish_artifact_update",
    "publish_workspace_state_update",
]
