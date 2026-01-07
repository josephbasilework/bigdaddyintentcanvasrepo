"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from logging import getLogger

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.backup import router as backup_router
from app.api.context import router as context_router
from app.api.health import router as health_router
from app.api.preferences import router as preferences_router
from app.api.workspace import router as workspace_router
from app.config import get_settings
from app.database import SessionLocal
from app.services.backup_service import BackupService
from app.ws import router as ws_router

logger = getLogger(__name__)
settings = get_settings()
_scheduler: BackgroundScheduler | None = None


def _run_scheduled_backups() -> None:
    """Run scheduled backups for all users.

    This function is called by APScheduler on a daily schedule.
    It creates backups for all users who have canvas data or preferences.
    """
    db: Session | None = None
    try:
        db = SessionLocal()
        service = BackupService(db)

        # Get unique user IDs from canvas and preferences tables
        from app.models.canvas import Canvas
        from app.models.preferences import Preferences

        canvas_users = {u[0] for u in db.query(Canvas.user_id).distinct().all()}
        prefs_users = {u[0] for u in db.query(Preferences.user_id).distinct().all()}
        all_users = canvas_users | prefs_users

        backups_created = 0
        for user_id in all_users:
            try:
                service.create_backup(user_id=user_id)
                backups_created += 1
            except Exception as e:
                logger.error(f"Failed to create scheduled backup for user {user_id}: {e}")

        logger.info(f"Scheduled backups completed: {backups_created} backups created")

    except Exception as e:
        logger.error(f"Failed to run scheduled backups: {e}", exc_info=True)
    finally:
        if db:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events. Resources are initialized
    on startup and cleaned up on shutdown.

    On startup:
    - Initializes APScheduler for daily backups (if enabled)

    On shutdown:
    - Shuts down the scheduler
    """
    global _scheduler

    # Startup
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Environment: {settings.environment}")

    # Initialize backup scheduler if enabled
    if settings.backup_enabled:
        _scheduler = BackgroundScheduler()
        _scheduler.add_job(
            _run_scheduled_backups,
            "cron",
            hour=settings.backup_schedule_hour,
            minute=0,
            id="daily_backup",
            name="Daily backup job",
        )
        _scheduler.start()
        logger.info(
            f"Backup scheduler started: daily at {settings.backup_schedule_hour:02d}:00"
        )
        print(f"Backup scheduler started: daily at {settings.backup_schedule_hour:02d}:00")
    else:
        logger.info("Backup scheduler disabled")
        print("Backup scheduler disabled")

    yield

    # Shutdown
    if _scheduler:
        _scheduler.shutdown()
        logger.info("Backup scheduler stopped")
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
    app.include_router(workspace_router, tags=["workspace"])
    app.include_router(preferences_router, tags=["preferences"])
    app.include_router(backup_router, tags=["backup"])

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
