"""Gemini embeddings provider (REST). Corpus-independent, so results are cached in
SQLite to avoid re-embedding identical text across runs."""
from __future__ import annotations

import hashlib

import httpx
import numpy as np

from ..config import settings
from ..db import get_cached_vector, set_cached_vector
from .embeddings import EmbeddingProvider, _l2

_MODEL = "text-embedding-004"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:embedContent"


class GeminiEmbedder(EmbeddingProvider):
    name = "gemini"

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set")

    def _one(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).hexdigest()
        cached = get_cached_vector(self.name, h)
        if cached is not None:
            return cached
        payload = {"model": f"models/{_MODEL}",
                   "content": {"parts": [{"text": text or " "}]}}
        r = httpx.post(_URL, params={"key": settings.gemini_api_key},
                       json=payload, timeout=60)
        r.raise_for_status()
        vec = r.json()["embedding"]["values"]
        set_cached_vector(self.name, h, vec)
        return vec

    def embed(self, texts: list[str]) -> np.ndarray:
        return _l2(np.array([self._one(t) for t in texts]))
