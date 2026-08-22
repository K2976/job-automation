# Architecture

## Layers

```
React app  (frontend/ — Vite + TS + Tailwind; 4-step workflow, typed API client)
      │  JSON / fetch   (built dist/ served by FastAPI; legacy static/index.html fallback)
FastAPI  (backend/app/api.py — thin: validate, call pipeline, return Pydantic)
      │
Orchestration  (pipeline.py — the two flows: analyze_job, generate_for_job)
      │
Stage modules  ── ingestion · kb · retrieval · matching · planning ·
                   generation · validation · analysis · export
      │
Providers  (providers/llm.py, providers/embeddings.py — mock/local defaults;
             providers/_http.py = retry/timeout for live Gemini/Groq)
      │
SQLite  (db.py, direct sqlite3)          Skill lexicon (text_utils.py)
```

Business logic never lives in the UI or the API handlers — handlers only marshal
input/output; the React app is presentational over a typed client (`frontend/src/api/`)
and a state hook (`store.ts`). All stages are pure-ish functions over Pydantic models
(`models.py`), which makes them independently testable. Export renders the structured
`TailoredResume` to PDF (reportlab)/HTML/Markdown — the structured model is the single
source of truth, never pre-baked resume text.

## The deterministic / LLM split (the core design decision)
- **Deterministic Python owns**: retrieval scoring, match classification, gap
  categorisation, provenance transitions, claim validation, ATS math, diffing.
- **The LLM owns only**: extraction from unstructured text (JD → requirements, résumé →
  profile) and prose (project rewrites, summary).

This is what makes the system testable offline and keeps the scores stable regardless of
provider. See [llm-strategy.md](llm-strategy.md).

## Data flow — analyze
```
jd_text ─► llm.analyze_jd ─► JDRequirements
candidate ─► db.get_entities ─► RetrievalIndex (embed corpus)
per requirement: index.search ─► matching._classify ─► RequirementMatch
matches ─► analyze_gaps ─► GapItem[]
matches + retrieved projects ─► planning.build_plan ─► ModificationPlan (+persist suggestions)
```

## Data flow — generate
```
approved suggestions (db) + KB entities ─► generation.generate_resume ─► TailoredResume
resume + ALL entities ─► validation.validate_resume ─► ValidationReport
requirements + matches + resume ─► analysis.ats_report ─► ATSReport
master render vs tailored ─► analysis.compare_resumes
```

## Provenance
`Status` (`models.py`) is threaded through every entity and claim:
`ORIGINAL · AI_SUGGESTED · USER_CONFIRMED · USER_EDITED · GENERATED · REJECTED`.
Only `ORIGINAL/USER_CONFIRMED/USER_EDITED` count as usable evidence
(`SUPPORTED_STATUSES`). Approval transitions live in `planning.apply_approval`.

## Error handling
Ingestion validates type/size (`ingestion.IngestionError` → HTTP 400). Provider failures
raise `LLMError` → HTTP 502. Malformed structured LLM output is caught and validated
against Pydantic before use (`providers/llm._parse_json`).

## V2 — Opportunity Intelligence
A second flow attaches to V1 without altering it:

```
FastAPI  (opportunities_api.py — thin router mounted alongside api.py)
      │
Discovery orchestrator  (opportunities/discovery.py — background task, polled DiscoveryRun)
      │
Sources  (opportunities/sources/ — FixtureSource + Greenhouse/Lever; error-isolated run())
      │
Processing  (opportunities/processing.py — normalize · dedup · filter · cheap match · rank; no LLM)
      │
V1 reuse  ── pipeline.match_jd (deep analysis: 1 analyze_jd/opp) ·
             pipeline.analyze_job + generate_for_job (package prep) · RetrievalIndex · matching
      │
Batches/packages  (opportunities/batches.py, packages.py)   SQLite (opportunity/batch/run/prefs)
```

The seam is deliberate: discovery deep-analysis calls `pipeline.match_jd` (analyze_jd +
deterministic matching/gaps — **no** `build_plan`/`rewrite`), so LLM cost is one call per
analysed opportunity; the full `analyze_job` + generation runs only at package preparation,
for *selected* opportunities. The Opportunity's `job_id` links back to a V1 `Job`. See
[opportunity-intelligence.md](opportunity-intelligence.md).
