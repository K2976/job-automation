import io

from fastapi.testclient import TestClient

from app import db, export, pipeline
from app.api import app
from app.models import EntityType, Status


def _generate(candidate_id):
    jd = (pipeline.FIXTURES / "jd_data_engineer.txt").read_text()
    res = pipeline.analyze_job(candidate_id, jd)
    return pipeline.generate_for_job(res["job_id"])["resume"], res["job_id"]


def test_pdf_round_trip(candidate_id):
    resume, _ = _generate(candidate_id)
    pdf = export.build_pdf(resume)
    assert pdf[:4] == b"%PDF"
    from pypdf import PdfReader
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
    assert resume.candidate.name.split()[0] in text
    assert "PostgreSQL" in text or "Python" in text


def test_html_render(candidate_id):
    resume, _ = _generate(candidate_id)
    html = export.render_html(resume)
    assert "<html" in html and resume.candidate.name in html


def test_export_endpoints(candidate_id):
    _, job_id = _generate(candidate_id)
    client = TestClient(app)
    pdf = client.get(f"/api/jobs/{job_id}/export.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert pdf.headers["content-type"] == "application/pdf"
    assert client.get(f"/api/jobs/{job_id}/export.html").text.startswith("<!doctype")


def test_profile_editing(candidate_id):
    client = TestClient(app)
    # edit candidate header
    r = client.patch(f"/api/candidates/{candidate_id}",
                     json={"name": "Kartik S", "headline": "Data Engineer"})
    assert r.json()["candidate"]["name"] == "Kartik S"

    # add a manual entity the LLM "missed"
    r = client.post(f"/api/candidates/{candidate_id}/entities",
                    json={"entity_type": "skill", "name": "Airflow", "content": "Airflow"})
    eid = r.json()["id"]
    assert db.get_entity(eid).source == "manual_entry"

    # edit then delete it
    client.patch(f"/api/entities/{eid}", json={"name": "Apache Airflow"})
    assert db.get_entity(eid).name == "Apache Airflow"
    assert client.delete(f"/api/entities/{eid}").status_code == 200
    assert db.get_entity(eid) is None


def test_generation_is_persisted(candidate_id):
    _, job_id = _generate(candidate_id)
    assert db.get_generation(job_id) is not None


def test_role_profile_snapshot(candidate_id):
    _, job_id = _generate(candidate_id)
    client = TestClient(app)
    r = client.post(f"/api/candidates/{candidate_id}/role-profiles",
                    json={"name": "Data Engineer view", "job_id": job_id})
    assert r.status_code == 200 and r.json()["target_role"] == "Data Engineer"
    listed = client.get(f"/api/candidates/{candidate_id}/role-profiles").json()
    assert listed["role_profiles"][0]["name"] == "Data Engineer view"
