"""SQLAlchemy model for Job artifact storage and retrieval.

Provides database persistence for job artifacts (files, blobs, documents)
produced during job execution.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ArtifactType(str, Enum):
    """Types of artifacts stored by jobs."""

    # Research outputs
    RESEARCH_REPORT = "research_report"
    SYNTHESIS_OUTPUT = "synthesis_output"
    PERSPECTIVE_RESULT = "perspective_result"

    # Documents
    PDF_DOCUMENT = "pdf_document"
    TEXT_DOCUMENT = "text_document"
    MARKDOWN_DOCUMENT = "markdown_document"

    # Data exports
    JSON_EXPORT = "json_export"
    CSV_EXPORT = "csv_export"

    # Images/visualizations
    CHART = "chart"
    GRAPH = "graph"
    IMAGE = "image"

    # Other
    LOG_FILE = "log_file"
    ATTACHMENT = "attachment"
    OTHER = "other"


class JobArtifact(Base):
    """Job artifact model for persistent storage of job outputs.

    Enables storage of:
    - Large binary files produced during job execution
    - Research reports and synthesis outputs
    - Exported data files
    - Images and visualizations
    """

    __tablename__ = "job_artifact"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Reference to the job that produced this artifact
    job_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True, comment="ARQ job ID (UUID string)"
    )
    # User who owns the job (for access control)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # Workspace context
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # Artifact identification
    artifact_type: Mapped[str] = mapped_column(
        String, nullable=False, index=True, comment="Type of artifact (ArtifactType enum)"
    )
    artifact_name: Mapped[str] = mapped_column(
        String, nullable=False, comment="Human-readable name for the artifact"
    )
    description: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Optional description of the artifact"
    )

    # File metadata
    filename: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Original filename (if applicable)"
    )
    mime_type: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="MIME type of the content"
    )
    size_bytes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Size of the artifact in bytes"
    )

    # Storage reference
    storage_path: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Path or URL where the artifact is stored"
    )
    # For inline storage (small artifacts), store as text
    inline_data: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Inline data for small artifacts (JSON, text, etc.)"
    )

    # Metadata and timestamps
    is_archived: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Whether the artifact is archived (0/1)"
    )
    archive_after_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Days after creation when this should be auto-archived",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
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
            "artifact_type": self.artifact_type,
            "artifact_name": self.artifact_name,
            "description": self.description,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "storage_path": self.storage_path,
            "inline_data": self.inline_data,
            "is_archived": bool(self.is_archived),
            "archive_after_days": self.archive_after_days,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_inline(self) -> bool:
        """Check if artifact is stored inline."""
        return self.inline_data is not None

    def is_file_based(self) -> bool:
        """Check if artifact is stored as a file."""
        return self.storage_path is not None
