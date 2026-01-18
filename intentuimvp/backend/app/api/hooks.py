"""Hook API endpoints for deterministic triggers."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.repositories.hook_repo import AsyncHookRepository
from app.schemas.hook import (
    HookCreateRequest,
    HookListResponse,
    HookResponse,
    HookUpdateRequest,
)
from app.services.hooks import (
    HOOK_TYPE_EVENT,
    HOOK_TYPE_SCHEDULE,
    SUPPORTED_SCHEDULE_TYPES,
    ensure_next_run_at,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user() -> str:
    """Get current user from authentication (MVP default)."""
    return "default_user"


def _validate_hook_values(
    *,
    hook_type: str | None,
    event_type: str | None,
    schedule_type: str | None,
    trigger: dict | None,
) -> None:
    if hook_type == HOOK_TYPE_EVENT and not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="eventType is required for event hooks",
        )
    if hook_type == HOOK_TYPE_SCHEDULE:
        if not schedule_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="scheduleType is required for schedule hooks",
            )
        if schedule_type not in SUPPORTED_SCHEDULE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported scheduleType: {schedule_type}",
            )
        if trigger is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="trigger is required for schedule hooks",
            )


@router.get("/api/hooks", response_model=HookListResponse)
async def list_hooks(
    hook_type: str | None = Query(default=None, alias="hookType"),
    event_type: str | None = Query(default=None, alias="eventType"),
    schedule_type: str | None = Query(default=None, alias="scheduleType"),
    enabled: bool | None = Query(default=None),
    workspace_id: str | None = Query(default=None, alias="workspaceId"),
    session_id: str | None = Query(default=None, alias="sessionId"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> HookListResponse:
    repo = AsyncHookRepository(db)
    hooks = await repo.list_hooks(
        hook_type=hook_type,
        event_type=event_type,
        schedule_type=schedule_type,
        enabled=enabled,
        user_id=user_id,
        workspace_id=workspace_id,
        session_id=session_id,
    )
    return HookListResponse(
        hooks=[HookResponse(**hook.to_dict()) for hook in hooks],
        count=len(hooks),
    )


@router.post(
    "/api/hooks",
    response_model=HookResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_hook(
    payload: HookCreateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> HookResponse:
    _validate_hook_values(
        hook_type=payload.hook_type,
        event_type=payload.event_type,
        schedule_type=payload.schedule_type,
        trigger=payload.trigger,
    )
    repo = AsyncHookRepository(db)

    hook = await repo.create_hook(
        name=payload.name,
        description=payload.description,
        hook_type=payload.hook_type,
        event_type=payload.event_type,
        schedule_type=payload.schedule_type,
        trigger=payload.trigger,
        action=payload.action,
        enabled=payload.enabled,
        user_id=payload.user_id or user_id,
        workspace_id=payload.workspace_id,
        session_id=payload.session_id,
    )
    hook = ensure_next_run_at(hook)
    hook = await repo.update_hook(hook)
    logger.info("Created hook %s", hook.id)
    return HookResponse(**hook.to_dict())


@router.put("/api/hooks/{hook_id}", response_model=HookResponse)
async def update_hook(
    hook_id: int,
    payload: HookUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> HookResponse:
    repo = AsyncHookRepository(db)
    hook = await repo.get_hook(hook_id)
    if hook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hook not found")

    effective_hook_type = payload.hook_type or hook.hook_type
    effective_event_type = (
        payload.event_type if payload.event_type is not None else hook.event_type
    )
    effective_schedule_type = (
        payload.schedule_type
        if payload.schedule_type is not None
        else hook.schedule_type
    )
    effective_trigger = (
        payload.trigger if payload.trigger is not None else hook.trigger
    )

    _validate_hook_values(
        hook_type=effective_hook_type,
        event_type=effective_event_type,
        schedule_type=effective_schedule_type,
        trigger=effective_trigger,
    )

    for field in [
        "name",
        "description",
        "hook_type",
        "event_type",
        "schedule_type",
        "trigger",
        "action",
        "enabled",
        "user_id",
        "workspace_id",
        "session_id",
    ]:
        value = getattr(payload, field)
        if value is not None:
            setattr(hook, field, value)

    if hook.user_id is None:
        hook.user_id = user_id
    hook = ensure_next_run_at(hook)
    hook = await repo.update_hook(hook)
    logger.info("Updated hook %s", hook.id)
    return HookResponse(**hook.to_dict())


@router.delete("/api/hooks/{hook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hook(
    hook_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: str = Depends(get_current_user),
) -> None:
    repo = AsyncHookRepository(db)
    deleted = await repo.delete_hook(hook_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hook not found")
