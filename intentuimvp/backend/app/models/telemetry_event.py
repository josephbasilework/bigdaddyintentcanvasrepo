"""SQLAlchemy model for telemetry event storage.

Stores all telemetry events for success metrics aggregation and querying.
Implements PRD §5.2 success metrics tracking.

Events are stored for querying metrics over rolling windows (24h, 7d).
PII is redacted before storage per NFR-PRIV-004.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TelemetryEventDB(Base):
    """Telemetry event model for persistent storage.

    Stores all telemetry events emitted for PRD §5.2 success metrics.
    Enables querying metrics over rolling windows (24h, 7d).

    PII is redacted before storage per NFR-PRIV-004.
    User IDs are stored as provided but should be UUIDs or hashes, not raw PII.
    """

    __tablename__ = "telemetry_events"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Event identification
    event_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    event_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    # Correlation & context (all optional, indexed for query performance)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # Event data (JSON string)
    # Contains sanitized event data with PII redacted
    event_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    source_service: Mapped[str] = mapped_column(String, nullable=False, default="intent-api")
    environment: Mapped[str] = mapped_column(String, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_name": self.event_name,
            "event_timestamp": self.event_timestamp.isoformat() if self.event_timestamp else None,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "event_data": self.event_data,
            "source_service": self.source_service,
            "environment": self.environment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
