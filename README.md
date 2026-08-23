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

Resume ingestion (PDF/DOCX/text) · candidate knowledge base with inline editing · JD
analysis · hybrid retrieval (semantic + keyword + structured filters) · evidence matching ·
gap analysis · modification plan · approval workflow · tailored generation · claim
validation · JD-alignment/ATS analysis · explainability · original-vs-tailored comparison ·
professional LaTeX PDF (+ reportlab PDF/HTML/Markdown/.tex) export · reusable role-view
snapshots · live Gemini/Groq or offline mock.

## Architecture at a glance

| Concern | Choice | Notes |
|---|---|---|
| API | FastAPI + Pydantic | thin; logic lives in stage modules |
| Frontend | **React + Vite + TypeScript + Tailwind** | 4-step workflow UI — [ADR-005](docs/decisions/ADR-005-vite-react-over-nextjs.md) |
| Storage | **SQLite** (stdlib) | stands in for Postgres — [ADR-001](docs/decisions/ADR-001-sqlite-over-postgres.md) |
| Vector search | **numpy cosine** | KB is tiny; no vector DB — [ADR-002](docs/decisions/ADR-002-numpy-over-pgvector.md) |
| LLM | `LLMProvider`: mock / Gemini / Groq | [ADR-003](docs/decisions/ADR-003-llm-provider-abstraction.md) |
| Embeddings | `EmbeddingProvider`: local TF-IDF / Gemini | [ADR-004](docs/decisions/ADR-004-local-embedding-default.md) |
| Export | **LaTeX template → PDF** (tectonic), reportlab PDF, HTML, Markdown, `.tex` | deterministic renderer over the structured model — [resume-template-system.md](docs/resume-template-system.md) |

The **mock LLM + local TF-IDF embedder are the defaults**, so the whole system runs and
is tested fully offline with **no API keys**. Gemini/Groq are opt-in via env vars.

## Quick start

```bash
# 1. Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # defaults are offline (mock + local)

# 2. Frontend (once — builds the React app FastAPI serves)
cd frontend && npm install && npm run build && cd ..

# 3. Run
uvicorn app.api:app --app-dir backend --reload
# open http://127.0.0.1:8000
```

The 4-step UI: **Profile** (load sample candidate / paste résumé, edit the knowledge base)
→ **Analysis** (pick a JD, see matches/gaps/evidence, click a requirement for the
explanation) → **Modifications** (accept/edit/reject) → **Résumé** (preview, validate,
alignment score, compare, and export PDF/HTML/Markdown).

Skip step 2 to run backend-only — FastAPI falls back to a legacy static UI when the React
app isn't built.

### Frontend dev (hot reload)
```bash
cd frontend && npm run dev      # Vite on :5173, proxies /api to :8000
```

### Live LLM providers
Set in `.env` (never in `.env.example`):
```bash
LLM_PROVIDER=groq      # or gemini
GROQ_API_KEY=...        # / GEMINI_API_KEY=...
# GEMINI_AUTH=query     # or "bearer" if the key is an OAuth/access token
```
Defaults: Groq → `openai/gpt-oss-120b`, Gemini → `gemini-2.5-flash` (override with
`LLM_MODEL`).

### Deploy (Vercel + Render)
Frontend on Vercel, backend on Render — see [`docs/deployment.md`](docs/deployment.md)
(`render.yaml` + `vercel.json` included). ⚠️ The public API has no auth, so a live-key
deploy lets anyone spend your LLM quota — it defaults to `LLM_PROVIDER=mock`; flip to live
only while demoing and set provider spend caps.
Verify a key with a read-only call before relying on it:
```bash
curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY" | head
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" | head
```

