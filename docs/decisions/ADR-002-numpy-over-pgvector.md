# ADR-002: numpy brute-force cosine instead of a vector database

**Status:** Accepted

## Context
`CLAUDE.md` suggests pgvector or a vector DB for semantic retrieval.

## Decision
Store no dedicated vector index. Build a small in-memory embedding matrix per candidate
and compute cosine similarity with numpy (`retrieval.RetrievalIndex`).

## Rationale
- One candidate's knowledge base is ~20–80 short entities. Brute-force cosine over an
  L2-normalised `(n, d)` matrix is **exact** and effectively instant.
- A vector DB (pgvector/FAISS/Chroma) adds infrastructure and an ANN approximation to
  solve a problem we do not have at this scale — textbook over-engineering.

## Consequences
- Retrieval is rebuilt per request. Fine now; if the KB grows to thousands of entities or
  becomes multi-tenant, introduce a persistent ANN index behind the same
  `RetrievalIndex`/`EmbeddingProvider` seam.
