"""SQLAlchemy model for audio_block table.

Audio blocks represent voice recordings on a canvas with optional
transcription. They can be created via the frontend AudioCapture
component and stored via the backend API.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.canvas import Canvas


class AudioBlockStatus(str, Enum):
    """Status of audio block processing."""

    PENDING = "pending"
    READY = "ready"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    ERROR = "error"


class AudioBlock(Base):
    """Audio block model for storing voice recordings and transcriptions."""

    __tablename__ = "audio_block"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canvas_id: Mapped[int] = mapped_column(
        ForeignKey("canvas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Storage reference (path or URL where the audio file is stored)
    audio_uri: Mapped[str] = mapped_column(String, nullable=False)
    # Transcribed text content (populated after transcription job completes)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Duration of the audio recording in seconds
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Processing status
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=AudioBlockStatus.PENDING
    )
    # Error message if processing failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    canvas: Mapped[Canvas] = relationship("Canvas", back_populates="audio_blocks")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "canvasId": self.canvas_id,
            "audioUri": self.audio_uri,
            "transcription": self.transcription,
            "duration": self.duration,
            "status": self.status,
            "errorMessage": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
