"""Environment-based configuration. No secrets or model names hardcoded elsewhere."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = two levels up from this file (backend/app/config.py -> repo/)
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "data/adaptive_resume.sqlite3"

    llm_provider: str = "mock"       # mock | gemini | groq
    llm_model: str = ""              # optional override
    gemini_api_key: str = ""
    groq_api_key: str = ""
    gemini_auth: str = "query"       # query (?key=) | bearer (Authorization header)
    llm_timeout: float = 60.0        # seconds per request
    llm_max_retries: int = 2         # retries on 429 / 5xx / timeout

    embedding_provider: str = "local"  # local | gemini

    retrieval_top_k: int = 8
    semantic_weight: float = 0.6
    keyword_weight: float = 0.4

    max_upload_bytes: int = 5 * 1024 * 1024

    # --- V3.5 remote browser worker (§13-§18) ---
    # Shared secret the MacBook worker presents. Empty ⇒ the whole /worker channel is
    # refused (fail closed) — never accidentally open. Set on Render, in the worker env.
    worker_auth_token: str = ""
    # True: /start runs the browser in-process (dev + the whole test suite, unchanged).
    # False: /start only enqueues (→QUEUED); the remote MacBook worker executes it. Render
    # sets INLINE_APPLICATIONS=false so the API service never launches Chromium (§5).
    inline_applications: bool = True
    # A worker (and any task it holds) is considered offline/stale after this many seconds
    # with no heartbeat; a claim must be at least `worker_stale_grace` old to be recovered.
    worker_heartbeat_timeout: float = 45.0
    worker_stale_grace: float = 60.0

    # --- V2 opportunity discovery ---
    # Enabled source adapters (comma-separated). Greenhouse + Lever are official no-auth
    # JSON feeds (real live jobs); "fixtures" is the offline demo source (used by tests and
    # available for no-network runs, but not on by default so results are real, not example.com).
    opportunity_sources: str = "greenhouse,lever"
    # Verified public board tokens (curl-checked to return jobs). Mid-size boards so a run
    # stays responsive (~hundreds of postings); add big boards (databricks, coinbase,
    # anthropic, stripe…) via GREENHOUSE_BOARDS env if you want a wider sweep.
    greenhouse_boards: str = "figma,discord,robinhood,dropbox,airbnb"
    lever_boards: str = "palantir,spotify"   # comma-separated Lever company slugs
    discovery_deep_top_n: int = 15    # opps that reach LLM JD analysis after cheap match
    discovery_shortlist_n: int = 10   # opps surfaced as the shortlist after ranking
    discovery_max_result_limit: int = 50  # hard cap on a per-run requested result count
    discovery_http_timeout: float = 15.0
    discovery_max_pages: int = 5      # pagination cap per source (anti-runaway)

    @property
    def opportunity_source_list(self) -> list[str]:
        return [s.strip() for s in self.opportunity_sources.split(",") if s.strip()]

    @property
    def greenhouse_board_list(self) -> list[str]:
        return [s.strip() for s in self.greenhouse_boards.split(",") if s.strip()]

    @property
    def lever_board_list(self) -> list[str]:
        return [s.strip() for s in self.lever_boards.split(",") if s.strip()]

    # Comma-separated allowed origins for the split deployment (frontend on a different
    # host than the API). "*" is fine here — there is no auth/cookies — but note CORS is
    # not a security boundary. See docs/deployment.md.
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_path(self) -> Path:
        p = Path(self.database_url)
        return p if p.is_absolute() else REPO_ROOT / p


settings = Settings()
