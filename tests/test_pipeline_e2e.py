"""End-to-end + lightweight RAG evaluation: the fixture profile against both JDs,
asserting expected evidence, gaps and role positioning (CLAUDE.md §29)."""
from app import pipeline
from app.models import ApprovalAction, ClaimStatus, MatchStatus
from app.planning import apply_approval


def _statuses(matches):
    return {m.requirement: m.match_status for m in matches}


def test_data_engineer_flow(candidate_id):
    jd = (pipeline.FIXTURES / "jd_data_engineer.txt").read_text()
    res = pipeline.analyze_job(candidate_id, jd)
    st = _statuses(res["matches"])

    # expected strong evidence for this candidate
    for skill in ("python", "sql", "postgresql"):
        assert st.get(skill) == MatchStatus.STRONG_MATCH
    # expected genuine gaps
    for skill in ("airflow", "spark", "etl"):
        assert st.get(skill) == MatchStatus.MISSING

    # data/backend projects should be ranked above the pure-UI library
    assert res["plan"].reorder[0] in ("Parkezy", "Setu AI")
    assert res["plan"].reorder[-1] == "PortfolioKit"

    gen = pipeline.generate_for_job(res["job_id"])
    assert gen["resume"].candidate.name == "Kartik Sanghi"
    # no original skill should ever be flagged unsupported
    assert gen["validation"].unsupported == 0
    # tailoring omits iOS-only skills from the skills line (they aren't JD-relevant)
    tailored_skills = {s.lower() for s in gen["resume"].skills}
    assert "swiftui" not in tailored_skills and "swift" not in tailored_skills
    # and the comparison surfaces master-only skills as dropped
    assert gen["comparison"]["skills_dropped"]


def test_second_jd_for_same_candidate_does_not_collide(candidate_id):
    """Regression: the same candidate must be able to analyze multiple JDs. Suggestion
    ids are job-scoped so the second analysis doesn't hit a UNIQUE constraint."""
    de = (pipeline.FIXTURES / "jd_data_engineer.txt").read_text()
    ai = (pipeline.FIXTURES / "jd_ai_engineer.txt").read_text()
    r1 = pipeline.analyze_job(candidate_id, de)
    r2 = pipeline.analyze_job(candidate_id, ai)   # must not raise
    assert r1["job_id"] != r2["job_id"]
    ids1 = {s.id for s in r1["plan"].suggestions}
    ids2 = {s.id for s in r2["plan"].suggestions}
    assert not (ids1 & ids2)                       # globally unique across jobs


def test_ai_engineer_gives_different_view(candidate_id):
    jd = (pipeline.FIXTURES / "jd_ai_engineer.txt").read_text()
    res = pipeline.analyze_job(candidate_id, jd)
    st = _statuses(res["matches"])
    assert st.get("python") == MatchStatus.STRONG_MATCH
    # Setu AI (edge-AI / CNN) should now be a top-ranked project
    assert "Setu AI" in res["plan"].reorder[:2]


def test_missing_skill_requires_approval_not_fabricated(candidate_id):
    jd = (pipeline.FIXTURES / "jd_data_engineer.txt").read_text()
    res = pipeline.analyze_job(candidate_id, jd)
    # airflow is missing -> generation without approval must not claim it
    gen = pipeline.generate_for_job(res["job_id"])
    assert "airflow" not in [s.lower() for s in gen["resume"].skills]

    # after the candidate confirms it, it appears — but as confirmation, not original
    add = next(s for s in res["plan"].suggestions if s.target == "airflow")
    apply_approval(candidate_id, add.id, ApprovalAction.ACCEPT)
    gen2 = pipeline.generate_for_job(res["job_id"])
    airflow_claim = next((c for c in gen2["validation"].claims
                          if c.text == "Skill: Airflow"), None)
    assert airflow_claim is not None
    assert airflow_claim.status == ClaimStatus.SUPPORTED_BY_USER_CONFIRMATION
