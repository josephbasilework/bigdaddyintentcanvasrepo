"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.context import router as context_router
from app.api.health import router as health_router
from app.config import get_settings
from app.ws import router as ws_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events. Resources are initialized
    on startup and cleaned up on shutdown.
    """
    # Startup
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Environment: {settings.environment}")
    yield
    # Shutdown
    print("Shutting down application")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routers
    app.include_router(health_router, tags=["health"])
    app.include_router(ws_router, tags=["websocket"])
    app.include_router(context_router, tags=["context"])

    @app.get("/")
    async def root() -> dict[str, object]:
        """Root endpoint with basic application info."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "status": "operational",
        }

    return app


app = create_app()
