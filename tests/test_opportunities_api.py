"""V2 API surface: preferences, discovery (background + poll), opportunities, batch limit,
package prep, tracker, source health. TestClient runs BackgroundTasks synchronously, so a
started run has completed by the time we poll it."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


def _seed() -> int:
    return client.post("/api/candidates/seed-fixture").json()["candidate_id"]


def _prefs() -> dict:
    return {"target_roles": ["Engineer", "Developer", "Cybersecurity"],
            "experience_level": "internship",
            "preferred_locations": ["India", "Remote"], "sources": ["fixtures"]}


def _discover(cid: int) -> dict:
    r = client.post(f"/api/candidates/{cid}/discovery/runs", json=_prefs())
    run_id = r.json()["run_id"]
    return client.get(f"/api/discovery/runs/{run_id}").json()


def test_preferences_roundtrip():
    cid = _seed()
    client.put(f"/api/candidates/{cid}/preferences", json=_prefs())
    got = client.get(f"/api/candidates/{cid}/preferences").json()
    assert got["target_roles"] == ["Engineer", "Developer", "Cybersecurity"]


def test_discovery_run_completes_with_real_counts():
    cid = _seed()
    run = _discover(cid)
    assert run["status"] == "COMPLETE"
    assert run["discovered"] == 8
    assert run["after_dedup"] == 6
    assert run["shortlisted"] == 6
    assert len(run["opportunity_ids"]) == 6


def test_opportunity_detail_has_why_apply():
    cid = _seed()
    run = _discover(cid)
    oid = run["opportunity_ids"][0]
    detail = client.get(f"/api/opportunities/{oid}").json()
    assert detail["opportunity"]["id"] == oid
    assert "strong_matches" in detail["why_apply"]
    assert detail["why_apply"]["match_score"] >= 0


def test_batch_limit_returns_409():
    cid = _seed()
    ids = _discover(cid)["opportunity_ids"]
    batch = client.post(f"/api/candidates/{cid}/batches",
                        json={"name": "B", "max_opportunities": 2}).json()
    r = client.post(f"/api/batches/{batch['id']}/selection",
                    json={"opportunity_ids": ids[:3]})
    assert r.status_code == 409


def test_batch_select_and_prepare():
    cid = _seed()
    ids = _discover(cid)["opportunity_ids"]
    batch = client.post(f"/api/candidates/{cid}/batches",
                        json={"name": "B", "max_opportunities": 2}).json()
    sel = client.post(f"/api/batches/{batch['id']}/selection",
                      json={"opportunity_ids": ids[:2]})
    assert sel.status_code == 200
    prep = client.post(f"/api/batches/{batch['id']}/prepare").json()
    assert len(prep["prepared"]) == 2
    opp = client.get(f"/api/opportunities/{ids[0]}").json()["opportunity"]
    assert opp["status"] == "READY_TO_APPLY"
    assert opp["job_id"] is not None
    # tailored résumé is exportable through the existing V1 endpoints
    assert client.get(f"/api/jobs/{opp['job_id']}/export.tex").status_code == 200
    assert client.get(f"/api/opportunities/{ids[0]}/cover-letter").json()["cover_letter"]


def test_manual_applied_status():
    cid = _seed()
    oid = _discover(cid)["opportunity_ids"][0]
    r = client.post(f"/api/opportunities/{oid}/status", json={"status": "APPLIED"})
    assert r.json()["status"] == "APPLIED"


def test_source_health_reported():
    cid = _seed()
    _discover(cid)
    sources = client.get(f"/api/candidates/{cid}/sources").json()["sources"]
    fixtures = next(s for s in sources if s["name"] == "fixtures")
    assert fixtures["status"] == "AVAILABLE"
    assert fixtures["discovered"] == 8
