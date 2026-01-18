"""Attachment ingestion helpers."""

from __future__ import annotations

import io
import logging
import mimetypes
import uuid
from dataclasses import dataclass
from datetime import datetime

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactType, JobArtifact
from app.models.attachment import (
    AttachmentStatus,
    AttachmentType,
    determine_attachment_type,
    get_attachment_storage,
)
from app.models.intent import AttachmentDB
from app.services.user_data_store import get_user_data_store

logger = logging.getLogger(__name__)

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_TEXT_CONTENT_CHARS = 8000
TEXT_PREVIEW_CHARS = 240
DESCRIPTION_PREVIEW_CHARS = 160

ALLOWED_TYPES = {
    AttachmentType.IMAGE,
    AttachmentType.AUDIO,
    AttachmentType.VIDEO,
    AttachmentType.DOCUMENT,
    AttachmentType.CODE,
}


@dataclass(frozen=True)
class AttachmentSummary:
    """Compact preview for attachment UI."""

    text_preview: str | None = None
    description_preview: str | None = None


def resolve_content_type(filename: str, content_type: str | None) -> str:
    """Resolve the best MIME type for an attachment."""
    if content_type and content_type != "application/octet-stream":
        return content_type
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _clip_text(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: max(0, limit - 3)].rstrip()}..."


def summarize_attachment(attachment: AttachmentDB) -> AttachmentSummary:
    """Build preview snippets from attachment content."""
    return AttachmentSummary(
        text_preview=_clip_text(attachment.text_content, TEXT_PREVIEW_CHARS),
        description_preview=_clip_text(attachment.description, DESCRIPTION_PREVIEW_CHARS),
    )


def _is_text_like(
    attachment_type: AttachmentType, filename: str, mime_type: str
) -> bool:
    if attachment_type in {AttachmentType.DOCUMENT, AttachmentType.CODE}:
        return True
    if mime_type.startswith("text/"):
        return True
    return filename.lower().endswith((".txt", ".md", ".csv", ".json", ".yaml", ".yml"))


def _is_pdf(filename: str, mime_type: str) -> bool:
    return mime_type == "application/pdf" or filename.lower().endswith(".pdf")


def _extract_text_from_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PDF extraction requires pypdf") from exc

    reader = PdfReader(io.BytesIO(content))
    pieces: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        if extracted:
            pieces.append(extracted)
        if sum(len(piece) for piece in pieces) >= MAX_TEXT_CONTENT_CHARS:
            break
    return "\n".join(pieces)


def _extract_image_description(content: bytes) -> str | None:
    try:
        from PIL import Image
    except Exception:  # pragma: no cover - optional dependency
        return None

    try:
        with Image.open(io.BytesIO(content)) as image:
            return f"Image {image.width}x{image.height}"
    except Exception:
        return None


def _extract_text_content(
    attachment_type: AttachmentType, filename: str, mime_type: str, content: bytes
) -> str | None:
    if not _is_text_like(attachment_type, filename, mime_type):
        return None
    if _is_pdf(filename, mime_type):
        return _extract_text_from_pdf(content)
    return content.decode("utf-8", errors="replace")


async def ingest_attachment(
    db: AsyncSession,
    upload: UploadFile,
    *,
    user_id: str,
    session_id: str | None = None,
    turn_id: int | None = None,
    node_id: int | None = None,
    workspace_id: str | None = None,
) -> AttachmentDB:
    """Store an uploaded attachment and extract metadata."""
    filename = upload.filename or "attachment"
    content = await upload.read()
    await upload.close()

    if not content:
        raise ValueError("Attachment is empty")
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise ValueError(f"Attachment exceeds {MAX_ATTACHMENT_BYTES} bytes")

    mime_type = resolve_content_type(filename, upload.content_type)
    attachment_type = determine_attachment_type(filename, mime_type)
    if attachment_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported attachment type for {filename}")

    attachment_id = str(uuid.uuid4())
    storage = get_attachment_storage()
    storage_path = await storage.store(
        user_id=user_id,
        attachment_id=attachment_id,
        filename=filename,
        content=content,
        mime_type=mime_type,
    )

    artifact = JobArtifact(
        job_id=f"attachment:{attachment_id}",
        user_id=user_id,
        workspace_id=workspace_id,
        artifact_type=ArtifactType.ATTACHMENT.value,
        artifact_name=filename,
        description=None,
        filename=filename,
        mime_type=mime_type,
        size_bytes=len(content),
        storage_path=storage_path,
        inline_data=None,
        archive_after_days=None,
        origin_turn_id=turn_id,
    )
    db.add(artifact)
    await db.flush()

    attachment = AttachmentDB(
        id=attachment_id,
        user_id=user_id,
        filename=filename,
        mime_type=mime_type,
        size_bytes=len(content),
        attachment_type=attachment_type.value,
        storage_path=storage_path,
        status=AttachmentStatus.PROCESSING.value,
        context_id=session_id,
        session_id=session_id,
        turn_id=turn_id,
        node_id=node_id,
        artifact_id=artifact.id,
    )

    try:
        text_content = _extract_text_content(
            attachment_type, filename, mime_type, content
        )
        description = (
            _extract_image_description(content)
            if attachment_type == AttachmentType.IMAGE
            else None
        )
        attachment.text_content = _clip_text(text_content, MAX_TEXT_CONTENT_CHARS)
        attachment.description = description
        attachment.status = AttachmentStatus.READY.value
        attachment.processed_at = datetime.utcnow()
    except Exception as exc:
        logger.warning("Attachment processing failed", exc_info=True)
        attachment.status = AttachmentStatus.ERROR.value
        attachment.error_message = str(exc)
        attachment.processed_at = datetime.utcnow()

    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    try:
        data_store = get_user_data_store()
        data_store.persist_artifact(artifact=artifact.to_dict())
    except Exception:
        logger.warning("Failed to persist attachment artifact", exc_info=True)

    return attachment
