from app import db, pipeline
from app.models import ApprovalAction, EntityType, Status
from app.planning import apply_approval


def _analyze(candidate_id):
    jd = (pipeline.FIXTURES / "jd_data_engineer.txt").read_text()
    return pipeline.analyze_job(candidate_id, jd)


def test_accept_transitions_to_confirmed(candidate_id):
    res = _analyze(candidate_id)
    add = next(s for s in res["plan"].suggestions if s.type.value == "ADD_SKILL")
    status = apply_approval(candidate_id, add.id, ApprovalAction.ACCEPT)
    assert status == Status.USER_CONFIRMED
    # a confirmed skill becomes real KB evidence — but never ORIGINAL
    skills = db.get_entities(candidate_id, entity_type=EntityType.skill,
                             statuses=[Status.USER_CONFIRMED])
    assert any(add.suggested.lower() in s.name.lower() for s in skills)


def test_reject_transitions_and_adds_nothing(candidate_id):
    res = _analyze(candidate_id)
    add = next(s for s in res["plan"].suggestions if s.type.value == "ADD_SKILL")
    before = len(db.get_entities(candidate_id))
    status = apply_approval(candidate_id, add.id, ApprovalAction.REJECT)
    assert status == Status.REJECTED
    assert len(db.get_entities(candidate_id)) == before   # nothing injected


def test_edit_transitions_to_user_edited(candidate_id):
    res = _analyze(candidate_id)
    add = next(s for s in res["plan"].suggestions if s.type.value == "ADD_SKILL")
    status = apply_approval(candidate_id, add.id, ApprovalAction.EDIT,
                            edited_text="Apache Spark")
    assert status == Status.USER_EDITED
    stored = {s.name for s in db.get_entities(candidate_id,
              entity_type=EntityType.skill, statuses=[Status.USER_EDITED])}
    assert "Apache Spark" in stored
