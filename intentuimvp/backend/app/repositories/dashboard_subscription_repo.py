"""Repository for dashboard subscription CRUD operations."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_subscription import (
    DashboardSubscription,
    DashboardSubscriptionTarget,
)
from app.repositories.base import BaseRepository


class DashboardSubscriptionRepository(BaseRepository[DashboardSubscription, Any, Any]):
    """Repository for dashboard subscription CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with database session."""
        super().__init__(db)

    @property
    def model(self) -> type[DashboardSubscription]:
        """Return the DashboardSubscription model."""
        return DashboardSubscription

    async def create_subscription(
        self,
        *,
        canvas_id: int,
        dashboard_node_id: int,
        subscription_target: DashboardSubscriptionTarget,
        source_id: str | None = None,
        config: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> DashboardSubscription:
        """Create a new dashboard subscription."""
        config_json = json.dumps(config) if config is not None else None
        return await self.create(
            canvas_id=canvas_id,
            dashboard_node_id=dashboard_node_id,
            subscription_target=subscription_target,
            source_id=source_id,
            subscription_config=config_json,
            is_active=is_active,
        )

    async def get_by_dashboard_node(
        self,
        dashboard_node_id: int,
        *,
        active_only: bool = False,
    ) -> list[DashboardSubscription]:
        """Get subscriptions for a dashboard node."""
        stmt = select(DashboardSubscription).where(
            DashboardSubscription.dashboard_node_id == dashboard_node_id
        )
        if active_only:
            stmt = stmt.where(DashboardSubscription.is_active.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_canvas(
        self,
        canvas_id: int,
        *,
        active_only: bool = False,
    ) -> list[DashboardSubscription]:
        """Get subscriptions for a canvas."""
        stmt = select(DashboardSubscription).where(
            DashboardSubscription.canvas_id == canvas_id
        )
        if active_only:
            stmt = stmt.where(DashboardSubscription.is_active.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_config(
        self,
        subscription_id: int,
        config: dict[str, Any],
    ) -> DashboardSubscription | None:
        """Update subscription config."""
        return await self.update(
            subscription_id,
            subscription_config=json.dumps(config),
        )

    async def set_active(
        self,
        subscription_id: int,
        is_active: bool,
    ) -> DashboardSubscription | None:
        """Activate or deactivate a subscription."""
        return await self.update(subscription_id, is_active=is_active)
