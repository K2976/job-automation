"""V3 queue API + worker, driven end-to-end with an injected FakePage (no browser). Covers
task creation under the batch cap, all three approval modes over HTTP, the review→approve
path, user-answer resume, controls, and that APPLIED is set only on a real submission."""
from __future__ import annotations

import contextlib

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.applications import queue
from app.applications.page import FakePage

client = TestClient(app)

BASIC = [{"fields": [
    {"label": "First Name", "name": "first", "type": "text", "required": True},
    {"label": "Email", "name": "email", "type": "email", "required": True},
    {"label": "Resume", "name": "resume", "type": "file", "required": True},
], "control": "submit", "confirmation": "Application submitted"}]

SALARY = [{"fields": [
    {"label": "Email", "name": "email", "type": "email", "required": True},
    {"label": "Expected salary", "name": "salary", "type": "text", "required": True},
    {"label": "Resume", "name": "resume", "type": "file", "required": True},
], "control": "submit", "confirmation": "Application submitted"}]


def _use_form(form):
    @contextlib.contextmanager
    def factory():
        yield FakePage(form)
    queue.OVERRIDE_FACTORY = lambda: factory()


@pytest.fixture(autouse=True)
def _fake_browser():
    _use_form(BASIC)
    yield
    queue.OVERRIDE_FACTORY = None


def _ready_batch(mode="AUTONOMOUS", n=2):
    """Seed → discover → prepare packages → create a batch of application tasks."""
    cid = client.post("/api/candidates/seed-fixture").json()["candidate_id"]
    prefs = {"target_roles": ["Engineer", "Developer"], "experience_level": "internship",
             "sources": ["fixtures"], "preferred_locations": ["India", "Remote"]}
    run_id = client.post(f"/api/candidates/{cid}/discovery/runs", json=prefs).json()["run_id"]
    ids = client.get(f"/api/discovery/runs/{run_id}").json()["opportunity_ids"][:n]
    batch = client.post(f"/api/candidates/{cid}/batches",
                        json={"name": "B", "max_opportunities": n}).json()
    client.post(f"/api/batches/{batch['id']}/selection", json={"opportunity_ids": ids})
    client.post(f"/api/batches/{batch['id']}/prepare")
    created = client.post(f"/api/batches/{batch['id']}/applications",
                          json={"approval_mode": mode}).json()
    return cid, batch["id"], ids, created


def test_create_applications_respects_batch_max():
    cid, bid, ids, created = _ready_batch(mode="AUTONOMOUS", n=2)
    assert created["count"] == 2 <= created["max_opportunities"]
    tasks = client.get(f"/api/batches/{bid}/applications").json()["tasks"]
    assert len(tasks) == 2
    assert all(t["approval_mode"] == "AUTONOMOUS" for t in tasks)


def test_autonomous_submits_and_marks_opportunity_applied():
    cid, bid, ids, _ = _ready_batch(mode="AUTONOMOUS", n=1)
    client.post(f"/api/batches/{bid}/applications/start")     # BackgroundTask runs in-thread
    task = client.get(f"/api/batches/{bid}/applications").json()["tasks"][0]
    assert task["status"] == "CONFIRMED"
    assert client.get(f"/api/opportunities/{ids[0]}").json()["opportunity"]["status"] == "APPLIED"


def test_manual_mode_fills_but_never_applies():
    cid, bid, ids, _ = _ready_batch(mode="MANUAL", n=1)
    client.post(f"/api/batches/{bid}/applications/start")
    task = client.get(f"/api/batches/{bid}/applications").json()["tasks"][0]
    assert task["status"] == "REVIEW_REQUIRED"
    assert client.get(f"/api/opportunities/{ids[0]}").json()["opportunity"]["status"] != "APPLIED"


def test_review_then_approve_submits():
    cid, bid, ids, created = _ready_batch(mode="REVIEW_BEFORE_SUBMIT", n=1)
    tid = created["tasks"][0]["id"]
    client.post(f"/api/applications/{tid}/start")
    assert client.get(f"/api/applications/{tid}").json()["task"]["status"] == "REVIEW_REQUIRED"
    r = client.post(f"/api/applications/{tid}/approve")
    assert r.status_code == 200
    assert client.get(f"/api/applications/{tid}").json()["task"]["status"] == "CONFIRMED"


def test_high_impact_pauses_then_user_answer_resumes():
    _use_form(SALARY)
    cid, bid, ids, created = _ready_batch(mode="AUTONOMOUS", n=1)
    tid = created["tasks"][0]["id"]
    client.post(f"/api/applications/{tid}/start")
    assert client.get(f"/api/applications/{tid}").json()["task"]["status"] == "USER_ACTION_REQUIRED"
    # user answers the salary question, then restart
    client.post(f"/api/applications/{tid}/answers", json={"answers": {"salary": "Market rate"}})
    client.post(f"/api/applications/{tid}/start")
    assert client.get(f"/api/applications/{tid}").json()["task"]["status"] == "CONFIRMED"


def test_manual_task_cannot_be_approved():
    cid, bid, ids, created = _ready_batch(mode="MANUAL", n=1)
    tid = created["tasks"][0]["id"]
    client.post(f"/api/applications/{tid}/start")
    assert client.post(f"/api/applications/{tid}/approve").status_code == 409


def test_summary_reports_answer_sources():
    cid, bid, ids, created = _ready_batch(mode="MANUAL", n=1)
    tid = created["tasks"][0]["id"]
    client.post(f"/api/applications/{tid}/start")
    s = client.get(f"/api/applications/{tid}/summary").json()
    assert s["deterministic"] >= 3 and s["unresolved"] == 0
    assert s["can_submit"] is True


def test_create_tasks_never_exceeds_max_even_if_selection_larger():
    """The batch cap is normally enforced by V2 set_selection; drive queue's own [:max]
    slice directly by writing an over-long opportunity_ids (§29/§50 — 11th impossible)."""
    from app import db
    from app.applications import queue
    from app.models import ApplicationBatch
    # Prepare TWO opportunities (both get job_id) via a batch of 2.
    cid, _, ids, _ = _ready_batch(mode="AUTONOMOUS", n=2)
    # A second batch whose max is 1 but whose selection lists both prepared opps.
    over = ApplicationBatch(candidate_id=cid, name="Over", max_opportunities=1)
    over.id = db.insert_batch(over)
    over.opportunity_ids = ids[:2]
    db.save_batch(over)
    tasks = queue.create_tasks_for_batch(over.id)
    assert len(tasks) == 1                      # capped at max, never 2


def test_control_pause_and_cancel():
    cid, bid, ids, created = _ready_batch(mode="MANUAL", n=1)
    tid = created["tasks"][0]["id"]
    assert client.post(f"/api/applications/{tid}/action",
                       json={"action": "pause"}).json()["status"] == "PAUSED"
    assert client.post(f"/api/applications/{tid}/action",
                       json={"action": "cancel"}).json()["status"] == "CANCELLED"
