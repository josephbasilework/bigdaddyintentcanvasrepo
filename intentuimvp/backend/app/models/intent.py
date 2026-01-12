"""SQLAlchemy models for intent indexing and attachments."""

import enum
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.ext.declarative import declarative_base


class IntentOutcome(str, enum.Enum):
    """Outcome status for user intents per PRD §15.2.

    Tracks whether the intent execution was successful, failed, or modified.
    Used for learning from past interactions and pruning failed entries.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    MODIFIED = "modified"

# Check if pgvector is available (for PostgreSQL vector embeddings)
try:
    import importlib.util

    _HAS_PGVECTOR = importlib.util.find_spec("pgvector") is not None
except Exception:
    _HAS_PGVECTOR = False

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeMeta

Base: "DeclarativeMeta" = declarative_base()  # type: ignore[assignment]

# Embedding dimension for all-MiniLM-L6-v2 model
EMBEDDING_DIM = 384


def _get_embedding_column_type():  # type: ignore[no-untyped-def]
    """Get the appropriate column type for embeddings based on database.

    Returns Vector(384) for PostgreSQL with pgvector, String for SQLite.
    """
    if _HAS_PGVECTOR and _is_postgresql():
        from pgvector.sqlalchemy import Vector

        return Vector(EMBEDDING_DIM)
    return String


def _get_resolution_column_type():  # type: ignore[no-untyped-def]
    """Get the appropriate column type for resolutions based on database."""
    if _is_postgresql():
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB
    return JSON


def _is_postgresql() -> bool:
    """Check if the current database is PostgreSQL."""
    database_url = os.getenv("DATABASE_URL", "")
    return database_url.startswith("postgresql://") or database_url.startswith("postgresql+asyncpg://")


class UserIntent(Base):
    """User intent with embedding for similarity search.

    Stores user intents with their vector embeddings for semantic search
    and intent matching. Implements PRD §15.2 Intent Index schema.

    Uses pgvector Vector(384) type for PostgreSQL, falls back to String for SQLite.
    Embeddings are generated using sentence-transformers/all-MiniLM-L6-v2 model.

    Schema per PRD §15.2:
    - id: Primary key (auto-increment integer, maps to UUID semantically)
    - user_id: User identifier (foreign key reference)
    - intent_text: Original user input text
    - embedding: VECTOR(384) for semantic similarity search
    - resolution: JSONB containing approved assumptions and actions taken
    - outcome: ENUM('success', 'failure', 'modified') for learning/pruning
    - created_at: Timestamp for recency weighting (decay: 0.99^days_old)
    """

    __tablename__ = "user_intents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    intent_text = Column(String, nullable=False)
    intent_type = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    # Vector(384) for PostgreSQL with pgvector, String for SQLite
    # Dimension 384 matches the all-MiniLM-L6-v2 sentence transformer model
    embedding = Column(_get_embedding_column_type(), nullable=True)
    context = Column(JSON, default=dict, nullable=False)
    handler = Column(String, nullable=True)
    executed = Column(Boolean, default=False, nullable=False)
    # PRD §15.2: resolution stores approved assumptions and actions taken
    resolution = Column(_get_resolution_column_type(), default=None, nullable=True)
    # PRD §15.2: outcome tracks success/failure/modified for learning
    outcome = Column(SQLEnum(IntentOutcome, name="intent_outcome"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        created_at = cast(datetime | None, self.created_at)
        outcome = self.outcome
        if isinstance(outcome, enum.Enum):
            outcome = outcome.value
        return {
            "id": self.id,
            "user_id": self.user_id,
            "intent_text": self.intent_text,
            "intent_type": self.intent_type,
            "confidence": self.confidence,
            "context": self.context,
            "handler": self.handler,
            "executed": self.executed,
            "resolution": self.resolution,
            "outcome": outcome,
            "created_at": created_at.isoformat() if created_at else None,
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
        processed_at = cast(datetime | None, self.processed_at)
        created_at = cast(datetime | None, self.created_at)
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
            "processed_at": processed_at.isoformat() if processed_at else None,
            "context_id": self.context_id,
            "created_at": created_at.isoformat() if created_at else None,
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
        created_at = cast(datetime | None, self.created_at)
        return {
            "id": self.id,
            "session_id": self.session_id,
            "assumption_id": self.assumption_id,
            "action": self.action,
            "original_text": self.original_text,
            "final_text": self.final_text,
            "category": self.category,
            "created_at": created_at.isoformat() if created_at else None,
        }
