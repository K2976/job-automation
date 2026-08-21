"""Gemini LLM provider (REST via httpx — no vendor SDK lock-in)."""
from __future__ import annotations

import httpx

from ..config import settings
from .llm import LLMError, LLMProvider

_DEFAULT_MODEL = "gemini-1.5-flash"
_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiLLMProvider(LLMProvider):
    name = "gemini"

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        self.model = settings.llm_model or _DEFAULT_MODEL

    def _complete(self, system: str, user: str) -> str:
        url = f"{_BASE}/{self.model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.2},
        }
        try:
            r = httpx.post(url, params={"key": settings.gemini_api_key},
                           json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError) as e:
            raise LLMError(f"Gemini request failed: {e}") from e
