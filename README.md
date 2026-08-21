# Adaptive Resume Engineer

An RAG-powered system that takes a candidate's **master profile** and a **job
description**, and produces a **role-specific tailored résumé** — reframing, reordering
and strengthening the candidate's real experience for the target role, without ever
silently inventing facts.

It is not a "JD → LLM → résumé" generator. It treats the candidate's experience as a
living knowledge base and reasons over *retrieved evidence* with a human-in-the-loop
approval step before anything is written.

```
Resume ─► ingest ─► Knowledge Base (provenance-tagged)
                          │
JD ─► analyze ─► requirements ─► hybrid retrieval ─► evidence matching ─► gap analysis
                                                                              │
                                              modification plan ─► HUMAN APPROVAL
                                                                              │
                                          tailored résumé ─► claim validation ─► ATS analysis
```

## Why it's different

- **Provenance on everything.** Every fact is `ORIGINAL`, `AI_SUGGESTED`,
  `USER_CONFIRMED`, `USER_EDITED`, `GENERATED` or `REJECTED`. A missing skill is never
  silently converted into a verified one.
- **RAG, not hallucination.** The LLM reasons over retrieved candidate evidence; the
  scoring, classification and validation are deterministic Python.
- **Human-in-the-loop.** Skill additions and project rewrites are *proposed*; nothing is
  applied until the candidate accepts/edits/rejects it.
- **Anti-hallucination validator.** After generation, every skill claim is traced back to
  evidence; unsupported claims are flagged.

## Features (V1)

Resume ingestion (PDF/DOCX/text) · candidate knowledge base · JD analysis · hybrid
retrieval (semantic + keyword + structured filters) · evidence matching · gap analysis ·
modification plan · approval workflow · tailored generation · claim validation ·
JD-alignment/ATS analysis · explainability · original-vs-tailored comparison.

## Architecture at a glance

| Concern | Choice | Notes |
|---|---|---|
| API | FastAPI + Pydantic | thin; logic lives in stage modules |
| UI | single-page vanilla JS | backend-first; Next.js is future work |
| Storage | **SQLite** (stdlib) | stands in for Postgres — [ADR-001](docs/decisions/ADR-001-sqlite-over-postgres.md) |
| Vector search | **numpy cosine** | KB is tiny; no vector DB — [ADR-002](docs/decisions/ADR-002-numpy-over-pgvector.md) |
| LLM | `LLMProvider`: mock / Gemini / Groq | [ADR-003](docs/decisions/ADR-003-llm-provider-abstraction.md) |
| Embeddings | `EmbeddingProvider`: local TF-IDF / Gemini | [ADR-004](docs/decisions/ADR-004-local-embedding-default.md) |

The **mock LLM + local TF-IDF embedder are the defaults**, so the whole system runs and
is tested fully offline with **no API keys**. Gemini/Groq are opt-in via env vars.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # defaults are offline (mock + local)

uvicorn app.api:app --app-dir backend --reload
# open http://127.0.0.1:8000
```

In the UI: **Load sample candidate → pick a sample JD → Analyze → accept/reject
suggestions → Generate**.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `data/adaptive_resume.sqlite3` | SQLite file path |
| `LLM_PROVIDER` | `mock` | `mock` \| `gemini` \| `groq` |
| `LLM_MODEL` | *(provider default)* | optional model override |
| `GEMINI_API_KEY` / `GROQ_API_KEY` | — | only if using that provider |
| `EMBEDDING_PROVIDER` | `local` | `local` \| `gemini` |
| `RETRIEVAL_TOP_K`, `SEMANTIC_WEIGHT`, `KEYWORD_WEIGHT` | `8`, `0.6`, `0.4` | retrieval tuning |

Never commit `.env`. See [`docs/setup.md`](docs/setup.md).

## Development & tests

```bash
pytest -q                 # 29 tests, fully offline (PDF test needs dev-only reportlab, else skips)
```

Structure: `backend/app/` (stage modules), `data/fixtures/` (sample profile + JDs, doubles
as the RAG eval set), `tests/`, `docs/`.
See [`docs/development.md`](docs/development.md) and [`docs/architecture.md`](docs/architecture.md).

## Documentation

[product overview](docs/product-overview.md) · [architecture](docs/architecture.md) ·
[knowledge base](docs/candidate-knowledge-base.md) · [RAG pipeline](docs/rag-pipeline.md) ·
[LLM strategy](docs/llm-strategy.md) · [resume generation](docs/resume-generation.md) ·
[gap analysis](docs/gap-analysis.md) · [validation](docs/validation.md) ·
[API](docs/api.md) · [setup](docs/setup.md) · [roadmap](docs/roadmap.md)

## Status

V1 core is implemented and tested end-to-end on the mock provider. Real Gemini/Groq
providers are wired but require keys. Job discovery (V2) and application automation (V3)
are intentionally **not** built — see the [roadmap](docs/roadmap.md).
