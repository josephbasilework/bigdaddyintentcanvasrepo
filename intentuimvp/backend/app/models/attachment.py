"""Models for file attachment handling.

Supports various attachment types (images, audio, documents) with
metadata extraction and storage abstraction.
"""

import logging
import os
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AttachmentType(str, Enum):
    """Types of attachments supported by the system."""

    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    CODE = "code"
    OTHER = "other"


class AttachmentStatus(str, Enum):
    """Status of attachment processing."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class AttachmentMetadata(BaseModel):
    """Metadata extracted from an attachment."""

    original_filename: str
    mime_type: str
    size_bytes: int
    attachment_type: AttachmentType

    # Optional extracted content
    text_content: str | None = None  # For documents/code
    transcription: str | None = None  # For audio
    description: str | None = None  # AI-generated description (for images)

    # Processing info
    status: AttachmentStatus = AttachmentStatus.PENDING
    error_message: str | None = None
    processed_at: datetime | None = None


class Attachment(BaseModel):
    """A file attachment with metadata and storage reference."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    metadata: AttachmentMetadata
    storage_path: str  # Path or URL where the file is stored
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Context information
    context_id: str | None = None  # Optional link to a context/session


class AttachmentStorage:
    """Abstract interface for attachment storage.

    Implementations can store files locally, in S3, or other storage backends.
    """

    async def store(
        self,
        user_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
    ) -> str:
        """Store an attachment and return its storage path.

        Args:
            user_id: User ID who owns the attachment.
            filename: Original filename.
            content: File content as bytes.
            mime_type: MIME type of the file.

        Returns:
            Storage path or URL for the stored file.
        """
        raise NotImplementedError

    async def retrieve(self, storage_path: str) -> bytes:
        """Retrieve an attachment's content.

        Args:
            storage_path: Path or URL of the stored file.

        Returns:
            File content as bytes.
        """
        raise NotImplementedError

    async def delete(self, storage_path: str) -> bool:
        """Delete an attachment.

        Args:
            storage_path: Path or URL of the stored file.

        Returns:
            True if deleted successfully.
        """
        raise NotImplementedError


class LocalAttachmentStorage(AttachmentStorage):
    """Local filesystem storage for attachments.

    Stores files in a configurable directory structure:
    <base_path>/<user_id>/<attachment_id>/<filename>
    """

    def __init__(self, base_path: str = "attachments") -> None:
        """Initialize local storage.

        Args:
            base_path: Base directory for attachment storage.
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_storage_path(
        self, user_id: str, attachment_id: str, filename: str
    ) -> str:
        """Get the full storage path for an attachment.

        Args:
            user_id: User ID.
            attachment_id: Attachment ID.
            filename: Original filename.

        Returns:
            Absolute path to the storage location.
        """
        # Sanitize filename
        safe_filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        user_dir = self.base_path / user_id
        attachment_dir = user_dir / attachment_id
        attachment_dir.mkdir(parents=True, exist_ok=True)
        return str(attachment_dir / safe_filename)

    async def store(
        self,
        user_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
    ) -> str:
        """Store an attachment on the local filesystem.

        Args:
            user_id: User ID who owns the attachment.
            filename: Original filename.
            content: File content as bytes.
            mime_type: MIME type of the file.

        Returns:
            Storage path for the stored file.
        """
        attachment_id = str(uuid.uuid4())
        storage_path = self._get_storage_path(user_id, attachment_id, filename)

        with open(storage_path, "wb") as f:
            f.write(content)

        logger.info(f"Stored attachment: {storage_path}")
        return storage_path

    async def retrieve(self, storage_path: str) -> bytes:
        """Retrieve an attachment's content from local filesystem.

        Args:
            storage_path: Path to the stored file.

        Returns:
            File content as bytes.

        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        if not os.path.exists(storage_path):
            raise FileNotFoundError(f"Attachment not found: {storage_path}")

        with open(storage_path, "rb") as f:
            return f.read()

    async def delete(self, storage_path: str) -> bool:
        """Delete an attachment from local filesystem.

        Args:
            storage_path: Path to the stored file.

        Returns:
            True if deleted successfully.
        """
        try:
            if os.path.exists(storage_path):
                os.remove(storage_path)
                logger.info(f"Deleted attachment: {storage_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete attachment: {e}")
            return False


def determine_attachment_type(filename: str, mime_type: str) -> AttachmentType:
    """Determine the attachment type from filename and MIME type.

    Args:
        filename: The filename.
        mime_type: The MIME type.

    Returns:
        The determined AttachmentType.
    """
    # Check MIME type first
    if mime_type.startswith("image/"):
        return AttachmentType.IMAGE
    if mime_type.startswith("audio/"):
        return AttachmentType.AUDIO
    if mime_type.startswith("video/"):
        return AttachmentType.VIDEO

    # Check by extension
    ext = os.path.splitext(filename)[1].lower()
    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}
    audio_exts = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"}
    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    code_exts = {".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".rb", ".php"}
    doc_exts = {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf"}

    if ext in image_exts:
        return AttachmentType.IMAGE
    if ext in audio_exts:
        return AttachmentType.AUDIO
    if ext in video_exts:
        return AttachmentType.VIDEO
    if ext in code_exts:
        return AttachmentType.CODE
    if ext in doc_exts:
        return AttachmentType.DOCUMENT

    return AttachmentType.OTHER


# Singleton storage instance
_storage: AttachmentStorage | None = None


def get_attachment_storage() -> AttachmentStorage:
    """Get the singleton attachment storage instance.

    Returns:
        Attachment storage instance.
    """
    global _storage
    if _storage is None:
        # Use local storage by default
        # Can be configured to use S3 or other storage
        _storage = LocalAttachmentStorage()
    return _storage
