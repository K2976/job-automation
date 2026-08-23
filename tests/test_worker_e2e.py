"""Full remote-api / local-worker loop (§29) with NO browser and NO real network: the
actual worker code (worker.worker) runs its claim → download résumé → drive runner →
report-complete path, but its HTTP client is wired to the FastAPI app in-process and its
Chromium session is swapped for a FakePage. This proves the split end to end: a QUEUED task
becomes CONFIRMED and the opportunity flips to APPLIED — through the real /worker endpoints."""
from __future__ import annotations

import contextlib

import pytest
from fastapi.testclient import TestClient

from app import db
from app.api import app
from app.applications.page import FakePage
from app.config import settings
from worker import worker as w

BASIC = [{"fields": [
    {"label": "First Name", "name": "first", "type": "text", "required": True},
    {"label": "Email", "name": "email", "type": "email", "required": True},
    {"label": "Resume", "name": "resume", "type": "file", "required": True},
], "control": "submit", "confirmation": "Application submitted"}]


@pytest.fixture
def api_client():
    """An httpx client that speaks to the FastAPI app in-process (no sockets), with the
    worker's own bearer token — exactly what worker.worker uses at runtime."""
    settings.worker_auth_token = "e2e-token"
    settings.inline_applications = False
    # TestClient IS a sync httpx.Client wired to the ASGI app — the worker code can't tell
    # it apart from a real one; every /worker hop is exercised for real, just no sockets.
    client = TestClient(app, headers={"Authorization": "Bearer e2e-token"})
    yield client
    client.close()
    settings.worker_auth_token = ""
    settings.inline_applications = True


@pytest.fixture(autouse=True)
def _fake_browser(monkeypatch):
    @contextlib.contextmanager
    def fake_session(headless: bool = True):
        yield FakePage(BASIC)
    monkeypatch.setattr(w, "playwright_session", fake_session)


def _queue_one(api_client) -> tuple[int, int]:
    """Seed → prepare → enqueue one AUTONOMOUS task; return (batch_id, opportunity_id)."""
    j = api_client.post("/api/candidates/seed-fixture").json()
    cid = j["candidate_id"]
    prefs = {"target_roles": ["Engineer", "Developer"], "experience_level": "internship",
             "sources": ["fixtures"], "preferred_locations": ["India", "Remote"]}
    run_id = api_client.post(f"/api/candidates/{cid}/discovery/runs",
                             json=prefs).json()["run_id"]
    oid = api_client.get(f"/api/discovery/runs/{run_id}").json()["opportunity_ids"][0]
    bid = api_client.post(f"/api/candidates/{cid}/batches",
                          json={"name": "B", "max_opportunities": 1}).json()["id"]
    api_client.post(f"/api/batches/{bid}/selection", json={"opportunity_ids": [oid]})
    api_client.post(f"/api/batches/{bid}/prepare")
    api_client.post(f"/api/batches/{bid}/applications", json={"approval_mode": "AUTONOMOUS"})
    api_client.post(f"/api/batches/{bid}/applications/start")     # remote ⇒ QUEUED
    return bid, oid


def test_full_remote_loop_submits_and_marks_applied(api_client):
    bid, oid = _queue_one(api_client)

    # Claim + process through the REAL worker code path.
    claim = api_client.post("/worker/tasks/claim",
                            json={"worker_id": w.WORKER_ID}).json()
    w._process(api_client, claim)

    # Observe the outcome the way the frontend would.
    task = api_client.get(f"/api/batches/{bid}/applications").json()["tasks"][0]
    assert task["status"] == "CONFIRMED"
    assert db.get_opportunity(oid).status.value == "APPLIED"

    # Queue is now drained — a second claim gets nothing.
    assert api_client.post("/worker/tasks/claim",
                           json={"worker_id": w.WORKER_ID}).status_code == 204


def test_review_mode_stops_at_review_not_applied(api_client):
    j = api_client.post("/api/candidates/seed-fixture").json()
    cid = j["candidate_id"]
    prefs = {"target_roles": ["Engineer", "Developer"], "experience_level": "internship",
             "sources": ["fixtures"], "preferred_locations": ["India", "Remote"]}
    run_id = api_client.post(f"/api/candidates/{cid}/discovery/runs",
                             json=prefs).json()["run_id"]
    oid = api_client.get(f"/api/discovery/runs/{run_id}").json()["opportunity_ids"][0]
    bid = api_client.post(f"/api/candidates/{cid}/batches",
                          json={"name": "B", "max_opportunities": 1}).json()["id"]
    api_client.post(f"/api/batches/{bid}/selection", json={"opportunity_ids": [oid]})
    api_client.post(f"/api/batches/{bid}/prepare")
    api_client.post(f"/api/batches/{bid}/applications",
                    json={"approval_mode": "REVIEW_BEFORE_SUBMIT"})
    api_client.post(f"/api/batches/{bid}/applications/start")

    claim = api_client.post("/worker/tasks/claim",
                            json={"worker_id": w.WORKER_ID}).json()
    assert claim["submit"] is False
    w._process(api_client, claim)

    task = api_client.get(f"/api/batches/{bid}/applications").json()["tasks"][0]
    assert task["status"] == "REVIEW_REQUIRED"          # filled, awaiting approval
    assert db.get_opportunity(oid).status.value != "APPLIED"
