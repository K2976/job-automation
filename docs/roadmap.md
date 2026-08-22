# Roadmap

## V1 — Adaptive résumé intelligence (this release)
`resume + JD → RAG → gap analysis → human approval → tailored résumé → validation`.
Implemented and tested end-to-end offline, with a full React frontend and live providers.

Done: ingestion · KB (with inline editing) · embeddings/hybrid retrieval · JD analysis ·
evidence matching · gap analysis · modification plan · approval workflow · generation ·
claim validation · JD-alignment analysis · explainability · comparison · PDF/HTML/Markdown
export · named role-view snapshots · live Gemini/Groq providers (retry/timeout/auth
hardening) · React frontend · tests · docs · clean git history.

### Natural V1.x extensions (same architecture, no contamination)
- Persistent résumé history / multiple saved generations per role view.
- DOCX export (the export renderer is format-agnostic over the structured model).
- Postgres + pgvector when multi-user/scale warrants it (swap `db.py`, [ADR-001]/[ADR-002]).
- `sentence-transformers` embedding provider for stronger local semantics ([ADR-004]).
- Generate the TS API types from `/openapi.json` instead of hand-maintaining ([ADR-005]).

## V2 — Opportunity intelligence (this release)
`candidate profile → discover opportunities → analyze JDs (V1 RAG) → rank → prepare packages`.
Attaches to V1 exactly as designed: discovered opportunities feed the existing JD analyzer
and matching, and application packages reuse the existing résumé pipeline. V1 is untouched.

Done: source adapter architecture (offline fixtures + Greenhouse/Lever public APIs) ·
error/CAPTCHA isolation with source health · normalization · deduplication · cheap
LLM-free filtering + matching · deep analysis via `match_jd` (one `analyze_jd` call per
survivor, no rewrite step) · deterministic ranking · why-apply explanation · search
preferences · application batches with a hard max-selection invariant · package prep
(tailored résumé + grounded cover letter) · opportunity tracker · background discovery
runs with polled, real-count progress · Opportunities frontend · tests · docs.

See [opportunity-intelligence.md](opportunity-intelligence.md),
[opportunity-sources.md](opportunity-sources.md), [application-batches.md](application-batches.md).

**Not** in V2 (deferred to V3): browser automation, form filling, automatic submission,
CAPTCHA solving/bypass. A blocked/CAPTCHA/unreachable source is skipped and reported — never
retried or bypassed.

## V3 — Application assistance (not built)
`job → tailored résumé → cover letter → application-form assistance → human review →
submission`. Retains human confirmation before any submission. **Not** part of V1.

Job search/scraping and application automation are intentionally excluded from V1
(CLAUDE.md §25, §41). Interfaces are kept extensible so these can be added later without
reworking the core.

[ADR-001]: decisions/ADR-001-sqlite-over-postgres.md
[ADR-002]: decisions/ADR-002-numpy-over-pgvector.md
[ADR-004]: decisions/ADR-004-local-embedding-default.md
[ADR-005]: decisions/ADR-005-vite-react-over-nextjs.md
