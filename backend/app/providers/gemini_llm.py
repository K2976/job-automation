"""Gemini LLM provider (REST via httpx — no vendor SDK lock-in).

Auth is swappable: AI Studio API keys go in the `?key=` query param; OAuth/access
tokens go in an `Authorization: Bearer` header. Controlled by GEMINI_AUTH so an
unusual key format is a config change, not a code change."""
from __future__ import annotations

from ..config import settings
from ._http import post_json
from .llm import LLMError, LLMProvider

_DEFAULT_MODEL = "gemini-2.5-flash"
_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiLLMProvider(LLMProvider):
    name = "gemini"

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        self.model = settings.llm_model or _DEFAULT_MODEL

    def _auth(self) -> tuple[dict | None, dict | None]:
        if settings.gemini_auth.lower() == "bearer":
            return None, {"Authorization": f"Bearer {settings.gemini_api_key}"}
        return {"key": settings.gemini_api_key}, None

    def _complete(self, system: str, user: str) -> str:
        url = f"{_BASE}/{self.model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.2},
        }
        params, headers = self._auth()
        data = post_json(url, json=payload, params=params, headers=headers)
        return _extract_text(data)


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        block = (data.get("promptFeedback") or {}).get("blockReason")
        raise LLMError(f"Gemini returned no candidates"
                       + (f" (blocked: {block})" if block else ""))
    cand = candidates[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise LLMError(f"Gemini returned empty text "
                       f"(finishReason={cand.get('finishReason')})")
    return text
