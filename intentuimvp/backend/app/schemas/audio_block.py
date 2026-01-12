"""Pydantic schemas for audio block API."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.audio_block import AudioBlockStatus


class AudioBlockCreateRequest(BaseModel):
    """Request body for creating an audio block."""

    canvas_id: int = Field(..., description="Canvas identifier")
    # Audio data can be provided either as:
    # 1. Base64-encoded audio data (for small recordings)
    # 2. A reference to already-stored audio (for larger files)
    audio_data: str | None = Field(
        default=None,
        description="Base64-encoded audio data (for direct upload)",
    )
    audio_uri: str | None = Field(
        default=None,
        description="URI/path to already-stored audio file",
    )
    duration: float | None = Field(
        default=None, description="Duration of audio in seconds"
    )


class AudioBlockUpdateRequest(BaseModel):
    """Request body for updating an audio block."""

    transcription: str | None = Field(
        default=None, description="Transcribed text content"
    )
    status: AudioBlockStatus | None = Field(
        default=None, description="Processing status"
    )
    error_message: str | None = Field(default=None, description="Error message if failed")


class AudioBlockResponse(BaseModel):
    """Response model for audio block data."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    canvasId: int  # noqa: N815 - camelCase for API compatibility
    audioUri: str  # noqa: N815 - camelCase for API compatibility
    transcription: str | None
    duration: float | None
    status: str
    errorMessage: str | None  # noqa: N815 - camelCase for API compatibility
    created_at: str
    updated_at: str


class AudioBlockListResponse(BaseModel):
    """Response model for listing audio blocks."""

    audio_blocks: list[AudioBlockResponse]
    count: int


class AudioUploadResponse(BaseModel):
    """Response model for audio file upload."""

    audio_uri: str = Field(..., description="URI/path where audio was stored")
    size_bytes: int = Field(..., description="Size of the uploaded audio file")
    mime_type: str = Field(..., description="MIME type of the audio file")
