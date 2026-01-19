"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from logging import getLogger

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.attachments import router as attachments_router
from app.api.audio import router as audio_router
from app.api.backup import router as backup_router
from app.api.canvas_actions import router as canvas_actions_router
from app.api.commands import router as commands_router
from app.api.context import router as context_router
from app.api.dashboard_external import router as dashboard_external_router
from app.api.dashboard_subscriptions import router as dashboard_subscriptions_router
from app.api.edges import router as edges_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.hooks import router as hooks_router
from app.api.intent_memory import router as intent_memory_router
from app.api.jobs import router as jobs_router
from app.api.mcp import router as mcp_router
from app.api.nodes import router as nodes_router
from app.api.notifications import router as notifications_router
from app.api.preferences import router as preferences_router
from app.api.reminders import router as reminders_router
from app.api.runs import router as runs_router
from app.api.telemetry import router as telemetry_router
from app.api.turns import router as turns_router
from app.api.workspace import router as workspace_router
from app.config import get_settings
from app.copilotkit import setup_copilotkit
from app.database import SessionLocal
from app.logging_config import configure_logging
from app.middleware import LoggingMiddleware
from app.services.backup_service import BackupService
from app.services.hooks import run_due_scheduled_hooks
from app.services.intent_index import IntentIndexStore
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


async def _run_scheduled_intent_pruning_async() -> None:
    """Async function for intent index pruning.

    This function runs the async IntentIndexStore.prune_failed method.
    """
    intent_store = IntentIndexStore()
    # Prune failed intents older than 90 days per retention policy
    pruned = await intent_store.prune_failed(cutoff_days=90)
    logger.info(f"Scheduled intent pruning completed: {pruned} intents pruned")


def _run_scheduled_intent_pruning() -> None:
    """Run scheduled intent index pruning for retention policy (NFR-PRIV-001, §15.3).

    This function is called by APScheduler on a daily schedule.
    It prunes intent entries older than 90 days with outcome='failure'.
    """
    try:
        asyncio.run(_run_scheduled_intent_pruning_async())
    except Exception as e:
        logger.error(f"Failed to run scheduled intent pruning: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events. Resources are initialized
    on startup and cleaned up on shutdown.

    On startup:
    - Configures structured logging
    - Validates required environment variables
    - Initializes APScheduler for daily backups (if enabled)

    On shutdown:
    - Shuts down the scheduler
    """
    global _scheduler

    # Startup
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Environment: {settings.environment}")

    # Configure structured logging (FR-022, NFR-OBS-005)
    configure_logging(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        json_format=settings.environment == "production",
    )
    logger.info(
        "Application starting",
        extra={"event": "startup", "version": settings.app_version},
    )

    # Validate required Gateway API key
    if not settings.pydantic_gateway_api_key or settings.pydantic_gateway_api_key.strip() == "":
        raise RuntimeError("PYDANTIC_GATEWAY_API_KEY required")
    logger.info("Gateway API key configured")
    print("Gateway API key configured")

    scheduler: BackgroundScheduler | None = None
    if settings.backup_enabled or settings.hooks_enabled:
        scheduler = BackgroundScheduler()

    # Initialize backup scheduler if enabled
    if scheduler and settings.backup_enabled:
        scheduler.add_job(
            _run_scheduled_backups,
            "cron",
            hour=settings.backup_schedule_hour,
            minute=0,
            id="daily_backup",
            name="Daily backup job",
        )
        # Add daily intent pruning job (runs at 2 AM daily)
        scheduler.add_job(
            _run_scheduled_intent_pruning,
            "cron",
            hour=2,
            minute=0,
            id="daily_intent_prune",
            name="Daily intent pruning job",
        )
        logger.info(
            f"Backup scheduler started: daily at {settings.backup_schedule_hour:02d}:00"
        )
        print(f"Backup scheduler started: daily at {settings.backup_schedule_hour:02d}:00")
        logger.info("Intent pruning scheduler started: daily at 02:00")
        print("Intent pruning scheduler started: daily at 02:00")
    elif not settings.backup_enabled:
        logger.info("Backup scheduler disabled")
        print("Backup scheduler disabled")

    if scheduler and settings.hooks_enabled:
        scheduler.add_job(
            run_due_scheduled_hooks,
            "interval",
            seconds=settings.hooks_scheduler_interval_seconds,
            id="scheduled_hooks",
            name="Scheduled hook runner",
        )
        logger.info(
            "Hook scheduler started: interval %ss",
            settings.hooks_scheduler_interval_seconds,
        )

    if scheduler:
        scheduler.start()
        _scheduler = scheduler

    yield

    # Shutdown
    logger.info("Application shutting down")
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

    # Structured logging middleware (NFR-OBS-001, NFR-OBS-005)
    app.add_middleware(LoggingMiddleware)

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
    app.include_router(runs_router, tags=["runs"])
    app.include_router(commands_router, tags=["commands"])
    app.include_router(context_router, tags=["context"])
    app.include_router(workspace_router, tags=["workspace"])
    app.include_router(canvas_actions_router, tags=["canvas"])
    app.include_router(nodes_router, tags=["nodes"])
    app.include_router(edges_router, tags=["edges"])
    app.include_router(audio_router, tags=["audio"])
    app.include_router(attachments_router, tags=["attachments"])
    app.include_router(preferences_router, tags=["preferences"])
    app.include_router(notifications_router, tags=["notifications"])
    app.include_router(reminders_router, tags=["reminders"])
    app.include_router(dashboard_subscriptions_router, tags=["dashboard"])
    app.include_router(dashboard_external_router, tags=["dashboard"])
    app.include_router(backup_router, tags=["backup"])
    app.include_router(mcp_router, tags=["mcp"])
    app.include_router(jobs_router, tags=["jobs"])
    app.include_router(telemetry_router, tags=["telemetry"])
    app.include_router(turns_router, tags=["turns"])
    app.include_router(events_router, tags=["events"])
    app.include_router(hooks_router, tags=["hooks"])
    app.include_router(intent_memory_router, tags=["intent-memory"])

    # CopilotKit endpoint (PRD Section 9.3 EI-004)
    setup_copilotkit(app)

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
