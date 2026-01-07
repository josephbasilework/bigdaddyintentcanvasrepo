"""SQLAlchemy models for job persistence and progress tracking."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Job(Base):
    """Job model for persistent tracking of background jobs.

    Provides database persistence for ARQ jobs, enabling:
    - Job history and audit trail
    - Progress percentage tracking
    - Step-by-step status updates
    - Result storage for completed jobs
    """

    __tablename__ = "job"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # ARQ job ID (UUID string) - matches Redis key
    job_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    # User who initiated the job
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # Workspace context for the job
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # Job type (deep_research, perspective_gather, synthesis, export, import, custom)
    job_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Job status (pending, queued, in_progress, complete, failed, cancelled)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)
    # Progress percentage (0-100)
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Current step description (e.g., "Gathering perspectives...")
    current_step: Mapped[str | None] = mapped_column(String, nullable=True)
    # Total number of steps in the job
    steps_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Current step number (1-indexed)
    step_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Job parameters (JSON string)
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Job result data (JSON string) - populated on completion
    result_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Error message (if failed)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Additional metadata (JSON string) - renamed to avoid SQLAlchemy reserved word
    job_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When the job was created
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    # When the job started processing
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # When the job completed (successfully or failed)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Last update timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "job_type": self.job_type,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "current_step": self.current_step,
            "steps_total": self.steps_total,
            "step_number": self.step_number,
            "parameters": self.parameters,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "metadata": self.job_metadata,  # Return as 'metadata' for API compatibility
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
