# Setup

## Requirements
- Python 3.11+ (developed on 3.13)
- No PostgreSQL, Docker or API keys needed for the default offline setup.

## Install & run
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.api:app --app-dir backend --reload
```
Open `http://127.0.0.1:8000`.

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
# .env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
# optionally EMBEDDING_PROVIDER=gemini
```
No code changes — the provider abstraction handles it.

## Security
`.env` and `*.sqlite3` are gitignored. Uploads are type/size validated. Provider keys stay
server-side; the browser never sees them. Never commit secrets — only `.env.example`.
