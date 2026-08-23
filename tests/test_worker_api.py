"""V3.5 remote worker channel (§13-§18, §30, §37). Exercises the /worker API the MacBook
worker uses: token auth, atomic single-claim, heartbeat/liveness, stale recovery (with the
never-double-submit rule), the server-owned APPLIED flip, ownership isolation, and the
batch cap enforced at claim. No browser and no real worker — just the HTTP surface."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app.api import app
from app.config import settings

client = TestClient(app)
TOKEN = "test-worker-token"
H = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def _worker_channel():
    """Open the worker channel (token set) and run in REMOTE mode so /start only enqueues."""
    settings.worker_auth_token = TOKEN
    settings.inline_applications = False
    yield
    settings.worker_auth_token = ""
    settings.inline_applications = True


def _queued_batch(mode="AUTONOMOUS", n=1):
    """Seed → discover → prepare → create tasks → enqueue them (remote start ⇒ QUEUED)."""
    cid = client.post("/api/candidates/seed-fixture").json()["candidate_id"]
    prefs = {"target_roles": ["Engineer", "Developer"], "experience_level": "internship",
             "sources": ["fixtures"], "preferred_locations": ["India", "Remote"]}
    run_id = client.post(f"/api/candidates/{cid}/discovery/runs", json=prefs).json()["run_id"]
    ids = client.get(f"/api/discovery/runs/{run_id}").json()["opportunity_ids"][:n]
    bid = client.post(f"/api/candidates/{cid}/batches",
                      json={"name": "B", "max_opportunities": n}).json()["id"]
    client.post(f"/api/batches/{bid}/selection", json={"opportunity_ids": ids})
    client.post(f"/api/batches/{bid}/prepare")
    client.post(f"/api/batches/{bid}/applications", json={"approval_mode": mode})
    client.post(f"/api/batches/{bid}/applications/start")     # remote ⇒ enqueue → QUEUED
    return cid, bid


def _claim(worker_id="w1"):
    return client.post("/worker/tasks/claim", json={"worker_id": worker_id}, headers=H)


# ------------------------------------------------------------------- auth #
def test_unauthenticated_claim_is_rejected():
    r = client.post("/worker/tasks/claim", json={"worker_id": "w1"})   # no header
    assert r.status_code == 401


def test_wrong_token_is_rejected():
    r = client.post("/worker/tasks/claim", json={"worker_id": "w1"},
                    headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_channel_refused_when_no_token_configured():
    settings.worker_auth_token = ""            # fail closed
    r = client.post("/worker/tasks/claim", json={"worker_id": "w1"}, headers=H)
    assert r.status_code == 503


# -------------------------------------------------------------- claiming #
def test_claim_returns_task_context_and_submit_flag():
    _queued_batch(mode="AUTONOMOUS", n=1)
    r = _claim()
    assert r.status_code == 200
    body = r.json()
    assert body["submit"] is True                       # autonomous ⇒ submit granted
    assert body["task"]["status"] == "CLAIMED"
    assert body["context"]["candidate_values"]          # context bundle is populated
    assert body["context"]["resume_url"].endswith("/resume.pdf")


def test_second_claim_gets_nothing_atomic():
    _queued_batch(mode="AUTONOMOUS", n=1)               # exactly one queued task
    assert _claim("w1").status_code == 200
    assert _claim("w2").status_code == 204              # already owned by w1


def test_review_mode_claim_does_not_grant_submit():
    _queued_batch(mode="REVIEW_BEFORE_SUBMIT", n=1)
    assert _claim().json()["submit"] is False


# --------------------------------------------------- heartbeat / liveness #
def test_heartbeat_marks_worker_online():
    assert client.get("/api/worker/status").json()["online"] is False
    client.post("/worker/heartbeat", json={"worker_id": "w1", "status": "idle"}, headers=H)
    status = client.get("/api/worker/status").json()
    assert status["online"] is True and status["inline"] is False


# ------------------------------------------------------------- complete #
def _task_id(bid):
    return client.get(f"/api/batches/{bid}/applications").json()["tasks"][0]["id"]


def test_complete_submitted_flips_opportunity_applied():
    cid, bid = _queued_batch(mode="AUTONOMOUS", n=1)
    task = _claim().json()["task"]
    r = client.post(f"/worker/tasks/{task['id']}/complete",
                    json={"worker_id": "w1", "status": "SUBMITTED"}, headers=H)
    assert r.json()["applied"] is True
    opp = db.get_opportunity(task["opportunity_id"])
    assert opp.status.value == "APPLIED"


def test_complete_uncertain_does_not_flip_applied():
    cid, bid = _queued_batch(mode="AUTONOMOUS", n=1)
    task = _claim().json()["task"]
    client.post(f"/worker/tasks/{task['id']}/complete",
                json={"worker_id": "w1", "status": "SUBMISSION_UNCERTAIN"}, headers=H)
    opp = db.get_opportunity(task["opportunity_id"])
    assert opp.status.value != "APPLIED"


def test_worker_cannot_report_applied_or_arbitrary_status():
    _queued_batch(mode="AUTONOMOUS", n=1)
    task = _claim().json()["task"]
    r = client.post(f"/worker/tasks/{task['id']}/complete",
                    json={"worker_id": "w1", "status": "QUEUED"}, headers=H)
    assert r.status_code == 400                          # not a reportable status


def test_worker_cannot_touch_task_it_does_not_own():
    _queued_batch(mode="AUTONOMOUS", n=1)
    task = _claim("w1").json()["task"]
    r = client.post(f"/worker/tasks/{task['id']}/complete",
                    json={"worker_id": "attacker", "status": "SUBMITTED"}, headers=H)
    assert r.status_code == 409
    assert db.get_opportunity(task["opportunity_id"]).status.value != "APPLIED"


# --------------------------------------------------------- stale recovery #
def test_stale_claim_without_submit_is_requeued():
    _queued_batch(mode="REVIEW_BEFORE_SUBMIT", n=1)     # fill-only ⇒ submit not granted
    task = _claim().json()["task"]
    # Force staleness: worker heartbeat + claim both "expired".
    n = db.recover_stale_tasks(heartbeat_timeout=0.0, stale_grace=0.0)
    assert n == 1
    assert db.get_task(task["id"]).status.value == "QUEUED"      # safe to re-run


def test_stale_claim_with_submit_becomes_uncertain_never_requeued():
    _queued_batch(mode="AUTONOMOUS", n=1)               # submit granted at claim
    task = _claim().json()["task"]
    n = db.recover_stale_tasks(heartbeat_timeout=0.0, stale_grace=0.0)
    assert n == 1
    # Must NOT re-queue — it might already have submitted (§18).
    assert db.get_task(task["id"]).status.value == "SUBMISSION_UNCERTAIN"


def test_fresh_claim_is_not_recovered():
    _queued_batch(mode="AUTONOMOUS", n=1)
    _claim()
    # Real timeouts: a just-claimed task with a live heartbeat is not stale.
    assert db.recover_stale_tasks(
        heartbeat_timeout=settings.worker_heartbeat_timeout,
        stale_grace=settings.worker_stale_grace) == 0


# ---------------------------------------------------------------- llm proxy #
def test_llm_answer_proxy_returns_grounded_answer():
    r = client.post("/worker/llm/answer",
                    json={"question": "Why do you want this role?",
                          "jd": "Backend Engineer. Python, FastAPI.",
                          "evidence": "Backend API: Built FastAPI services"}, headers=H)
    assert r.status_code == 200
    assert "answer" in r.json()
