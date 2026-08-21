# Development

## Layout
```
backend/app/
  config.py            env config          db.py         SQLite (direct sqlite3)
  models.py            Pydantic domain     text_utils.py skill lexicon + tokeniser
  prompts.py           versioned prompts   providers/    llm.py, embeddings.py, gemini*, groq*
  ingestion.py  kb.py  retrieval.py  matching.py  planning.py
  generation.py  validation.py  analysis.py
  pipeline.py          orchestration       api.py + static/index.html
data/fixtures/         sample profile + JDs (also the eval set)
tests/                 pytest (offline)
docs/                  incl. decisions/ (ADRs)
```

## Tests
```bash
pytest -q          # 27 tests, no keys, no network
```
`tests/conftest.py` gives each test an isolated temp SQLite DB and a `candidate_id`
fixture. Coverage: text utils, retrieval/matching, provenance transitions, validation,
ATS, ingestion/JD parsing, full pipeline e2e (both JDs), and the API via TestClient.

## Conventions
- Keep API handlers thin; logic goes in stage modules over Pydantic models.
- Deterministic logic (scoring/classification/validation) must **not** call the LLM.
- Every entity/claim carries provenance; never mint `ORIGINAL` for AI-suggested data.
- Prompts live in `prompts.py` (versioned), never inline in logic.
- Model names/keys come from config, never hardcoded.

## Adding things
- **New LLM provider**: one file implementing `_complete`; register in
  `get_llm_provider`.
- **New embedding provider**: implement `EmbeddingProvider.embed` (+ `fit` if corpus-
  dependent); register in `get_embedding_provider`.
- **New entity type**: add to `EntityType`, a content builder in `kb.py`, seed it.

## Git
Milestone-sized commits, existing repo identity, no AI-attribution trailers (CLAUDE.md
§32–33).
