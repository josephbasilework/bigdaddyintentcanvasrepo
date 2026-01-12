"""Services module for IntentUI backend.

This module contains business logic services that provide specific functionality
to the application layer.
"""

from app.services.embedding import (
    EMBEDDING_DIM,
    EmbeddingService,
    create_embedding_provider,
    encode_text,
    encode_texts,
    get_embedding_service,
)

__all__ = [
    "EMBEDDING_DIM",
    "EmbeddingService",
    "create_embedding_provider",
    "encode_text",
    "encode_texts",
    "get_embedding_service",
]
