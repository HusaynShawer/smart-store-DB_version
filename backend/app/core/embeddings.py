# app/core/embeddings.py
"""
Embedding integration with automatic provider fallback.

Strategy ("auto"):
  1. Cohere multilingual (`embed-multilingual-v3.0`, 1024d) when `COHERE_API_KEY` is set.
  2. SovereignEG OpenAI-compatible `/v1/embeddings` (`text-embedding-3-small`, 1536d)
     otherwise — zero extra config, reuses SOVEREIGNEG_API_KEY.

The rest of the app depends on the `EmbeddingService` interface, never on a vendor.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Literal

import cohere
import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmbeddingService(ABC):
    """Interface for text embedding providers."""

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents (stored content)."""

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query."""


def _normalise(vector: list[float]) -> list[float]:
    """L2-normalise so cosine distance == plain vector distance in pgvector."""
    norm = (sum(x * x for x in vector) or 0.0) ** 0.5
    if not norm:
        return vector
    return [x / norm for x in vector]


class CohereEmbeddingService(EmbeddingService):
    """Cohere `embed-multilingual-v3.0` implementation (multilingual, 1024d)."""

    def __init__(self) -> None:
        self._client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, input_type="search_document")

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self._embed([text], input_type="search_query")
        return vectors[0] if vectors else []

    async def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        response = await asyncio.to_thread(
            self._client.embed,
            texts=texts,
            model=settings.COHERE_MODEL,
            input_type=input_type,
            embedding_types=["float"],
        )
        if response.embeddings and response.embeddings.float_ is not None:
            return [list(v) for v in response.embeddings.float_]
        logger.warning("Cohere returned no float embeddings (class: %s)", type(response.embeddings))
        return []


class SovereignEGEmbeddingService(EmbeddingService):
    """OpenAI-compatible `/v1/embeddings` via SovereignEG (text-embedding-3-small, 1536d).

    Used as the automatic fallback when no Cohere key is configured.
    """

    def __init__(self) -> None:
        self._base_url = settings.LLM_BASE_URL.rstrip("/")
        self._api_key = settings.SOVEREIGNEG_API_KEY
        self._model = settings.EMBEDDING_MODEL
        self._timeout = 60.0
        self._batch = 32

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch):
            chunk = texts[start : start + self._batch]
            vectors.extend(await self._embed(chunk))
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self._embed([text])
        return vectors[0] if vectors else []

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self._model, "input": texts}
        headers = {
            "Authorization": f"Bearer {self._api_key or 'EMPTY_API_KEY'}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/embeddings", headers=headers, json=payload
                )
        except httpx.HTTPError as exc:
            logger.warning("SovereignEG embeddings request failed: %s", exc)
            return []
        if response.status_code != 200:
            logger.warning(
                "SovereignEG embeddings HTTP %s: %s", response.status_code, response.text[:200]
            )
            return []
        data = response.json()
        try:
            items = sorted(data["data"], key=lambda item: item.get("index", 0))
            return [_normalise(item["embedding"]) for item in items]
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Unexpected embeddings response: %s", exc)
            return []


def _select_provider() -> Literal["cohere", "sovereign"]:
    forced = settings.EMBEDDING_PROVIDER
    if forced in ("cohere", "sovereign"):
        return forced
    return "cohere" if settings.COHERE_API_KEY else "sovereign"


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Cached singleton with automatic fallback between Cohere and SovereignEG."""
    provider = _select_provider()
    logger.info("Embedding provider: %s", provider)
    if provider == "cohere":
        return CohereEmbeddingService()
    return SovereignEGEmbeddingService()