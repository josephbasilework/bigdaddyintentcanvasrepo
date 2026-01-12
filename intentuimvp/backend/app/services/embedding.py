"""Embedding service for generating text embeddings using sentence-transformers.

This module provides text embedding generation using the all-MiniLM-L6-v2 model,
which produces 384-dimensional vectors optimized for semantic similarity tasks.

Per PRD §15.2 (F7.2: Intent Index):
- Model: sentence-transformers/all-MiniLM-L6-v2
- Dimensions: 384
- Use case: Intent similarity search with cosine similarity threshold > 0.7
"""
from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.models.intent import EMBEDDING_DIM

logger = logging.getLogger(__name__)

# Default model name from sentence-transformers library
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Environment variable to override the model
_MODEL_ENV_VAR = "INTENTUI_EMBEDDING_MODEL"


class EmbeddingService:
    """Service for generating text embeddings using sentence-transformers.

    This service lazily loads the sentence transformer model on first use
    to avoid startup overhead when embeddings aren't needed.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """Initialize the embedding service.

        Args:
            model_name: Name of the sentence-transformers model to use.
                Defaults to "sentence-transformers/all-MiniLM-L6-v2".
                Can be overridden via INTENTUI_EMBEDDING_MODEL env var.
        """
        self._model_name = model_name or os.getenv(_MODEL_ENV_VAR, DEFAULT_MODEL_NAME)
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        """Get or lazily load the sentence transformer model.

        Returns:
            The loaded SentenceTransformer model.

        Raises:
            RuntimeError: If the model fails to load.
        """
        if self._model is None:
            try:
                logger.info("Loading sentence transformer model: %s", self._model_name)
                self._model = SentenceTransformer(self._model_name)
                logger.info("Successfully loaded sentence transformer model")
            except Exception as e:
                logger.error("Failed to load sentence transformer model: %s", e)
                raise RuntimeError(f"Failed to load embedding model '{self._model_name}': {e}") from e
        return self._model

    def encode(self, text: str) -> list[float]:
        """Generate embedding for a single text string.

        Args:
            text: The input text to encode.

        Returns:
            A list of floats representing the text embedding.
            Dimension is 384 for all-MiniLM-L6-v2.

        Raises:
            RuntimeError: If the model fails to load or encode.
        """
        if not text or not text.strip():
            raise ValueError("Cannot encode empty or whitespace-only text")

        try:
            # Returns numpy array of shape (1, EMBEDDING_DIM)
            embedding = self.model.encode(text, convert_to_numpy=True)
            # Convert to list of floats for database storage
            return embedding.tolist()
        except Exception as e:
            logger.error("Failed to encode text: %s", e)
            raise RuntimeError(f"Failed to encode text: {e}") from e

    def encode_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Generate embeddings for multiple text strings.

        Batch encoding is more efficient than individual encode calls
        when processing multiple texts.

        Args:
            texts: Sequence of input texts to encode.

        Returns:
            A list of embedding lists, one per input text.

        Raises:
            RuntimeError: If the model fails to load or encode.
        """
        if not texts:
            return []

        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            raise ValueError("Cannot encode empty sequence or all-whitespace texts")

        try:
            embeddings = self.model.encode(valid_texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error("Failed to encode batch of %d texts: %s", len(texts), e)
            raise RuntimeError(f"Failed to encode batch: {e}") from e

    @property
    def embedding_dim(self) -> int:
        """Get the embedding dimension of the model."""
        return EMBEDDING_DIM


# Global singleton instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service(model_name: str | None = None) -> EmbeddingService:
    """Get the singleton embedding service instance.

    Args:
        model_name: Optional model name override. Only used on first call.

    Returns:
        The singleton EmbeddingService instance.
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(model_name=model_name)
    return _embedding_service


@lru_cache(maxsize=1)
def _get_cached_embedding_service() -> EmbeddingService:
    """Cached accessor for the embedding service.

    Uses LRU cache to ensure the same instance is returned across calls.
    """
    return get_embedding_service()


def encode_text(text: str) -> list[float] | None:
    """Convenience function to encode text using the singleton service.

    Returns None on error instead of raising, for easier integration
    with error-handling code.

    Args:
        text: The input text to encode.

    Returns:
        A list of floats representing the embedding, or None on failure.
    """
    try:
        service = get_embedding_service()
        return service.encode(text)
    except Exception as e:
        logger.warning("Failed to encode text (returning None): %s", e)
        return None


def encode_texts(texts: Sequence[str]) -> list[list[float]] | None:
    """Convenience function to encode multiple texts.

    Returns None on error instead of raising.

    Args:
        texts: Sequence of input texts to encode.

    Returns:
        A list of embedding lists, or None on failure.
    """
    try:
        service = get_embedding_service()
        return service.encode_batch(texts)
    except Exception as e:
        logger.warning("Failed to encode texts (returning None): %s", e)
        return None


# Create an embedding provider function compatible with IntentIndexLookup
def create_embedding_provider():
    """Create an embedding provider for use with IntentIndexLookup.

    The returned function has the signature EmbeddingProvider from
    app/agents/intent_index.py.

    Returns:
        A callable that takes text and returns an embedding sequence or None.
    """
    def provider(text: str) -> Sequence[float] | None:
        return encode_text(text)

    return provider
