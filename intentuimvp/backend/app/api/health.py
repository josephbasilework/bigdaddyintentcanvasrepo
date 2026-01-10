"""Health check endpoint for liveness/readiness probes."""

from fastapi import APIRouter

from app.config import get_settings
from app.redis import check_redis_health

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns the service status, version, and Redis connectivity for
    liveness/readiness probes.
    """
    redis_status = "connected" if await check_redis_health() else "disconnected"
    return {
        "status": "ok",
        "version": settings.app_version,
        "redis": redis_status,
    }
