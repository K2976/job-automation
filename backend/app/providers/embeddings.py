"""Embedding provider abstraction (CLAUDE.md §11). Default is an offline TF-IDF embedder
(no torch) so vector retrieval never depends on paid inference during development
(ADR-004). Gemini embeddings are opt-in. Heavier local semantic models
(sentence-transformers) can be added behind this same interface later."""
from __future__ import annotations

import math
from abc import ABC, abstractmethod

import numpy as np

from ..config import settings
from ..text_utils import content_tokens


class EmbeddingProvider(ABC):
    name = "base"

    def fit(self, corpus: list[str]) -> None:
        """Optional corpus fit (TF-IDF needs it; contextless providers no-op)."""

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n_texts, dim) float array. Rows should be L2-normalised."""


def _l2(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class LocalTfidfEmbedder(EmbeddingProvider):
    """Corpus-fit TF-IDF vectors. Exact, instant at KB scale, fully deterministic."""
    name = "local"

    def __init__(self) -> None:
        self._vocab: dict[str, int] = {}
        self._idf: np.ndarray | None = None

    def fit(self, corpus: list[str]) -> None:
        vocab: dict[str, int] = {}
        doc_tokensets = []
        for text in corpus:
            toks = content_tokens(text)
            doc_tokensets.append(set(toks))
            for t in toks:
                vocab.setdefault(t, len(vocab))
        n = max(len(corpus), 1)
        df = np.zeros(len(vocab))
        for tokset in doc_tokensets:
            for t in tokset:
                df[vocab[t]] += 1
        self._vocab = vocab
        self._idf = np.array([math.log((1 + n) / (1 + d)) + 1.0 for d in df])

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._idf is None:
            self.fit(texts)
        dim = len(self._vocab)
        mat = np.zeros((len(texts), dim))
        for i, text in enumerate(texts):
            for t in content_tokens(text):
                j = self._vocab.get(t)
                if j is not None:
                    mat[i, j] += 1.0
        if dim:
            mat *= self._idf
        return _l2(mat)


def get_embedding_provider(name: str | None = None) -> EmbeddingProvider:
    provider = (name or settings.embedding_provider or "local").lower()
    if provider == "local":
        return LocalTfidfEmbedder()
    if provider == "gemini":
        from .gemini_embeddings import GeminiEmbedder
        return GeminiEmbedder()
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {provider!r} (expected local|gemini)")
