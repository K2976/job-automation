# Development

## Layout
```
backend/app/
  config.py            env config          db.py         SQLite (direct sqlite3)
  models.py            Pydantic domain     text_utils.py skill lexicon + tokeniser
  prompts.py           versioned prompts   providers/    llm.py, embeddings.py, gemini*,
                                                          groq*, _http.py (retry/timeout)
  ingestion.py  kb.py  retrieval.py  matching.py  planning.py
  generation.py  validation.py  analysis.py  export.py (PDF/HTML)
  pipeline.py          orchestration       api.py + static/index.html (fallback UI)
frontend/              React + Vite + TS + Tailwind
  src/api/             client.ts (typed fetch) + types.ts (matches models.py)
  src/store.ts         useEngine() state hook   src/ui.tsx  primitives
  src/App.tsx          src/panels/  Profile · Analysis · Modifications · Resume
data/fixtures/         sample profile + JDs (also the eval set)
tests/                 pytest (offline)
docs/                  incl. decisions/ (ADRs)
```

## Frontend
```bash
cd frontend
npm install
npm run dev        # Vite dev server :5173, proxies /api -> :8000
npm run build      # tsc typecheck + production build to dist/ (served by FastAPI)
npm run typecheck  # tsc --noEmit
npm test           # vitest — component render + interaction smoke tests
```
The React app is presentational: all logic goes through `src/api/client.ts` and the
`useEngine()` hook. `types.ts` is hand-kept in sync with `backend/app/models.py`.

### Design system
Light, editorial theme defined as tokens in `src/index.css` (Tailwind v4 `@theme`): a
single deep-teal accent, **Inter** for UI and **JetBrains Mono** for data / provenance /
scores. Shared primitives live in `src/ui.tsx` (`Button`, `Badge`, `Meter`, `Alert`,
`EmptyState`, `SectionHeader`, `Surface`, `icons`). Provenance is shown with text + a dot,
never colour alone. Prefer sections + dividers + whitespace over nested cards.

### Visual verification (no browser driver installed)
`src/gallery.tsx` (served at `/gallery.html` in dev, excluded from the production bundle)
renders the real Shell + panels with mock data so any screen can be screenshotted without a
backend. Capture with headless Chrome and view the PNG:
```bash
npm run dev
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --window-size=1280,900 --screenshot=out.png "http://localhost:5173/gallery.html?s=analysis"
# states: start | profile | analysis | modifications | resume
```

## Tests
```bash
pytest -q          # 29 tests, no keys, no network
```
`tests/conftest.py` gives each test an isolated temp SQLite DB and a `candidate_id`
fixture. Coverage: text utils, retrieval/matching, provenance transitions, validation,
ATS, ingestion/JD parsing, binary PDF/DOCX extraction, full pipeline e2e (both JDs), and
the API via TestClient. The PDF test needs the dev-only `reportlab` (skips if absent).

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
