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


def test_claim_denies_submit_once_batch_cap_is_reached():
    """max=1: once one task is SUBMITTED, a claim of the next task in the batch is granted
    fill-only (submit=False) — the cap is enforced at claim, not just at creation (§20)."""
    _cid, bid = _queued_batch(mode="AUTONOMOUS", n=2)   # 2 queued tasks; cap tightened below
    # Force the batch max to 1 and mark one task SUBMITTED, so the cap is already met.
    batch = db.get_batch(bid)
    batch.max_opportunities = 1
    db.save_batch(batch)
    first = _claim("w1").json()["task"]
    client.post(f"/worker/tasks/{first['id']}/complete",
                json={"worker_id": "w1", "status": "SUBMITTED"}, headers=H)
    # The second task is still QUEUED; claiming it must NOT grant submit (cap reached).
    assert _claim("w2").json()["submit"] is False


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


# --------------------------------------------------------------- fail #
def test_fail_preserves_progress_made_before_the_crash():
    """A worker crash (e.g. a Playwright TimeoutError mid-fill) must not erase the fields it
    had already filled — /fail should persist them just like /complete does, so the UI shows
    what actually happened instead of an empty 0-questions task."""
    cid, bid = _queued_batch(mode="MANUAL", n=1)
    task = _claim().json()["task"]
    r = client.post(f"/worker/tasks/{task['id']}/fail", json={
        "worker_id": "w1", "error_code": "WORKER_ERROR",
        "error_message": "TimeoutError: ElementHandle.fill: Timeout 30000ms exceeded.",
        "questions": [{"field_key": "h0", "question_text": "First Name", "name": "first",
                       "answer": "Kartik", "answer_source": "CANDIDATE_PROFILE"}],
        "logs": [{"event": "FIELD_FILLED", "detail": "first"}],
        "current_page": 0,
    }, headers=H)
    assert r.status_code == 200
    detail = client.get(f"/api/applications/{task['id']}").json()
    assert detail["task"]["status"] == "FAILED"
    assert detail["summary"]["questions"] == 1
    assert any(e["event"] == "FIELD_FILLED" for e in detail["task"]["logs"])


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
