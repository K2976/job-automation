# Roadmap

## V1 — Adaptive résumé intelligence (this release)
`resume + JD → RAG → gap analysis → human approval → tailored résumé → validation`.
Implemented and tested end-to-end offline. Real Gemini/Groq providers wired (need keys).

Done: ingestion · KB · embeddings/hybrid retrieval · JD analysis · evidence matching · gap
analysis · modification plan · approval workflow · generation · claim validation ·
JD-alignment analysis · explainability · comparison · tests · docs · clean git history.

### Natural V1.x extensions (same architecture, no contamination)
- Named, reusable **Role Profiles** persisted over the KB (currently realised per Job).
- HTML/PDF/DOCX export of the tailored résumé (the model is format-agnostic).
- Postgres + pgvector when multi-user/scale warrants it (swap `db.py`, [ADR-001]/[ADR-002]).
- `sentence-transformers` embedding provider for stronger local semantics ([ADR-004]).

## V2 — Job discovery (not built)
`candidate profile → find relevant jobs → analyze JDs → rank jobs`. Designed to attach as a
new source feeding the existing JD analyzer; **not** part of V1.

## V3 — Application assistance (not built)
`job → tailored résumé → cover letter → application-form assistance → human review →
submission`. Retains human confirmation before any submission. **Not** part of V1.

Job search/scraping and application automation are intentionally excluded from V1
(CLAUDE.md §25, §41). Interfaces are kept extensible so these can be added later without
reworking the core.

[ADR-001]: decisions/ADR-001-sqlite-over-postgres.md
[ADR-002]: decisions/ADR-002-numpy-over-pgvector.md
[ADR-004]: decisions/ADR-004-local-embedding-default.md
