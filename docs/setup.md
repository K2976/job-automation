# Setup

## Requirements
- Python 3.11+ (developed on 3.13)
- No PostgreSQL, Docker or API keys needed for the default offline setup.

## Install & run
```bash
# backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# frontend (once — builds the React app FastAPI serves)
cd frontend && npm install && npm run build && cd ..

uvicorn app.api:app --app-dir backend --reload
```
Open `http://127.0.0.1:8000`. (Skip the frontend build to run backend-only — a legacy
static UI is served as a fallback.) For frontend hot-reload: `cd frontend && npm run dev`.

## Configuration
All config is env-based (`backend/app/config.py`, read from `.env`).

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `data/adaptive_resume.sqlite3` | relative to repo root |
| `LLM_PROVIDER` | `mock` | `mock` \| `gemini` \| `groq` |
| `LLM_MODEL` | *(provider default)* | optional override |
| `GEMINI_API_KEY` / `GROQ_API_KEY` | — | required only for that provider |
| `EMBEDDING_PROVIDER` | `local` | `local` \| `gemini` |
| `RETRIEVAL_TOP_K` / `SEMANTIC_WEIGHT` / `KEYWORD_WEIGHT` | `8` / `0.6` / `0.4` | retrieval tuning |
| `MAX_UPLOAD_BYTES` | `5242880` | upload size cap |

## Using a real LLM
```bash
# .env  (never .env.example)
LLM_PROVIDER=groq              # or gemini
GROQ_API_KEY=your_key          # / GEMINI_API_KEY=your_key
# GEMINI_AUTH=query            # or "bearer" for OAuth/access tokens
# LLM_TIMEOUT=60  LLM_MAX_RETRIES=2
```
No code changes — the provider abstraction handles it. Verify a key first with a
read-only call:
```bash
curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY" | head
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" | head
```
If Gemini returns "API key not valid", the key is likely an OAuth token — set
`GEMINI_AUTH=bearer`.

## Security
`.env` and `*.sqlite3` are gitignored. Uploads are type/size validated. Provider keys stay
server-side; the browser never sees them. Never commit secrets — only `.env.example`.
