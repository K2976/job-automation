"""Provider failure handling (§22) — fully offline via a mocked httpx. Asserts the app
returns useful errors, never leaks the API key, retries only transient failures, and never
corrupts candidate data or fakes a successful generation."""
import httpx
import pytest

from app import db, pipeline
from app.config import settings
from app.providers import _http
from app.providers.groq_llm import GroqLLMProvider
from app.providers.gemini_llm import GeminiLLMProvider
from app.providers.llm import LLMError, LLMProvider

SECRET = "sk-supersecret-do-not-leak"


class FakeResp:
    def __init__(self, status=200, json=None, text="", headers=None):
        self.status_code = status
        self._json = json if json is not None else {}
        self.text = text or str(self._json)
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=httpx.Request("POST", "http://x"),
                                        response=self)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _no_sleep_and_keys(monkeypatch):
    monkeypatch.setattr(_http.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(settings, "groq_api_key", SECRET)
    monkeypatch.setattr(settings, "gemini_api_key", SECRET)
    monkeypatch.setattr(settings, "llm_max_retries", 2)


def _patch_post(monkeypatch, fn):
    calls = {"n": 0}
    def wrapped(*a, **k):
        calls["n"] += 1
        return fn(calls["n"], *a, **k)
    monkeypatch.setattr(_http.httpx, "post", wrapped)
    return calls


def test_invalid_key_raises_and_never_leaks_secret(monkeypatch):
    _patch_post(monkeypatch, lambda n, *a, **k:
                FakeResp(401, json={"error": "invalid api key"}))
    with pytest.raises(LLMError) as exc:
        GroqLLMProvider()._complete("s", "u")
    assert SECRET not in str(exc.value)          # key must never appear in the error
    assert "401" in str(exc.value)


def test_timeout_retries_then_raises(monkeypatch):
    def boom(n, *a, **k):
        raise httpx.TimeoutException("slow")
    calls = _patch_post(monkeypatch, boom)
    with pytest.raises(LLMError):
        GroqLLMProvider()._complete("s", "u")
    assert calls["n"] == settings.llm_max_retries + 1   # retried, bounded


def test_rate_limit_then_success(monkeypatch):
    ok = {"choices": [{"message": {"content": "hello"}}]}
    def resp(n, *a, **k):
        return FakeResp(429, headers={"retry-after": "1"}) if n == 1 else FakeResp(200, json=ok)
    _patch_post(monkeypatch, resp)
    assert GroqLLMProvider()._complete("s", "u") == "hello"


def test_5xx_retries(monkeypatch):
    calls = _patch_post(monkeypatch, lambda n, *a, **k: FakeResp(503, text="unavailable"))
    with pytest.raises(LLMError):
        GroqLLMProvider()._complete("s", "u")
    assert calls["n"] == settings.llm_max_retries + 1


def test_malformed_response_raises(monkeypatch):
    _patch_post(monkeypatch, lambda n, *a, **k: FakeResp(200, json={"unexpected": 1}))
    with pytest.raises(LLMError):
        GroqLLMProvider()._complete("s", "u")


def test_gemini_empty_candidates_raises(monkeypatch):
    _patch_post(monkeypatch, lambda n, *a, **k:
                FakeResp(200, json={"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(LLMError) as exc:
        GeminiLLMProvider()._complete("s", "u")
    assert "SAFETY" in str(exc.value)


class _FailingLLM(LLMProvider):
    """Analyzes fine (unused here) but blows up at generation time."""
    name = "failing"
    def _complete(self, system, user):
        raise LLMError("provider exploded")
    def compose_summary(self, role, highlights):
        raise LLMError("provider exploded")


def test_generation_failure_does_not_corrupt_data(candidate_id):
    """A provider failure mid-generation must not persist a partial résumé or mutate KB."""
    jd = (pipeline.FIXTURES / "jd_data_engineer.txt").read_text()
    res = pipeline.analyze_job(candidate_id, jd)   # mock, succeeds
    job_id = res["job_id"]
    before = len(db.get_entities(candidate_id))

    with pytest.raises(LLMError):
        pipeline.generate_for_job(job_id, llm=_FailingLLM())

    assert db.get_generation(job_id) is None                 # no partial write
    assert len(db.get_entities(candidate_id)) == before      # KB untouched
