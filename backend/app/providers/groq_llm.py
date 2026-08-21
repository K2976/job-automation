"""Groq LLM provider (OpenAI-compatible REST via httpx)."""
from __future__ import annotations

import httpx

from ..config import settings
from .llm import LLMError, LLMProvider

_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqLLMProvider(LLMProvider):
    name = "groq"

    def __init__(self) -> None:
        if not settings.groq_api_key:
            raise LLMError("GROQ_API_KEY is not set")
        self.model = settings.llm_model or _DEFAULT_MODEL

    def _complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
        try:
            r = httpx.post(_URL, json=payload, headers=headers, timeout=60)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError) as e:
            raise LLMError(f"Groq request failed: {e}") from e
