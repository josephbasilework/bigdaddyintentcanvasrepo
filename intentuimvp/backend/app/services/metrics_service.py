"""Metrics aggregation and query service for PRD §5.2 success metrics.

Provides computed values for all 7 PRD §5.2 success metrics over rolling windows.
Supports 24h and 7d rolling windows, per-user workspace views.

Metrics (from PRD §5.2):
1. Task Completion Rate (>80%)
2. Assumption Accuracy (>70%)
3. Time-to-Value (<30s for simple tasks)
4. Session Continuity (>60%)
5. Research Job Completion (>75%)
6. Command vs Chat Ratio (>3:1)
7. MCP Adoption (>30%)

Reference: intentuimvp/docs/telemetry_spec.md
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.telemetry_event import TelemetryEventDB
from app.telemetry_events import EventName

logger = logging.getLogger(__name__)


# Rolling window durations
WINDOW_24H = timedelta(hours=24)
WINDOW_7D = timedelta(days=7)


class MetricResult:
    """Result of a metric computation.

    Attributes:
        metric_name: Name of the metric
        value: Computed value
        target: Target value from PRD
        window: Rolling window (e.g., "24h", "7d")
        sample_size: Number of data points included
        metadata: Additional metadata about the computation
    """

    def __init__(
        self,
        metric_name: str,
        value: float,
        target: float,
        window: str,
        sample_size: int = 0,
        metadata: dict[str, Any] | None = None,
    ):
        self.metric_name = metric_name
        self.value = value
        self.target = target
        self.window = window
        self.sample_size = sample_size
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "target": self.target,
            "window": self.window,
            "sample_size": self.sample_size,
            "meets_target": self.value >= self.target if self.target > 0 else self.value <= self.target,
            **self.metadata,
        }


class MetricsService:
    """Service for computing and querying success metrics.

    Computes all 7 PRD §5.2 success metrics from stored telemetry events.
    Supports rolling windows (24h, 7d) and per-user filtering.
    """

    async def get_all_metrics(
        self,
        db: AsyncSession,
        window: str = "24h",
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Get all 7 success metrics for the given window.

        Args:
            db: Database session
            window: Rolling window ("24h" or "7d")
            user_id: Optional user filter
            workspace_id: Optional workspace filter

        Returns:
            Dictionary of metric results keyed by metric name
        """
        window_delta = WINDOW_24H if window == "24h" else WINDOW_7D
        cutoff = datetime.now(UTC) - window_delta

        metrics = {
            "task_completion_rate": await self.get_task_completion_rate(
                db, cutoff, window, user_id, workspace_id
            ),
            "assumption_accuracy": await self.get_assumption_accuracy(
                db, cutoff, window, user_id, workspace_id
            ),
            "time_to_value": await self.get_time_to_value(
                db, cutoff, window, user_id, workspace_id
            ),
            "session_continuity": await self.get_session_continuity(
                db, cutoff, window, user_id, workspace_id
            ),
            "research_job_completion": await self.get_research_job_completion(
                db, cutoff, window, user_id, workspace_id
            ),
            "command_vs_chat_ratio": await self.get_command_vs_chat_ratio(
                db, cutoff, window, user_id, workspace_id
            ),
            "mcp_adoption": await self.get_mcp_adoption(
                db, cutoff, window, user_id, workspace_id
            ),
        }

        return {k: v.to_dict() for k, v in metrics.items()}

    async def get_task_completion_rate(
        self,
        db: AsyncSession,
        cutoff: datetime,
        window: str,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> MetricResult:
        """Metric 1: Task Completion Rate (>80%).

        Computed as: (successful intents / total intents) * 100
        From intent.executed events where status = "success"
        """
        # Build query filters
        filters = [
            TelemetryEventDB.event_name == EventName.INTENT_EXECUTED,
            TelemetryEventDB.event_timestamp >= cutoff,
        ]
        if user_id:
            filters.append(TelemetryEventDB.user_id == user_id)
        if workspace_id:
            filters.append(TelemetryEventDB.workspace_id == workspace_id)

        # Count total and successful intents
        total_result = await db.execute(
            select(func.count()).select_from(TelemetryEventDB).where(*filters)
        )
        total_count = total_result.scalar() or 0

        # Filter for success status in event_data
        success_result = await db.execute(
            select(func.count())
            .select_from(TelemetryEventDB)
            .where(
                *filters,
                TelemetryEventDB.event_data.like('%"status": "success"%'),
            )
        )
        success_count = success_result.scalar() or 0

        value = (success_count / total_count * 100) if total_count > 0 else 0.0

        return MetricResult(
            metric_name="task_completion_rate",
            value=round(value, 2),
            target=80.0,
            window=window,
            sample_size=total_count,
            metadata={"success_count": success_count},
        )

    async def get_assumption_accuracy(
        self,
        db: AsyncSession,
        cutoff: datetime,
        window: str,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> MetricResult:
        """Metric 2: Assumption Accuracy (>70%).

        Computed as: (accepted without modification / total resolved) * 100
        From assumption.resolved events where resolution = "accepted_as_is"
        """
        filters = [
            TelemetryEventDB.event_name == EventName.ASSUMPTION_RESOLVED,
            TelemetryEventDB.event_timestamp >= cutoff,
        ]
        if user_id:
            filters.append(TelemetryEventDB.user_id == user_id)
        if workspace_id:
            filters.append(TelemetryEventDB.workspace_id == workspace_id)

        # Count total resolved assumptions
        total_result = await db.execute(
            select(func.count()).select_from(TelemetryEventDB).where(*filters)
        )
        total_count = total_result.scalar() or 0

        # Count accepted_as_is resolutions
        accepted_result = await db.execute(
            select(func.count())
            .select_from(TelemetryEventDB)
            .where(
                *filters,
                TelemetryEventDB.event_data.like('%"resolution": "accepted_as_is"%'),
            )
        )
        accepted_count = accepted_result.scalar() or 0

        value = (accepted_count / total_count * 100) if total_count > 0 else 0.0

        return MetricResult(
            metric_name="assumption_accuracy",
            value=round(value, 2),
            target=70.0,
            window=window,
            sample_size=total_count,
            metadata={"accepted_count": accepted_count},
        )

    async def get_time_to_value(
        self,
        db: AsyncSession,
        cutoff: datetime,
        window: str,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> MetricResult:
        """Metric 3: Time-to-Value (<30s for simple tasks).

        Computed as: average execution_duration_ms for is_simple_task=True intents
        Target is < 30 seconds (30000 ms)
        """
        filters = [
            TelemetryEventDB.event_name == EventName.INTENT_EXECUTED,
            TelemetryEventDB.event_timestamp >= cutoff,
            TelemetryEventDB.event_data.like('%"is_simple_task": true%'),
        ]
        if user_id:
            filters.append(TelemetryEventDB.user_id == user_id)
        if workspace_id:
            filters.append(TelemetryEventDB.workspace_id == workspace_id)

        # Get events and parse durations from event_data
        result = await db.execute(
            select(TelemetryEventDB.event_data).where(*filters)
        )
        event_data_list = result.scalars().all()

        durations_ms = []
        for event_data_str in event_data_list:
            if event_data_str is None:
                continue
            try:
                event_data = json.loads(event_data_str)
                duration = event_data.get("execution_duration_ms", 0)
                durations_ms.append(duration)
            except (json.JSONDecodeError, TypeError):
                continue

        avg_duration_ms = (
            sum(durations_ms) / len(durations_ms) if durations_ms else 0
        )

        return MetricResult(
            metric_name="time_to_value",
            value=round(avg_duration_ms, 2),
            target=30000.0,  # 30 seconds in ms
            window=window,
            sample_size=len(durations_ms),
            metadata={"unit": "ms"},
        )

    async def get_session_continuity(
        self,
        db: AsyncSession,
        cutoff: datetime,
        window: str,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> MetricResult:
        """Metric 4: Session Continuity (>60%).

        Computed as: (sessions with previous_session_id / total sessions) * 100
        From session.started events where previous_session_id is not null
        """
        filters = [
            TelemetryEventDB.event_name == EventName.SESSION_STARTED,
            TelemetryEventDB.event_timestamp >= cutoff,
        ]
        if user_id:
            filters.append(TelemetryEventDB.user_id == user_id)

        # Count total sessions
        total_result = await db.execute(
            select(func.count()).select_from(TelemetryEventDB).where(*filters)
        )
        total_count = total_result.scalar() or 0

        # Count sessions with previous_session_id (resuming)
        resuming_result = await db.execute(
            select(func.count())
            .select_from(TelemetryEventDB)
            .where(
                *filters,
                TelemetryEventDB.event_data.like('%"previous_session_id":%'),
            )
        )
        resuming_count = resuming_result.scalar() or 0

        value = (resuming_count / total_count * 100) if total_count > 0 else 0.0

        return MetricResult(
            metric_name="session_continuity",
            value=round(value, 2),
            target=60.0,
            window=window,
            sample_size=total_count,
            metadata={"resuming_count": resuming_count},
        )

    async def get_research_job_completion(
        self,
        db: AsyncSession,
        cutoff: datetime,
        window: str,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> MetricResult:
        """Metric 5: Research Job Completion (>75%).

        Computed as: (completed deep_research jobs / total deep_research jobs) * 100
        Uses Job table for accuracy (status = 'complete')
        """
        filters = [
            Job.job_type == "deep_research",
            Job.created_at >= cutoff,
        ]
        if user_id:
            filters.append(Job.user_id == user_id)
        if workspace_id:
            filters.append(Job.workspace_id == workspace_id)

        # Count total deep_research jobs
        total_result = await db.execute(
            select(func.count()).select_from(Job).where(*filters)
        )
        total_count = total_result.scalar() or 0

        # Count completed jobs
        completed_result = await db.execute(
            select(func.count())
            .select_from(Job)
            .where(
                *filters,
                Job.status == "complete",
            )
        )
        completed_count = completed_result.scalar() or 0

        value = (completed_count / total_count * 100) if total_count > 0 else 0.0

        return MetricResult(
            metric_name="research_job_completion",
            value=round(value, 2),
            target=75.0,
            window=window,
            sample_size=total_count,
            metadata={"completed_count": completed_count},
        )

    async def get_command_vs_chat_ratio(
        self,
        db: AsyncSession,
        cutoff: datetime,
        window: str,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> MetricResult:
        """Metric 6: Command vs Chat Ratio (>3:1).

        Computed as: command_count / chat_count
        From intent.submitted events where interaction_mode = "command" vs "chat"
        """
        filters = [
            TelemetryEventDB.event_name == EventName.INTENT_SUBMITTED,
            TelemetryEventDB.event_timestamp >= cutoff,
        ]
        if user_id:
            filters.append(TelemetryEventDB.user_id == user_id)
        if workspace_id:
            filters.append(TelemetryEventDB.workspace_id == workspace_id)

        # Count command interactions
        command_result = await db.execute(
            select(func.count())
            .select_from(TelemetryEventDB)
            .where(
                *filters,
                TelemetryEventDB.event_data.like('%"interaction_mode": "command"%'),
            )
        )
        command_count = command_result.scalar() or 0

        # Count chat interactions
        chat_result = await db.execute(
            select(func.count())
            .select_from(TelemetryEventDB)
            .where(
                *filters,
                TelemetryEventDB.event_data.like('%"interaction_mode": "chat"%'),
            )
        )
        chat_count = chat_result.scalar() or 0

        ratio = (command_count / chat_count) if chat_count > 0 else float(command_count)

        return MetricResult(
            metric_name="command_vs_chat_ratio",
            value=round(ratio, 2),
            target=3.0,
            window=window,
            sample_size=command_count + chat_count,
            metadata={
                "command_count": command_count,
                "chat_count": chat_count,
            },
        )

    async def get_mcp_adoption(
        self,
        db: AsyncSession,
        cutoff: datetime,
        window: str,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> MetricResult:
        """Metric 7: MCP Adoption (>30%).

        Computed as: (users with mcp.configured events / total unique users) * 100
        From mcp.configured events, counting unique user_ids
        """
        filters = [
            TelemetryEventDB.event_name == EventName.MCP_CONFIGURED,
            TelemetryEventDB.event_timestamp >= cutoff,
        ]

        if user_id:
            filters.append(TelemetryEventDB.user_id == user_id)

        # Count unique users with MCP configured
        mcp_users_result = await db.execute(
            select(func.count(func.distinct(TelemetryEventDB.user_id)))
            .select_from(TelemetryEventDB)
            .where(*filters)
        )
        mcp_user_count = mcp_users_result.scalar() or 0

        # Count total unique users in the same window (from any event)
        all_users_result = await db.execute(
            select(func.count(func.distinct(TelemetryEventDB.user_id)))
            .select_from(TelemetryEventDB)
            .where(
                TelemetryEventDB.event_timestamp >= cutoff,
                TelemetryEventDB.user_id.isnot(None),
            )
        )
        total_user_count = all_users_result.scalar() or 0

        # If user filter is specified, adoption is either 100% or 0%
        if user_id:
            value = 100.0 if mcp_user_count > 0 else 0.0
        else:
            value = (
                (mcp_user_count / total_user_count * 100) if total_user_count > 0 else 0.0
            )

        return MetricResult(
            metric_name="mcp_adoption",
            value=round(value, 2),
            target=30.0,
            window=window,
            sample_size=total_user_count,
            metadata={"users_with_mcp": mcp_user_count},
        )


# Singleton instance
_metrics_service: MetricsService | None = None


def get_metrics_service() -> MetricsService:
    """Get the singleton metrics service instance.

    Returns:
        Metrics service instance.
    """
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service
