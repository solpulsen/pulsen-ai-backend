"""Embedding Provider — LOCKED to text-embedding-3-small (1536 dims).

FROZEN ARCHITECTURE: Do not change model or dimensions without migration + full reindex.
Matches VECTOR(1536) and HNSW cosine index in knowledge_chunks.

Usage:
    from knowledge_engine.core.embeddings import get_embedder
    embedder = get_embedder()
    vectors = await embedder.embed(["text1", "text2"])
    dim = embedder.vector_dimension
    name = embedder.model_name
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import List

from knowledge_engine.core.config import EMBEDDING_MODEL, EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @property
    @abstractmethod
    def vector_dimension(self) -> int:
        ...

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts. Returns normalized float vectors."""
        ...

    @abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query. Returns a single normalized float vector."""
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embedding using text-embedding-3-small.
    1536 dimensions. Requires OPENAI_API_KEY.
    Matches VECTOR(1536) and HNSW cosine index in knowledge_chunks.
    """

    MODEL_ID = EMBEDDING_MODEL
    DIMENSION = EMBEDDING_DIMENSIONS

    def __init__(self):
        from openai import AsyncOpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required for OpenAI embedding provider. "
                "Set it in backend runtime secrets."
            )
        # Use original OpenAI API directly — not proxy
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
        )

    @property
    def model_name(self) -> str:
        return self.MODEL_ID

    @property
    def vector_dimension(self) -> int:
        return self.DIMENSION

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed document passages via OpenAI API."""
        response = await self._client.embeddings.create(
            model=self.MODEL_ID,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single query via OpenAI API."""
        response = await self._client.embeddings.create(
            model=self.MODEL_ID,
            input=[query],
        )
        return response.data[0].embedding


# ─── Singleton ────────────────────────────────────────────────────────────────

_embedder: EmbeddingProvider | None = None


def get_embedder() -> EmbeddingProvider:
    """
    Get the configured embedding provider (singleton).
    Locked: OpenAI text-embedding-3-small (1536 dims). No alternatives.
    """
    global _embedder
    if _embedder is None:
        provider = os.environ.get("EMBEDDING_PROVIDER", "openai").lower()
        if provider == "openai":
            logger.info("Initializing OpenAI embedding provider (text-embedding-3-small, 1536 dims)")
            _embedder = OpenAIEmbeddingProvider()
        else:
            raise ValueError(
                f"Unknown EMBEDDING_PROVIDER: '{provider}'. "
                f"v1 supports: 'openai'."
            )
    return _embedder
