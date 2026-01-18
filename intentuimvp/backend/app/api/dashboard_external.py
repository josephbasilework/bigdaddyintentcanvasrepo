"""Dashboard external state write-back endpoints."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_async_db
from app.mcp.client import MCPClient
from app.models.dashboard_subscription import DashboardSubscriptionTarget
from app.repositories.dashboard_subscription_repo import DashboardSubscriptionRepository
from app.schemas.dashboard_external import (
    DashboardExternalWriteRequest,
    DashboardExternalWriteResponse,
)
from app.services.dashboard_updates import publish_dashboard_update
from app.services.external_state import (
    build_external_source_id,
    coerce_external_source_config,
)

router = APIRouter()

MAX_PREVIEW_CHARS = 4000


def get_current_user() -> str:
    """Get current user from authentication."""
    return "default_user"


def _sanitize_preview(value: Any, depth: int = 0) -> Any:
    if depth >= 4:
        return "[truncated]"
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and len(value) > MAX_PREVIEW_CHARS:
            return f"{value[: MAX_PREVIEW_CHARS - 3]}..."
        return value
    if isinstance(value, list):
        return [_sanitize_preview(item, depth + 1) for item in value[:50]]
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in list(value.items())[:50]:
            sanitized[str(key)] = _sanitize_preview(item, depth + 1)
        return sanitized
    return str(value)


def _normalize_endpoint(endpoint: str | None, allowed_protocols: set[str]) -> str | None:
    if not endpoint:
        return None
    trimmed = endpoint.strip()
    if not trimmed:
        return None
    parsed = urlparse(trimmed)
    if parsed.scheme not in allowed_protocols:
        return None
    if not parsed.netloc:
        return None
    return trimmed


def _sanitize_endpoint_for_preview(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return endpoint


async def _parse_response_payload(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    text = response.text
    if len(text) > MAX_PREVIEW_CHARS:
        text = text[: MAX_PREVIEW_CHARS - 3] + "..."
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


@router.post(
    "/api/dashboard/external/write",
    response_model=DashboardExternalWriteResponse,
)
async def write_external_state(
    payload: DashboardExternalWriteRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Execute a write-back operation for an external dashboard source."""
    subscription_repo = DashboardSubscriptionRepository(db)
    subscriptions = await subscription_repo.get_by_dashboard_node(
        payload.dashboard_node_id, active_only=True
    )
    subscription = next(
        (
            sub
            for sub in subscriptions
            if sub.subscription_target == DashboardSubscriptionTarget.EXTERNAL_STATE
        ),
        None,
    )
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External subscription not found",
        )
    if subscription.canvas_id != payload.canvas_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dashboard node does not belong to canvas",
        )

    config = coerce_external_source_config(subscription.get_config())
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="External subscription configuration invalid",
        )
    if not config.allow_write:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Write-back is not enabled for this dashboard",
        )

    source_id = subscription.source_id or build_external_source_id(config)
    override_payload = payload.payload_override

    if config.type == "api":
        endpoint = _normalize_endpoint(config.endpoint, {"http", "https"})
        if not endpoint:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API endpoint must use http or https",
            )
        write_payload = override_payload or config.write_payload or {}
        if not payload.confirm:
            return {
                "success": False,
                "requires_confirmation": True,
                "preview": {
                    "method": config.write_method,
                    "endpoint": _sanitize_endpoint_for_preview(endpoint),
                    "payload": _sanitize_preview(write_payload),
                },
                "error": "Confirmation required before external write",
            }
        timeout = httpx.Timeout(10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.request(
                config.write_method,
                endpoint,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json=write_payload,
            )
        if response.status_code >= 400:
            return {
                "success": False,
                "error": f"Write-back failed ({response.status_code})",
            }
        result_payload = await _parse_response_payload(response)
        await publish_dashboard_update(
            canvas_id=subscription.canvas_id,
            target=DashboardSubscriptionTarget.EXTERNAL_STATE,
            source_id=source_id,
            change_type="updated",
            data={
                "status": "connected",
                "payload": result_payload,
            },
        )
        return {
            "success": True,
            "result": result_payload,
            "requires_confirmation": False,
        }

    if config.type == "mcp":
        if not config.mcp_tool_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MCP tool name is required",
            )
        args = override_payload or config.write_payload or config.mcp_args or {}
        async with AsyncSessionLocal() as session:
            client = MCPClient(session)
            await client.initialize()
            try:
                if payload.confirm:
                    result = await client.call_tool_with_confirmation(
                        tool_name=config.mcp_tool_name,
                        arguments=args,
                        initiated_by=user_id,
                        server_id=config.mcp_server_id,
                    )
                else:
                    result = await client.call_tool(
                        tool_name=config.mcp_tool_name,
                        arguments=args,
                        initiated_by=user_id,
                        server_id=config.mcp_server_id,
                    )
            finally:
                await client.shutdown()
        if result.required_confirmation and not payload.confirm:
            return {
                "success": False,
                "requires_confirmation": True,
                "preview": result.preview,
                "diff": result.diff,
                "error": "Confirmation required before MCP write",
            }
        if not result.success:
            return {
                "success": False,
                "error": result.error or "MCP write-back failed",
            }
        await publish_dashboard_update(
            canvas_id=subscription.canvas_id,
            target=DashboardSubscriptionTarget.EXTERNAL_STATE,
            source_id=source_id,
            change_type="updated",
            data={
                "status": "connected",
                "payload": result.result,
            },
        )
        return {
            "success": True,
            "result": result.result,
            "requires_confirmation": False,
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Write-back is not supported for this source type",
    )
