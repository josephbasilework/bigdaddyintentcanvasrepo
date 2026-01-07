"""Job artifact storage and retrieval service.

Provides storage abstraction for job artifacts, supporting both:
- File-based storage for large artifacts (using existing attachment storage)
- Inline storage for small artifacts (stored directly in database)
"""

import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactType, JobArtifact
from app.models.attachment import LocalAttachmentStorage

logger = logging.getLogger(__name__)


# Configuration constants
INLINE_SIZE_THRESHOLD = 10240  # 10KB - store inline if smaller
DEFAULT_ARCHIVE_AFTER_DAYS = 30  # Default TTL for artifacts
ARTIFACT_STORAGE_PATH = "job_artifacts"  # Base path for artifact files


class ArtifactMetadata(BaseModel):
    """Metadata for a job artifact."""

    artifact_type: ArtifactType
    artifact_name: str
    description: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    archive_after_days: int | None = DEFAULT_ARCHIVE_AFTER_DAYS


class StoredArtifact(BaseModel):
    """Representation of a stored artifact."""

    id: int
    job_id: str
    user_id: str | None
    workspace_id: str | None
    artifact_type: str
    artifact_name: str
    description: str | None
    filename: str | None
    mime_type: str | None
    size_bytes: int | None
    storage_path: str | None
    inline_data: str | None
    is_archived: bool
    created_at: str
    updated_at: str

    def is_inline(self) -> bool:
        """Check if artifact is stored inline."""
        return self.inline_data is not None

    def is_file_based(self) -> bool:
        """Check if artifact is stored as a file."""
        return self.storage_path is not None

    @classmethod
    def from_model(cls, artifact: JobArtifact) -> "StoredArtifact":
        """Create StoredArtifact from JobArtifact model."""
        return cls(**artifact.to_dict())


