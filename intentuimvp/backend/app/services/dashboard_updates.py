"""Dashboard update publishing service.

This module provides a compatibility layer for publishing dashboard updates
when entities change. It wraps the DashboardStreamingService with a simpler
interface that can be called from API endpoints and repositories.

Implements FR-015: Dashboards (Live State Visualization)
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from app.database import AsyncSessionLocal
from app.models.dashboard_subscription import DashboardSubscriptionTarget
from app.models.turn import TurnActor, TurnType
from app.repositories.canvas_repo import CanvasRepository
from app.services.turns import log_turn_for_user_async
from app.ws.dashboard_streaming import get_dashboard_streaming_service

logger = logging.getLogger(__name__)


async def publish_dashboard_update(
    canvas_id: int,
    target: DashboardSubscriptionTarget,
    source_id: str,
    change_type: Literal["created", "updated", "deleted"],
    data: dict[str, Any],
) -> int:
    """Publish a dashboard update to subscribed clients.

    This is a convenience wrapper around DashboardStreamingService.publish_update
    that can be easily called from API endpoints and repositories.

    Args:
        canvas_id: The canvas where the change occurred.
        target: The type of entity that changed.
        source_id: The ID of the changed entity.
        change_type: The type of change (created, updated, deleted).
        data: The updated entity data.

    Returns:
        Number of dashboard connections that received the update.
    """
    service = get_dashboard_streaming_service()
    count = await service.publish_update(
        canvas_id=canvas_id,
        target=target,
        source_id=source_id,
        change_type=change_type,
        data=data,
    )

    if count > 0:
        logger.debug(
            f"Dashboard update published: {target.value}={source_id}, "
            f"change_type={change_type}, subscribers={count}"
        )

    if target in {
        DashboardSubscriptionTarget.WORKSPACE_STATE,
        DashboardSubscriptionTarget.TOOL_OUTPUT,
        DashboardSubscriptionTarget.ARTIFACT,
    }:
        try:
            async with AsyncSessionLocal() as session:
                canvas_repo = CanvasRepository(session)
                resolved_canvas = await canvas_repo.get_by_id(canvas_id)
                user_id = resolved_canvas.user_id if resolved_canvas else "default_user"
                await log_turn_for_user_async(
                    session,
                    user_id=user_id,
                    workspace_id=canvas_id,
                    actor=TurnActor.SYSTEM,
                    turn_type=TurnType.EXTERNAL_STATE_CHANGE,
                    summary=f"External state update: {target.value}",
                    payload={
                        "target": target.value,
                        "source_id": source_id,
                        "change_type": change_type,
                        "data": data,
                    },
                )
        except Exception:
            logger.warning("Failed to log external state update turn", exc_info=True)

    return count
