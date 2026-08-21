# Architecture

## Layers

```
Single-page UI  (backend/app/static/index.html — vanilla JS, no build step)
      │  JSON / fetch
FastAPI  (backend/app/api.py — thin: validate, call pipeline, return Pydantic)
      │
Orchestration  (pipeline.py — the two flows: analyze_job, generate_for_job)
      │
Stage modules  ── ingestion · kb · retrieval · matching · planning ·
                   generation · validation · analysis
      │
Providers  (providers/llm.py, providers/embeddings.py — mock/local defaults)
      │
SQLite  (db.py, direct sqlite3)          Skill lexicon (text_utils.py)
```

Business logic never lives in the UI or the API handlers — handlers only marshal
input/output. All stages are pure-ish functions over Pydantic models (`models.py`), which
makes them independently testable.

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
