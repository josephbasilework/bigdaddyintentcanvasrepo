"""SQLAlchemy models for intent indexing and attachments."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeMeta

Base: "DeclarativeMeta" = declarative_base()  # type: ignore[assignment]


class UserIntent(Base):
    """User intent with embedding for similarity search.

    Stores user intents with their vector embeddings for semantic search
    and intent matching.
    """

    __tablename__ = "user_intents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    intent_text = Column(String, nullable=False)
    intent_type = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    # Note: embedding column uses pgvector type, defined as String here for compatibility
    # In production, would use: Column(Vector(1536))
    embedding = Column(String, nullable=True)
    context = Column(JSON, default={}, nullable=False)
    handler = Column(String, nullable=True)
    executed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "intent_text": self.intent_text,
            "intent_type": self.intent_type,
            "confidence": self.confidence,
            "context": self.context,
            "handler": self.handler,
            "executed": self.executed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AttachmentDB(Base):
    """Database model for file attachments."""

    __tablename__ = "attachments"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    attachment_type = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    text_content = Column(Text, nullable=True)
    transcription = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending", nullable=False)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    context_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "attachment_type": self.attachment_type,
            "storage_path": self.storage_path,
            "text_content": self.text_content,
            "transcription": self.transcription,
            "description": self.description,
            "status": self.status,
            "error_message": self.error_message,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "context_id": self.context_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AssumptionResolutionDB(Base):
    """Database model for assumption resolutions."""

    __tablename__ = "assumption_resolutions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    assumption_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)  # accept, reject, edit
    original_text = Column(Text, nullable=False)
    final_text = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "assumption_id": self.assumption_id,
            "action": self.action,
            "original_text": self.original_text,
            "final_text": self.final_text,
            "category": self.category,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