**V3.5 production split:** the public site (Vercel + Render + **Neon** Postgres) stays up
independently; the heavy Playwright/Chromium worker runs on the MacBook in Docker and reaches
the Render API over an authenticated outbound channel. Follow
[`docs/deployment-runbook.md`](docs/deployment-runbook.md) and
[`docs/manual-cloud-setup.md`](docs/manual-cloud-setup.md); background in
[production-architecture](docs/production-architecture.md), [worker-api](docs/worker-api.md),
[database](docs/database.md), [docker worker](docs/docker-browser-worker.md),
[mac worker](docs/mac-browser-worker.md), [render](docs/render-deployment.md),
[vercel](docs/vercel-deployment.md).

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `data/adaptive_resume.sqlite3` | SQLite file path |
| `LLM_PROVIDER` | `mock` | `mock` \| `gemini` \| `groq` |
| `LLM_MODEL` | *(provider default)* | optional model override |
| `GEMINI_API_KEY` / `GROQ_API_KEY` | — | only if using that provider |
| `GEMINI_AUTH` | `query` | `query` (API key) \| `bearer` (OAuth token) |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` | `60` / `2` | per-request timeout, retry on 429/5xx |
| `EMBEDDING_PROVIDER` | `local` | `local` \| `gemini` |
| `RETRIEVAL_TOP_K`, `SEMANTIC_WEIGHT`, `KEYWORD_WEIGHT` | `8`, `0.6`, `0.4` | retrieval tuning |

Never commit `.env`. See [`docs/setup.md`](docs/setup.md).

## Development & tests

```bash
pytest -q                 # 35 backend tests, fully offline
cd frontend && npm run build   # tsc typecheck + production build
```

Structure: `backend/app/` (stage modules), `frontend/` (React app), `data/fixtures/`
(sample profile + JDs, doubles as the RAG eval set), `tests/`, `docs/`.
See [`docs/development.md`](docs/development.md) and [`docs/architecture.md`](docs/architecture.md).

## Documentation

[product overview](docs/product-overview.md) · [architecture](docs/architecture.md) ·
[knowledge base](docs/candidate-knowledge-base.md) · [RAG pipeline](docs/rag-pipeline.md) ·
[LLM strategy](docs/llm-strategy.md) · [resume generation](docs/resume-generation.md) ·
[gap analysis](docs/gap-analysis.md) · [validation](docs/validation.md) ·
[API](docs/api.md) · [setup](docs/setup.md) · [deployment](docs/deployment.md) ·
[roadmap](docs/roadmap.md) · **[AI validation report](docs/ai-validation-report.md)** ·
[RAG evaluation](docs/rag-evaluation.md)

### AI / RAG evaluation
```bash
pytest tests/evaluation -q                          # offline evaluation asserts (mock)
python tests/evaluation/run_eval.py --provider groq   # live eval, writes docs/eval-runs/groq.json
```
Findings, Gemini-vs-Groq, and limitations are in the
[AI validation report](docs/ai-validation-report.md). Headline: the deterministic core is
robust to live input, project reframing works, the validator catches live hallucination,
and Groq (`gpt-oss-120b`) is ~7× faster than Gemini (`gemini-3.6-flash`).

## Status

**V1** is complete: full React frontend, live Gemini/Groq providers (hardened with retry/
timeout/auth handling), résumé PDF/HTML/Markdown export, profile editing, role-view
snapshots, and the full analyze → approve → generate → validate loop.

**V2 — Opportunity Intelligence** is complete: modular source adapters (offline fixtures +
Greenhouse/Lever public APIs, with CAPTCHA/blocked sources skipped and reported — never
bypassed), a cheap-first discovery pipeline that reuses the V1 RAG engine for analysis and
matching, deterministic ranking with why-apply explanations, application batches with a
hard max-selection invariant, package preparation (tailored résumé + grounded cover letter)
reusing the V1 résumé pipeline, and an opportunity tracker — surfaced through an
Opportunities section in the same UI. Discovery runs in the background with polled,
real-count progress. See [opportunity-intelligence.md](docs/opportunity-intelligence.md),
[opportunity-sources.md](docs/opportunity-sources.md), and
[application-batches.md](docs/application-batches.md).

**V3 — Application Automation** is complete: a deterministic-first Playwright layer that
fills and (optionally) submits applications for prepared opportunities. The DOM/accessibility
tree fills identity/résumé/cover-letter fields; the LLM answers only semantic questions and
its answer is validated against candidate evidence; high-impact questions (salary/visa/
relocation) always pause. Three approval modes (Manual / Review-before-submit / Autonomous)
behind one submit predicate; CAPTCHAs stop the agent and are never bypassed; multi-page forms,
confirmation vs submission-uncertain, and the V2 batch maximum are all handled. The engine is
decoupled from the browser behind a `BrowserPage` protocol, so it is tested with an in-memory
fake **and** re-verified against real Chromium on a bundled mock application site. Surfaced
through an Applications section (operational controls only — no live browser viewer). See
[application-automation.md](docs/application-automation.md),
[browser-agent.md](docs/browser-agent.md), [approval-modes.md](docs/approval-modes.md).

All offline on the mock provider: 60+ backend test cases (Playwright tests skip if Chromium is
absent) and a typechecked frontend build. The production browser worker must run as a
dedicated service — see [deployment.md](docs/deployment.md). Roadmap: [docs/roadmap.md](docs/roadmap.md).
