# ADR-004: Local TF-IDF embeddings as the default

**Status:** Accepted

## Context
Embedding retrieval and LLM generation are separate concerns. Development should not
depend on paid inference, and the default install should stay light (no torch).

## Decision
`EmbeddingProvider` (`providers/embeddings.py`) with:

- **`LocalTfidfEmbedder`** (default): corpus-fit TF-IDF vectors, numpy, deterministic,
  offline. Exact and instant at KB scale.
- **`GeminiEmbedder`**: `text-embedding-004` over REST, results cached in SQLite.

Selected by `EMBEDDING_PROVIDER`.

## Rationale
- Keeps `pip install` light and tests fast/deterministic.
- Combined with keyword overlap in hybrid retrieval, TF-IDF is a believable dev-time
  semantic signal without a heavyweight model.

## Consequences
- TF-IDF is lexical, not truly semantic (won't bridge unrelated synonyms). For higher
  retrieval quality, switch to `gemini`, or add a `sentence-transformers` implementation
  behind the same interface (noted as opt-in in `requirements.txt`).
- TF-IDF is corpus-dependent, so the index fits on the current corpus each build; Gemini
  vectors are corpus-independent and cached.