class ArtifactStorageService:
    """Service for storing and retrieving job artifacts.

    Supports:
    - Inline storage for small artifacts (stored in database)
    - File-based storage for large artifacts (using filesystem)
    - Automatic cleanup and archival
    """

    def __init__(
        self,
        storage_path: str = ARTIFACT_STORAGE_PATH,
        inline_threshold: int = INLINE_SIZE_THRESHOLD,
    ) -> None:
        """Initialize the artifact storage service.

        Args:
            storage_path: Base path for file-based storage.
            inline_threshold: Size threshold in bytes for inline storage.
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.inline_threshold = inline_threshold

        # Initialize local attachment storage for file-based artifacts
        self._file_storage = LocalAttachmentStorage(str(self.storage_path))

    def _get_storage_path(
        self, job_id: str, artifact_id: int, filename: str | None = None
    ) -> str:
        """Get the storage path for a file-based artifact.

        Args:
            job_id: The job ID.
            artifact_id: The artifact database ID.
            filename: Optional filename for the file.

        Returns:
            Absolute path to the storage location.
        """
        job_dir = self.storage_path / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            safe_filename = "".join(
                c if c.isalnum() or c in "._-" else "_" for c in filename
            )
            return str(job_dir / f"{artifact_id}_{safe_filename}")

        return str(job_dir / str(artifact_id))

    async def store_artifact(
        self,
        db: AsyncSession,
        job_id: str,
        metadata: ArtifactMetadata,
        content: str | bytes,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> StoredArtifact:
        """Store a job artifact.

        Automatically chooses between inline and file-based storage
        based on content size.

        Args:
            db: Database session.
            job_id: The job ID that produced this artifact.
            metadata: Artifact metadata.
            content: Artifact content (string or bytes).
            user_id: Optional user ID for access control.
            workspace_id: Optional workspace ID.

        Returns:
            StoredArtifact with database record details.
        """
        # Determine size and mime type
        if isinstance(content, str):
            size_bytes = len(content.encode("utf-8"))
            mime_type = metadata.mime_type or "text/plain"
        else:
            size_bytes = len(content)
            mime_type = metadata.mime_type or "application/octet-stream"

        # Decide storage strategy based on size
        if size_bytes <= self.inline_threshold:
            storage_path = None
            inline_data = content if isinstance(content, str) else content.decode("utf-8")
        else:
            # Store as file
            artifact_id = 0  # Will be set after DB insert
            temp_filename = metadata.filename or f"{uuid.uuid4()}.bin"
            storage_path = self._get_storage_path(job_id, artifact_id, temp_filename)

            # Write file
            content_bytes = (
                content.encode("utf-8") if isinstance(content, str) else content
            )
            storage_path = await self._file_storage.store(
                user_id or "system",
                temp_filename,
                content_bytes,
                mime_type,
            )
            inline_data = None

        # Create database record
        artifact = JobArtifact(
            job_id=job_id,
            user_id=user_id,
            workspace_id=workspace_id,
            artifact_type=metadata.artifact_type.value,
            artifact_name=metadata.artifact_name,
            description=metadata.description,
            filename=metadata.filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            inline_data=inline_data,
            archive_after_days=metadata.archive_after_days,
        )

        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)

        logger.info(
            f"Stored artifact {artifact.id} for job {job_id} "
            f"(inline={artifact.is_inline()}, size={size_bytes})"
        )

        return StoredArtifact.from_model(artifact)

    async def get_artifact(
        self, db: AsyncSession, artifact_id: int
    ) -> StoredArtifact | None:
        """Get artifact metadata by ID.

        Args:
            db: Database session.
            artifact_id: The artifact ID.

        Returns:
            StoredArtifact or None if not found.
        """
        result = await db.execute(select(JobArtifact).where(JobArtifact.id == artifact_id))
        artifact = result.scalar_one_or_none()

        if artifact:
            return StoredArtifact.from_model(artifact)
        return None

    async def get_artifact_content(
        self, db: AsyncSession, artifact_id: int
    ) -> tuple[StoredArtifact, str | bytes] | None:
        """Get artifact with its content.

        Args:
            db: Database session.
            artifact_id: The artifact ID.

        Returns:
            Tuple of (StoredArtifact, content) or None if not found.
        """
        artifact = await self.get_artifact(db, artifact_id)
        if not artifact:
            return None

        # Load content based on storage type
        if artifact.is_inline():
            content: str | bytes = artifact.inline_data or ""
        else:
            if not artifact.storage_path:
                return None
            content_bytes = await self._file_storage.retrieve(artifact.storage_path)
            # Return as bytes for binary, str for text
            if artifact.mime_type and artifact.mime_type.startswith("text/"):
                content = content_bytes.decode("utf-8")
            else:
                content = content_bytes

        return (artifact, content)

    async def list_job_artifacts(
        self,
        db: AsyncSession,
        job_id: str,
        artifact_type: ArtifactType | None = None,
        include_archived: bool = False,
    ) -> list[StoredArtifact]:
        """List all artifacts for a job.

        Args:
            db: Database session.
            job_id: The job ID.
            artifact_type: Optional filter by artifact type.
            include_archived: Whether to include archived artifacts.

        Returns:
            List of StoredArtifacts.
        """
        query = select(JobArtifact).where(JobArtifact.job_id == job_id)

        if artifact_type:
            query = query.where(JobArtifact.artifact_type == artifact_type.value)

        if not include_archived:
            query = query.where(JobArtifact.is_archived == 0)

        query = query.order_by(JobArtifact.created_at)

        result = await db.execute(query)
        artifacts = result.scalars().all()

        return [StoredArtifact.from_model(a) for a in artifacts]

    async def delete_artifact(self, db: AsyncSession, artifact_id: int) -> bool:
        """Delete an artifact.

        Removes both the database record and the file (if applicable).

        Args:
            db: Database session.
            artifact_id: The artifact ID.

        Returns:
            True if deleted successfully.
        """
        artifact = await self.get_artifact(db, artifact_id)
        if not artifact:
            return False

        # Delete file if applicable
        if artifact.storage_path:
            try:
                await self._file_storage.delete(artifact.storage_path)
            except Exception as e:
                logger.warning(f"Failed to delete artifact file: {e}")

        # Delete database record
        result = await db.execute(
            select(JobArtifact).where(JobArtifact.id == artifact_id)
        )
        db_artifact = result.scalar_one_or_none()
        if db_artifact:
            await db.delete(db_artifact)
            await db.commit()
            logger.info(f"Deleted artifact {artifact_id}")
            return True

        return False

    async def archive_artifact(self, db: AsyncSession, artifact_id: int) -> bool:
        """Mark an artifact as archived.

        Args:
            db: Database session.
            artifact_id: The artifact ID.

        Returns:
            True if archived successfully.
        """
        result = await db.execute(
            select(JobArtifact).where(JobArtifact.id == artifact_id)
        )
        artifact = result.scalar_one_or_none()

        if artifact:
            artifact.is_archived = 1
            await db.commit()
            logger.info(f"Archived artifact {artifact_id}")
            return True

        return False

    async def cleanup_expired_artifacts(
        self, db: AsyncSession, dry_run: bool = False
    ) -> list[StoredArtifact]:
        """Find and optionally delete artifacts past their TTL.

        Args:
            db: Database session.
            dry_run: If True, only return expired artifacts without deleting.

        Returns:
            List of expired artifacts that were (or would be) deleted.
        """
        # Find artifacts with custom archive_after_days
        result = await db.execute(
            select(JobArtifact).where(
                JobArtifact.archive_after_days.isnot(None),
                JobArtifact.is_archived == 0,
            )
        )
        all_artifacts = result.scalars().all()

        expired = []
        for artifact in all_artifacts:
            if artifact.archive_after_days:
                expiry = artifact.created_at + timedelta(days=artifact.archive_after_days)
                if datetime.utcnow() > expiry:
                    expired.append(StoredArtifact.from_model(artifact))

        if dry_run:
            logger.info(f"Dry run: would delete {len(expired)} expired artifacts")
            return expired

        # Delete expired artifacts
        for expired_artifact in expired:
            await self.delete_artifact(db, expired_artifact.id)

        logger.info(f"Cleaned up {len(expired)} expired artifacts")
        return expired


# Singleton instance
_artifact_service: ArtifactStorageService | None = None


def get_artifact_storage() -> ArtifactStorageService:
    """Get the singleton artifact storage service.

    Returns:
        Artifact storage service instance.
    """
    global _artifact_service
    if _artifact_service is None:
        _artifact_service = ArtifactStorageService()
    return _artifact_service
