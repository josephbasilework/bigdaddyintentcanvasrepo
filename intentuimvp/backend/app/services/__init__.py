"""Services module for IntentUI backend."""

from __future__ import annotations

from typing import Any

_EMBEDDING_EXPORTS = {
    "EMBEDDING_DIM",
    "EmbeddingService",
    "create_embedding_provider",
    "encode_text",
    "encode_texts",
    "get_embedding_service",
}


def __getattr__(name: str) -> Any:
    if name in _EMBEDDING_EXPORTS:
        from app.services import embedding as _embedding

        return getattr(_embedding, name)
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = sorted(_EMBEDDING_EXPORTS)
