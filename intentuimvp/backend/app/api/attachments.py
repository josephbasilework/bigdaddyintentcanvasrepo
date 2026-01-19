"""Attachment ingestion API endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.models.intent import AttachmentDB
from app.schemas.attachment import (
    AttachmentListResponse,
    AttachmentResponse,
)
from app.services.attachments import (
    MAX_ATTACHMENT_BYTES,
    ingest_attachment,
    resolve_content_type,
    summarize_attachment,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def get_current_user() -> str:
    """Get current user from authentication.

    Basic implementation using a simple header.
    TODO: Replace with proper JWT/OAuth authentication.
    """
    return "default_user"  # MVP: single user for now


def _build_attachment_response(attachment: AttachmentDB) -> AttachmentResponse:
    summary = summarize_attachment(attachment)
    content_url = f"/api/attachments/{attachment.id}/content"
    return AttachmentResponse(
        id=attachment.id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        attachment_type=attachment.attachment_type,
        status=attachment.status,
        text_preview=summary.text_preview,
        description_preview=summary.description_preview,
        error_message=attachment.error_message,
        created_at=attachment.created_at.isoformat(),
        processed_at=attachment.processed_at.isoformat()
        if attachment.processed_at
        else None,
        session_id=attachment.session_id,
        turn_id=attachment.turn_id,
        node_id=attachment.node_id,
        artifact_id=attachment.artifact_id,
        content_url=content_url,
        preview_url=content_url,
    )


@router.post(
    "/api/attachments",
    response_model=AttachmentListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachments(
    files: list[UploadFile] = File(..., description="Files to upload"),
    session_id: str | None = Form(default=None),
    turn_id: int | None = Form(default=None),
    node_id: int | None = Form(default=None),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload one or more attachments."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided",
        )

    attachments: list[AttachmentResponse] = []
    for upload in files:
        try:
            attachment = await ingest_attachment(
                db,
                upload,
                user_id=user_id,
                session_id=session_id,
                turn_id=turn_id,
                node_id=node_id,
            )
        except ValueError as exc:
            await upload.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            await upload.close()
            logger.error("Attachment upload failed", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload attachment",
            ) from exc

        attachments.append(_build_attachment_response(attachment))

    return {
        "attachments": attachments,
        "count": len(attachments),
        "max_bytes": MAX_ATTACHMENT_BYTES,
    }


@router.get("/api/attachments/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment(
    attachment_id: str,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Get attachment metadata by ID."""
    attachment = await db.get(AttachmentDB, attachment_id)
    if attachment is None or attachment.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    return _build_attachment_response(attachment)


@router.get("/api/attachments/{attachment_id}/content", response_model=None)
async def get_attachment_content(
    attachment_id: str,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> FileResponse | RedirectResponse:
    """Retrieve raw attachment content for preview or download."""
    attachment = await db.get(AttachmentDB, attachment_id)
    if attachment is None or attachment.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    storage_path = attachment.storage_path
    if storage_path.startswith("http://") or storage_path.startswith("https://"):
        return RedirectResponse(storage_path)

    file_path = Path(storage_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file not found",
        )

    mime_type = resolve_content_type(attachment.filename, attachment.mime_type)
    headers = {"Content-Disposition": f'inline; filename="{attachment.filename}"'}
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=attachment.filename,
        headers=headers,
    )


@router.delete(
    "/api/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_attachment(
    attachment_id: str,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user),
) -> None:
    """Delete an attachment and its stored file."""
    attachment = await db.get(AttachmentDB, attachment_id)
    if attachment is None or attachment.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    storage_path = attachment.storage_path
    await db.delete(attachment)
    await db.commit()

    if storage_path.startswith("http://") or storage_path.startswith("https://"):
        return

    file_path = Path(storage_path)
    if file_path.exists():
        file_path.unlink()
    logger.info("Deleted attachment %s for user %s", attachment_id, user_id)
