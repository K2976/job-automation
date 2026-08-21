"""Shared HTTP helper for live LLM providers: timeout + bounded retry on transient
failures (timeouts, 429 rate limits, 5xx). Keeps retry/timeout policy in one place."""
from __future__ import annotations

import time

import httpx

from ..config import settings
from .llm import LLMError

_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


def post_json(url: str, *, json: dict, params: dict | None = None,
              headers: dict | None = None) -> dict:
    """POST and return parsed JSON, retrying transient errors with backoff.
    Raises LLMError (never leaks the raw httpx exception or the API key)."""
    last: Exception | None = None
    for attempt in range(settings.llm_max_retries + 1):
        try:
            r = httpx.post(url, json=json, params=params, headers=headers,
                           timeout=settings.llm_timeout)
            if r.status_code in _RETRYABLE_STATUS:
                last = LLMError(f"HTTP {r.status_code}: {r.text[:200]}")
                _sleep(attempt, r)
                continue
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException as e:
            last = LLMError(f"request timed out after {settings.llm_timeout}s")
            _sleep(attempt, None)
        except httpx.HTTPStatusError as e:
            # non-retryable status (e.g. 401/403 bad key, 400 bad request)
            raise LLMError(f"HTTP {e.response.status_code}: "
                           f"{e.response.text[:200]}") from e
        except httpx.HTTPError as e:
            last = LLMError(f"network error: {type(e).__name__}")
            _sleep(attempt, None)
    raise last or LLMError("request failed")


def _sleep(attempt: int, resp: httpx.Response | None) -> None:
    if resp is not None:
        retry_after = resp.headers.get("retry-after")
        if retry_after and retry_after.isdigit():
            time.sleep(min(float(retry_after), 30.0))
            return
    time.sleep(min(2 ** attempt, 8))  # 1s, 2s, 4s, 8s…
