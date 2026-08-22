"""Shared HTTP GET for live sources. Maps transport/status outcomes to the Source*
skip-reason exceptions so every adapter reports failures the same way — and so an
anti-bot/CAPTCHA wall is detected and SKIPPED, never retried or bypassed (§7, §32)."""
from __future__ import annotations

import html
import re

import httpx

from ...config import settings
from .base import (
    SourceBlocked,
    SourceCaptcha,
    SourceError,
    SourceRateLimited,
    SourceUnreachable,
    SourceUnsupported,
)

# Body markers that mean "an anti-bot/CAPTCHA challenge was served, not real content".
_CAPTCHA_MARKERS = ("captcha", "cf-challenge", "attention required", "access denied",
                    "are you a robot", "verify you are human", "cf-browser-verification")
_TAG_RE = re.compile(r"<[^>]+>")


def get_json(url: str, *, params: dict | None = None):
    """GET JSON with one bounded set of expectations. Raises a Source* error on failure."""
    try:
        r = httpx.get(url, params=params, timeout=settings.discovery_http_timeout,
                      headers={"User-Agent": "AdaptiveResumeEngineer/2.0 (+discovery)"},
                      follow_redirects=True)
    except httpx.TimeoutException as e:
        raise SourceUnreachable(f"timed out after {settings.discovery_http_timeout}s") from e
    except httpx.HTTPError as e:
        raise SourceUnreachable(f"network error: {type(e).__name__}") from e

    if r.status_code == 429:
        raise SourceRateLimited("HTTP 429 (rate limited)")
    if r.status_code == 403:
        # 403 is the usual anti-bot/CAPTCHA signal — inspect the body to classify.
        low = r.text[:2000].lower()
        if any(m in low for m in _CAPTCHA_MARKERS):
            raise SourceCaptcha("anti-bot challenge on 403")
        raise SourceBlocked("HTTP 403 (access denied)")
    if r.status_code in (401, 404):
        raise SourceUnsupported(f"HTTP {r.status_code} (bad board or endpoint)")
    if r.status_code >= 400:
        raise SourceError(f"HTTP {r.status_code}")

    low = r.text[:2000].lower()
    if any(m in low for m in _CAPTCHA_MARKERS):
        raise SourceCaptcha("anti-bot challenge in response body")
    try:
        return r.json()
    except ValueError as e:
        raise SourceUnsupported("response was not JSON (unexpected site structure)") from e


def plain_text(raw: str) -> str:
    """HTML → readable plain text for JD analysis (Greenhouse returns escaped HTML)."""
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", html.unescape(raw))
    return re.sub(r"\s+\n", "\n", re.sub(r"[ \t]+", " ", text)).strip()
