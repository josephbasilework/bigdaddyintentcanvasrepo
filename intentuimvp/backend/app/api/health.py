"""Health check endpoint for liveness/readiness probes."""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns the service status and version for liveness/readiness probes.
    """
    return {
        "status": "ok",
        "version": settings.app_version,
    }
