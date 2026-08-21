from fastapi.testclient import TestClient

from app.api import app


def test_full_api_flow():
    client = TestClient(app)  # triggers startup -> init_db on the isolated test db

    assert client.get("/api/health").json()["llm_provider"] == "mock"

    cid = client.post("/api/candidates/seed-fixture").json()["candidate_id"]

    jd = "Data Engineer\nRequired:\n- Python, SQL, PostgreSQL, ETL, Airflow"
    analysis = client.post("/api/jobs",
                           json={"candidate_id": cid, "jd_text": jd}).json()
    job_id = analysis["job_id"]
    assert analysis["matches"]
    assert analysis["plan"]["suggestions"]

    add = next(s for s in analysis["plan"]["suggestions"] if s["type"] == "ADD_SKILL")
    r = client.post(f"/api/suggestions/{add['id']}/approve",
                    json={"action": "ACCEPT"})
    assert r.json()["status"] == "USER_CONFIRMED"

    gen = client.post(f"/api/jobs/{job_id}/generate").json()
    assert gen["resume"]["candidate"]["name"] == "Kartik Sanghi"
    assert gen["validation"]["unsupported"] == 0
    assert 0.0 <= gen["ats"]["overall_score"] <= 1.0

    ex = client.get(f"/api/jobs/{job_id}/explain", params={"requirement": "python"})
    assert ex.json()["status"] == "STRONG_MATCH"


def test_ingest_text_endpoint():
    client = TestClient(app)
    r = client.post("/api/ingest", data={"text": "Jane\njane@x.com\nSkills: Python, SQL"})
    assert r.status_code == 200
    assert r.json()["candidate"]["email"] == "jane@x.com"


def test_unknown_candidate_404():
    client = TestClient(app)
    assert client.post("/api/jobs", json={"candidate_id": 999,
                                          "jd_text": "x"}).status_code == 404
