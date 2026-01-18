"""Repository for AudioBlock CRUD operations."""

import base64
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import UnaryExpression, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import LocalAttachmentStorage
from app.models.audio_block import AudioBlock, AudioBlockStatus
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class AudioBlockRepository(BaseRepository[AudioBlock, Any, Any]):
    """Repository for audio block CRUD operations.

    Provides methods for creating, reading, updating, and deleting
    audio block records with file storage support.
    """

    def __init__(self, db: AsyncSession, storage_path: str = "audio_blocks") -> None:
        """Initialize repository with database session and storage.

        Args:
            db: SQLAlchemy async session
            storage_path: Base path for audio file storage
        """
        super().__init__(db)
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.attachment_storage = LocalAttachmentStorage(str(self.storage_path))

    @property
    def model(self) -> type[AudioBlock]:
        """Return the AudioBlock model."""
        return AudioBlock

    async def get_by_canvas(
        self,
        canvas_id: int,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AudioBlock]:
        """Get audio blocks by canvas ID with pagination.

        Args:
            canvas_id: Canvas identifier
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audio blocks belonging to the canvas
        """
        stmt = (
            select(AudioBlock)
            .where(AudioBlock.canvas_id == canvas_id)
            .order_by(AudioBlock.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_from_data(
        self,
        canvas_id: int,
        audio_data: str | None = None,
        audio_uri: str | None = None,
        duration: float | None = None,
    ) -> AudioBlock:
        """Create a new audio block with file storage.

        Args:
            canvas_id: Canvas identifier
            audio_data: Base64-encoded audio data (for direct upload)
            audio_uri: URI/path to already-stored audio file
            duration: Duration of audio in seconds

        Returns:
            Created audio block

        Raises:
            ValueError: If neither audio_data nor audio_uri is provided
        """
        if audio_uri:
            # Use provided URI directly
            final_uri = audio_uri
        elif audio_data:
            # Decode base64 and store the file
            try:
                # Remove data URL prefix if present (e.g., "data:audio/webm;base64,")
                if "," in audio_data:
                    audio_data = audio_data.split(",", 1)[1]

                audio_bytes = base64.b64decode(audio_data)
                filename = f"{uuid.uuid4()}.webm"
                final_uri = await self.attachment_storage.store(
                    user_id=str(canvas_id),
                    attachment_id=None,
                    filename=filename,
                    content=audio_bytes,
                    mime_type="audio/webm",
                )
                logger.info(f"Stored audio file: {final_uri} ({len(audio_bytes)} bytes)")
            except Exception as e:
                logger.error(f"Failed to store audio data: {e}", exc_info=True)
                raise ValueError(f"Failed to store audio data: {e}") from e
        else:
            raise ValueError("Either audio_data or audio_uri must be provided")

        return await self.create(
            canvas_id=canvas_id,
            audio_uri=final_uri,
            duration=duration,
            status=AudioBlockStatus.READY,
        )

    async def update_transcription(
        self,
        audio_block_id: int,
        transcription: str,
    ) -> AudioBlock | None:
        """Update the transcription for an audio block.

        Args:
            audio_block_id: Audio block identifier
            transcription: Transcribed text content

        Returns:
            Updated audio block if found, None otherwise
        """
        return await self.update(
            audio_block_id,
            transcription=transcription,
            status=AudioBlockStatus.TRANSCRIBED,
        )

    async def set_status(
        self,
        audio_block_id: int,
        status: AudioBlockStatus,
        error_message: str | None = None,
    ) -> AudioBlock | None:
        """Update the status of an audio block.

        Args:
            audio_block_id: Audio block identifier
            status: New status
            error_message: Optional error message for error status

        Returns:
            Updated audio block if found, None otherwise
        """
        updates: dict[str, Any] = {"status": status}
        if error_message is not None:
            updates["error_message"] = error_message
        return await self.update(audio_block_id, **updates)

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        order_by: UnaryExpression[Any] | None = None,
    ) -> list[AudioBlock]:
        """List audio blocks with pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            order_by: Optional ordering clause

        Returns:
            List of audio blocks
        """
        return await super().list(offset=offset, limit=limit, order_by=order_by)

    async def delete_audio_file(self, audio_block_id: int) -> bool:
        """Delete an audio block and its associated file.

        Args:
            audio_block_id: Audio block identifier

        Returns:
            True if deleted, False if not found

        Raises:
            Exception: If file deletion fails
        """
        audio_block = await self.get_by_id(audio_block_id)
        if audio_block is None:
            return False

        # Delete the associated file
        try:
            await self.attachment_storage.delete(audio_block.audio_uri)
            logger.info(f"Deleted audio file: {audio_block.audio_uri}")
        except Exception as e:
            logger.warning(f"Failed to delete audio file {audio_block.audio_uri}: {e}")

        # Delete the database record
        return await self.delete(audio_block_id)
