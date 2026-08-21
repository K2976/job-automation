"""Groq LLM provider (OpenAI-compatible REST via httpx)."""
from __future__ import annotations

from ..config import settings
from ._http import post_json
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
        data = post_json(_URL, json=payload, headers=headers)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"Groq returned an unexpected response shape: {e}") from e
