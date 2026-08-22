"""Greenhouse/Lever adapters against mocked HTTP — the core suite never hits a live API.
Covers success, pagination-shape, malformed, rate-limit, and CAPTCHA/anti-bot skip (§37)."""
from __future__ import annotations

import httpx
import pytest

from app.config import settings
from app.models import SearchPreferences, SourceStatus
from app.opportunities.sources import get_enabled_sources
from app.opportunities.sources.greenhouse import GreenhouseSource
from app.opportunities.sources.lever import LeverSource

GH_JOBS = {"jobs": [
    {"id": 1, "title": "Backend Engineer", "location": {"name": "Remote"},
     "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
     "content": "&lt;p&gt;Build APIs with &lt;strong&gt;Python&lt;/strong&gt; and FastAPI&lt;/p&gt;"},
    {"id": 2, "title": "Data Engineer", "location": {"name": "Bangalore"},
     "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
     "content": "SQL and ETL pipelines"},
]}
LEVER_POSTINGS = [
    {"id": "a", "text": "ML Engineer", "categories": {"location": "Remote", "commitment": "Internship"},
     "workplaceType": "remote", "descriptionPlain": "Train models with PyTorch",
     "hostedUrl": "https://jobs.lever.co/acme/a", "applyUrl": "https://jobs.lever.co/acme/a/apply"},
]


def _patch(monkeypatch, *, status=200, json=None, text=None):
    def fake_get(url, **kw):
        return httpx.Response(status, json=json, text=text)
    monkeypatch.setattr(httpx, "get", fake_get)


def test_greenhouse_success(monkeypatch):
    _patch(monkeypatch, json=GH_JOBS)
    result = GreenhouseSource(["acme"]).run(SearchPreferences())
    assert result.status == SourceStatus.AVAILABLE
    assert len(result.opportunities) == 2
    first = result.opportunities[0]
    assert first.title == "Backend Engineer"
    assert "Python" in first.description and "<" not in first.description  # HTML stripped
    assert first.source_id == "acme:1"


def test_lever_success_maps_fields(monkeypatch):
    _patch(monkeypatch, json=LEVER_POSTINGS)
    result = LeverSource(["acme"]).run(SearchPreferences())
    assert result.status == SourceStatus.AVAILABLE
    opp = result.opportunities[0]
    assert opp.title == "ML Engineer"
    assert opp.work_mode == "remote"
    assert opp.employment_type == "Internship"
    assert opp.application_url.endswith("/apply")


def test_rate_limit_is_isolated(monkeypatch):
    _patch(monkeypatch, status=429, text="slow down")
    result = GreenhouseSource(["acme"]).run(SearchPreferences())
    assert result.status == SourceStatus.RATE_LIMITED
    assert result.opportunities == []


def test_captcha_body_is_detected_not_bypassed(monkeypatch):
    _patch(monkeypatch, status=200, text="Please complete the CAPTCHA to continue")
    result = LeverSource(["acme"]).run(SearchPreferences())
    assert result.status == SourceStatus.CAPTCHA  # skipped, never solved


def test_malformed_response_is_unsupported(monkeypatch):
    _patch(monkeypatch, status=200, text="<html>not json</html>")
    result = GreenhouseSource(["acme"]).run(SearchPreferences())
    assert result.status == SourceStatus.UNSUPPORTED


def test_bad_board_token_is_unsupported(monkeypatch):
    _patch(monkeypatch, status=404, text="not found")
    result = GreenhouseSource(["nope"]).run(SearchPreferences())
    assert result.status == SourceStatus.UNSUPPORTED


def test_registry_drops_unconfigured_sources(monkeypatch):
    monkeypatch.setattr(settings, "greenhouse_boards", "")
    monkeypatch.setattr(settings, "lever_boards", "acme")
    names = [s.name for s in get_enabled_sources(["fixtures", "greenhouse", "lever"])]
    assert "greenhouse" not in names  # no boards configured
    assert "lever" in names and "fixtures" in names
