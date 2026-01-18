"""Pydantic schemas for attachment API."""

from pydantic import BaseModel, ConfigDict, Field


class AttachmentResponse(BaseModel):
    """Response model for attachment metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    mime_type: str
    size_bytes: int
    attachment_type: str
    status: str
    text_preview: str | None = None
    description_preview: str | None = None
    error_message: str | None = None
    created_at: str
    processed_at: str | None = None
    session_id: str | None = None
    turn_id: int | None = None
    node_id: int | None = None
    artifact_id: int | None = None
    content_url: str = Field(..., description="URL for retrieving attachment content")
    preview_url: str | None = Field(
        default=None, description="URL for previewing the attachment"
    )


class AttachmentListResponse(BaseModel):
    """Response model for a list of attachments."""

    attachments: list[AttachmentResponse]
    count: int
    max_bytes: int
