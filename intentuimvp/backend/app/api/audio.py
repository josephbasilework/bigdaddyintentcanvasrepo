"""Audio block API endpoints for CRUD operations."""

import logging
import mimetypes
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.jobs.service import JobService
from app.models.audio_block import AudioBlock, AudioBlockStatus
from app.repositories.audio_block_repo import AudioBlockRepository
from app.schemas.audio_block import (
    AudioBlockCreateRequest,
    AudioBlockListResponse,
    AudioBlockResponse,
    AudioBlockUpdateRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user() -> str:
    """Get current user from authentication.

    Basic implementation using a simple header.
    TODO: Replace with proper JWT/OAuth authentication.

    Returns:
        User ID string
    """
    return "default_user"  # MVP: single user for now


def _serialize_audio_block(audio_block: AudioBlock) -> dict[str, Any]:
    """Serialize audio block model to API response payload."""
    return {
        "id": audio_block.id,
        "canvasId": audio_block.canvas_id,
        "audioUri": audio_block.audio_uri,
        "transcription": audio_block.transcription,
        "duration": audio_block.duration,
        "status": audio_block.status,
        "errorMessage": audio_block.error_message,
        "created_at": audio_block.created_at.isoformat(),
        "updated_at": audio_block.updated_at.isoformat(),
    }


@router.post(
    "/api/audio/blocks",
    response_model=AudioBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_audio_block(
    payload: AudioBlockCreateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Create a new audio block.

    Args:
        payload: Audio block creation data
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Created audio block data

    Raises:
        HTTPException: If audio block creation fails
    """
    try:
        repo = AudioBlockRepository(db)
        audio_block = await repo.create_from_data(
            canvas_id=payload.canvas_id,
            audio_data=payload.audio_data,
            audio_uri=payload.audio_uri,
            duration=payload.duration,
        )
        logger.info(
            f"Created audio block {audio_block.id} on canvas {payload.canvas_id} "
            f"for user {user_id}"
        )
        return _serialize_audio_block(audio_block)
    except IntegrityError as e:
        logger.warning(
            f"Failed to create audio block on canvas {payload.canvas_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid canvas_id",
        ) from e
    except ValueError as e:
        logger.warning(f"Invalid audio data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to create audio block for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create audio block",
        ) from e


@router.get("/api/audio/blocks", response_model=AudioBlockListResponse)
async def list_audio_blocks(
    canvas_id: int | None = Query(default=None, description="Filter by canvas ID"),
    offset: int = Query(default=0, ge=0, description="Number of blocks to skip"),
    limit: int = Query(default=100, ge=1, le=500, description="Max blocks to return"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """List audio blocks with optional canvas filter.

    Args:
        canvas_id: Optional canvas identifier to filter blocks
        offset: Pagination offset
        limit: Pagination limit
        db: Database session
        user_id: Authenticated user ID

    Returns:
        List of audio block data with count
    """
    repo = AudioBlockRepository(db)
    if canvas_id is not None:
        blocks = await repo.get_by_canvas(canvas_id, offset=offset, limit=limit)
        logger.info(
            f"Retrieved {len(blocks)} audio blocks for canvas {canvas_id} "
            f"(user {user_id})"
        )
    else:
        blocks = await repo.list(offset=offset, limit=limit)
        logger.info(f"Retrieved {len(blocks)} audio blocks for user {user_id}")

    return {
        "audio_blocks": [_serialize_audio_block(block) for block in blocks],
        "count": len(blocks),
    }


@router.get("/api/audio/blocks/{block_id}", response_model=AudioBlockResponse)
async def get_audio_block(
    block_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get audio block by ID.

    Args:
        block_id: Audio block identifier
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Audio block data

    Raises:
        HTTPException: If audio block not found
    """
    repo = AudioBlockRepository(db)
    block = await repo.get_by_id(block_id)
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio block not found",
        )

    logger.info(f"Retrieved audio block {block_id} for user {user_id}")
    return _serialize_audio_block(block)


@router.put("/api/audio/blocks/{block_id}", response_model=AudioBlockResponse)
async def update_audio_block(
    block_id: int,
    payload: AudioBlockUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict:
    """Update audio block by ID.

    Args:
        block_id: Audio block identifier
        payload: Audio block update data
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Updated audio block data

    Raises:
        HTTPException: If audio block not found or update fails
    """
    repo = AudioBlockRepository(db)
    block = await repo.get_by_id(block_id)
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio block not found",
        )

    updates: dict[str, Any] = {}
    fields_set = payload.model_fields_set

    if "transcription" in fields_set:
        updates["transcription"] = payload.transcription
    if "status" in fields_set and payload.status is not None:
        updates["status"] = payload.status
    if "error_message" in fields_set:
        updates["error_message"] = payload.error_message

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    try:
        updated = await repo.update(block_id, **updates)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audio block not found",
            )
        logger.info(f"Updated audio block {block_id} for user {user_id}")
        return _serialize_audio_block(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update audio block {block_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update audio block",
        ) from e


@router.delete("/api/audio/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audio_block(
    block_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> None:
    """Delete audio block by ID and its associated file.

    Args:
        block_id: Audio block identifier
        db: Database session
        user_id: Authenticated user ID

    Raises:
        HTTPException: If audio block not found
    """
    repo = AudioBlockRepository(db)
    deleted = await repo.delete_audio_file(block_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio block not found",
        )
    logger.info(f"Deleted audio block {block_id} for user {user_id}")


@router.get("/api/audio/blocks/{block_id}/content")
async def get_audio_block_content(
    block_id: int,
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Retrieve raw audio content for playback."""
    repo = AudioBlockRepository(db)
    block = await repo.get_by_id(block_id)
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio block not found",
        )

    audio_uri = block.audio_uri
    if audio_uri.startswith("http://") or audio_uri.startswith("https://"):
        return RedirectResponse(audio_uri)

    file_path = Path(audio_uri)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found",
        )

    mime_type, _ = mimetypes.guess_type(file_path.name)
    if mime_type == "video/webm":
        mime_type = "audio/webm"
    return FileResponse(
        path=file_path,
        media_type=mime_type or "audio/webm",
        filename=file_path.name,
    )


@router.post("/api/audio/blocks/{block_id}/transcribe")
async def transcribe_audio_block(
    block_id: int,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict[str, str]:
    """Enqueue transcription for an audio block."""
    repo = AudioBlockRepository(db)
    block = await repo.get_by_id(block_id)
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio block not found",
        )

    if block.status == AudioBlockStatus.TRANSCRIBING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Audio block is already transcribing",
        )

    job_service = JobService()
    job_id = await job_service.enqueue_transcription(
        audio_block_id=block_id,
        user_id=user_id,
        workspace_id=str(block.canvas_id),
    )

    await repo.set_status(block_id, AudioBlockStatus.TRANSCRIBING)
    logger.info(f"Queued transcription job {job_id} for audio block {block_id}")

    return {"job_id": job_id, "status": "queued"}
