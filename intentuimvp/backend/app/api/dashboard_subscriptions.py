"""Dashboard subscription API endpoints."""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models.dashboard_subscription import DashboardSubscriptionTarget
from app.repositories.dashboard_subscription_repo import DashboardSubscriptionRepository
from app.repositories.node_repo import NodeRepository
from app.schemas.dashboard_subscription import (
    DashboardSubscriptionCreateRequest,
    DashboardSubscriptionListResponse,
    DashboardSubscriptionResponse,
    DashboardSubscriptionUpdateRequest,
)
from app.services.external_state import build_external_source_id, coerce_external_source_config

router = APIRouter()


def get_current_user() -> str:
    """Get current user from authentication."""
    return "default_user"


async def _resolve_external_source_id(
    config: dict[str, Any] | None,
    explicit_source_id: str | None,
) -> str | None:
    if explicit_source_id:
        return explicit_source_id
    if not config:
        return None
    parsed = coerce_external_source_config(config)
    if not parsed:
        return None
    return build_external_source_id(parsed)


@router.post(
    "/api/dashboard/subscriptions",
    response_model=DashboardSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dashboard_subscription(
    payload: DashboardSubscriptionCreateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Create or update a dashboard subscription."""
    node_repo = NodeRepository(db)
    node = await node_repo.get_by_id(payload.dashboard_node_id)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    if node.canvas_id != payload.canvas_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dashboard node does not belong to canvas",
        )

    subscription_repo = DashboardSubscriptionRepository(db)
    if payload.subscription_target == DashboardSubscriptionTarget.EXTERNAL_STATE:
        existing = await subscription_repo.get_by_dashboard_node(
            payload.dashboard_node_id, active_only=False
        )
        for sub in existing:
            if sub.subscription_target == DashboardSubscriptionTarget.EXTERNAL_STATE:
                source_id = await _resolve_external_source_id(
                    payload.config, payload.source_id
                )
                updates: dict[str, Any] = {
                    "subscription_target": payload.subscription_target,
                    "source_id": source_id,
                    "subscription_config": json.dumps(payload.config)
                    if payload.config is not None
                    else None,
                    "is_active": payload.is_active,
                }
                updated = await subscription_repo.update(sub.id, **updates)
                if not updated:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update subscription",
                    )
                return updated.to_dict()

    source_id = await _resolve_external_source_id(payload.config, payload.source_id)
    subscription = await subscription_repo.create_subscription(
        canvas_id=payload.canvas_id,
        dashboard_node_id=payload.dashboard_node_id,
        subscription_target=payload.subscription_target,
        source_id=source_id,
        config=payload.config,
        is_active=payload.is_active,
    )
    return subscription.to_dict()


@router.get(
    "/api/dashboard/subscriptions",
    response_model=DashboardSubscriptionListResponse,
)
async def list_dashboard_subscriptions(
    canvas_id: int | None = Query(default=None, description="Filter by canvas"),
    dashboard_node_id: int | None = Query(
        default=None, description="Filter by dashboard node"
    ),
    active_only: bool = Query(default=True, description="Return active subscriptions only"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """List dashboard subscriptions."""
    subscription_repo = DashboardSubscriptionRepository(db)
    if dashboard_node_id is not None:
        subscriptions = await subscription_repo.get_by_dashboard_node(
            dashboard_node_id, active_only=active_only
        )
    elif canvas_id is not None:
        subscriptions = await subscription_repo.get_by_canvas(
            canvas_id, active_only=active_only
        )
    else:
        subscriptions = await subscription_repo.list()

    return {
        "subscriptions": [sub.to_dict() for sub in subscriptions],
        "count": len(subscriptions),
    }


@router.put(
    "/api/dashboard/subscriptions/{subscription_id}",
    response_model=DashboardSubscriptionResponse,
)
async def update_dashboard_subscription(
    subscription_id: int,
    payload: DashboardSubscriptionUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Update a dashboard subscription."""
    subscription_repo = DashboardSubscriptionRepository(db)
    existing = await subscription_repo.get_by_id(subscription_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    updates: dict[str, Any] = {}
    if payload.subscription_target is not None:
        updates["subscription_target"] = payload.subscription_target
    if payload.source_id is not None:
        updates["source_id"] = payload.source_id
    if payload.config is not None:
        updates["subscription_config"] = json.dumps(payload.config)
    if payload.is_active is not None:
        updates["is_active"] = payload.is_active

    target = updates.get("subscription_target", existing.subscription_target)
    if target == DashboardSubscriptionTarget.EXTERNAL_STATE and payload.config is not None:
        computed_source_id = await _resolve_external_source_id(
            payload.config, payload.source_id
        )
        if computed_source_id:
            updates["source_id"] = computed_source_id

    updated = await subscription_repo.update(subscription_id, **updates)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update subscription",
        )
    return updated.to_dict()


@router.delete(
    "/api/dashboard/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_dashboard_subscription(
    subscription_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> None:
    """Delete a dashboard subscription."""
    subscription_repo = DashboardSubscriptionRepository(db)
    deleted = await subscription_repo.delete(subscription_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
