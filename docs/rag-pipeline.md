# RAG pipeline

We deliberately do **not** build `JD → LLM → résumé`. The LLM reasons over retrieved,
provenance-tagged evidence.

## Ingestion → KB → index
```
resume (pdf/docx/txt) ─► ingestion.extract_text ─► llm.parse_resume ─► MasterProfile
MasterProfile ─► kb.seed_profile ─► KBEntity rows (status=ORIGINAL)
KBEntity.content ─► EmbeddingProvider.fit+embed ─► RetrievalIndex.matrix
```
The candidate reviews the parsed `MasterProfile` before it is persisted (`/api/ingest`
returns it; `/api/candidates` persists it).

## Hybrid retrieval (`retrieval.py`)
For a query (a JD requirement, or a role+skills query for project ranking):

```
             ┌─ semantic: cosine(query, entity)   (L2-normalised embeddings, exact)
score = w_s ·┤
             └─ keyword:  token overlap (text_utils.keyword_overlap)
      + w_k · keyword
      filtered by structured metadata (entity_type, status)
      ─► sort desc ─► top_k
```
Weights: `SEMANTIC_WEIGHT` (0.6), `KEYWORD_WEIGHT` (0.4), `RETRIEVAL_TOP_K` (8). Only
`SUPPORTED_STATUSES` entities are retrieved as evidence.

Why brute force: the KB is tiny — see [ADR-002](decisions/ADR-002-numpy-over-pgvector.md).

## Reranking
The fused score *is* the rerank signal (semantic + keyword combined), then a plain sort.
A cross-encoder reranker can slot in after `search` if needed.

## Context assembly for generation
Generation receives only what it needs (CLAUDE.md §20): candidate identity, JD
requirements, ranked relevant projects, approved rewrites, confirmed skills, emphasis
order — not the entire KB. See [resume-generation.md](resume-generation.md).

## Evaluation
`data/fixtures/` (one master profile + two JDs) doubles as the eval set.
`tests/test_pipeline_e2e.py` asserts expected strong matches, expected gaps, and role
positioning (e.g. Setu AI ranks top-2 for AI Engineer; PortfolioKit ranks last for Data
Engineer).
