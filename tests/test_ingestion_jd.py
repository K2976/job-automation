import pytest

from app.ingestion import IngestionError, extract_text, ingest_resume_text
from app.providers import get_llm_provider


def test_reject_unsupported_type():
    with pytest.raises(IngestionError):
        extract_text("resume.exe", b"data")


def test_reject_oversize(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_bytes", 4)
    with pytest.raises(IngestionError):
        extract_text("resume.txt", b"way too long")


def test_extract_txt():
    assert "hello" in extract_text("r.txt", b"hello world")


def test_jd_analysis_splits_required_preferred():
    llm = get_llm_provider("mock")
    jd = """Data Engineer
Required skills:
- Python and SQL
Nice to have:
- Spark
"""
    req = llm.analyze_jd(jd)
    assert "python" in req.required_skills
    assert "sql" in req.required_skills
    assert "spark" in req.preferred_skills


def test_mock_resume_parse_extracts_contact_and_skills():
    llm = get_llm_provider("mock")
    profile = ingest_resume_text(
        "Jane Doe\njane@doe.com\nSkills: Python, PostgreSQL, FastAPI", llm)
    assert profile.candidate.email == "jane@doe.com"
    names = {s.name for s in profile.skills}
    assert "python" in names and "postgresql" in names
