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

    @property
    def db_path(self) -> Path:
        p = Path(self.database_url)
        return p if p.is_absolute() else REPO_ROOT / p


settings = Settings()
