from app import db
from app.analysis import ats_report
from app.models import (
    Candidate,
    ClaimStatus,
    EntityType,
    JDRequirements,
    KBEntity,
    ResumeBullet,
    ResumeSection,
    Status,
    TailoredResume,
    ValidationReport,
)
from app.validation import validate_resume


def _entities(candidate_id):
    return db.get_entities(candidate_id)


def _resume(skills, bullets):
    sec = ResumeSection(title="Projects",
                        bullets=[ResumeBullet(text=b) for b in bullets])
    r = TailoredResume(candidate=Candidate(name="X"), target_role="Data Engineer",
                       summary="Delivered results.", skills=skills, sections=[sec])
    from app.generation import render_markdown
    r.markdown = render_markdown(r)
    return r


def test_original_skill_supported(candidate_id):
    r = _resume(["PostgreSQL", "Python"], ["Built APIs with FastAPI"])
    report = validate_resume(r, _entities(candidate_id))
    statuses = {c.text: c.status for c in report.claims}
    assert statuses["Skill: PostgreSQL"] == ClaimStatus.SUPPORTED_BY_ORIGINAL
    assert report.unsupported == 0


def test_unsupported_skill_flagged(candidate_id):
    r = _resume(["Kubernetes"], ["Deployed with Kubernetes"])
    report = validate_resume(r, _entities(candidate_id))
    assert report.unsupported >= 1
    assert any(c.status == ClaimStatus.UNSUPPORTED for c in report.claims)


def test_confirmed_skill_marked_as_confirmation(candidate_id):
    # inject a user-confirmed skill and check provenance shows through
    db.insert_entity(KBEntity(candidate_id=candidate_id, entity_type=EntityType.skill,
                              name="Airflow", content="Airflow",
                              status=Status.USER_CONFIRMED))
    r = _resume(["Airflow"], ["Orchestrated pipelines with Airflow"])
    report = validate_resume(r, _entities(candidate_id))
    st = {c.text: c.status for c in report.claims}
    assert st["Skill: Airflow"] == ClaimStatus.SUPPORTED_BY_USER_CONFIRMATION


def test_invented_metric_flagged(candidate_id):
    r = _resume(["Python"], ["Did work"])
    r.summary = "Improved throughput by 250% across systems."
    r.markdown = r.summary
    report = validate_resume(r, _entities(candidate_id))
    assert any("250" in c.text for c in report.claims
               if c.status == ClaimStatus.UNSUPPORTED)


def test_ats_coverage_math():
    req = JDRequirements(required_skills=["python", "sql", "airflow", "spark"],
                         keywords=["python", "sql", "pipeline"])
    r = _resume(["Python", "SQL"], ["Built python sql pipeline"])
    validation = ValidationReport()
    report = ats_report(req, [], r, validation)
    assert report.skill_coverage == 0.5           # 2 of 4 required present
    assert "airflow" in report.missing_skills
    assert 0.0 <= report.overall_score <= 1.0
