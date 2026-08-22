"""V3 engine, fully browser-free (FakePage + MockLLM). Proves every safety decision:
state machine, field mapping, question classification, all three approval modes, high-impact
pause, CAPTCHA→BLOCKED, login, multi-page, confirmation, submission-uncertain, APPLIED
wiring. This is the checkpoint before any Playwright code exists."""
from __future__ import annotations

import pytest

from app.applications import field_mapper as fm
from app.applications import runner
from app.applications.page import FakePage
from app.applications.questions import FillContext, classify
from app.applications.state_machine import IllegalTransition, can, transition
from app.applications.page import FieldDescriptor
from app.models import (
    ApplicationStatus as St, ApplicationTask, ApprovalMode, Candidate, FieldType,
)
from app.providers.llm import MockLLMProvider

CAND = Candidate(name="Kartik Sanghi", email="k@example.com", phone="+91 99999 00000",
                 location="Bengaluru, India",
                 links=["https://linkedin.com/in/kartik", "https://github.com/kartik"])


def _ctx(**kw) -> FillContext:
    base = dict(candidate_values=fm.candidate_field_values(CAND),
                evidence="Backend API: Built FastAPI services with PostgreSQL",
                jd_text="Backend Engineer. Python, FastAPI, PostgreSQL.",
                supported_skills={"python", "fastapi", "postgresql", "rest", "sql"},
                resume_artifact="/tmp/resume.pdf", cover_letter="Dear team, ...",
                llm=MockLLMProvider(), role="Backend Engineer")
    base.update(kw)
    return FillContext(**base)


def _task(mode=ApprovalMode.REVIEW_BEFORE_SUBMIT) -> ApplicationTask:
    return ApplicationTask(opportunity_id=1, candidate_id=1, batch_id=1,
                           application_url="file:///app.html", approval_mode=mode)


# ------------------------------------------------------------ state machine #
def test_state_machine_rejects_illegal_transition():
    t = _task()
    assert can(St.READY, St.QUEUED)
    assert not can(St.READY, St.SUBMITTED)
    with pytest.raises(IllegalTransition):
        transition(t, St.SUBMITTED)


def test_confirmed_is_terminal():
    assert can(St.SUBMITTED, St.CONFIRMED)
    from app.applications.state_machine import _LEGAL
    assert _LEGAL[St.CONFIRMED] == set()


# --------------------------------------------------------------- field map #
def test_field_mapper_aliases_and_seniority_of_name():
    assert fm.map_field("First Name") == fm.FIRST_NAME
    assert fm.map_field("Surname") == fm.LAST_NAME
    assert fm.map_field("Full name") == fm.FULL_NAME     # "name" alone → full_name
    assert fm.map_field("Email Address") == fm.EMAIL
    assert fm.map_field("LinkedIn Profile") == fm.LINKEDIN
    assert fm.map_field("Favorite color") is None


def test_candidate_values_derives_name_and_links():
    v = fm.candidate_field_values(CAND)
    assert v[fm.FIRST_NAME] == "Kartik" and v[fm.LAST_NAME] == "Sanghi"
    assert "linkedin.com" in v[fm.LINKEDIN] and "github.com" in v[fm.GITHUB]
    assert v[fm.CITY] == "Bengaluru"


# ----------------------------------------------------------- classification #
def _fd(label, ftype="text", required=False, name="", options=None):
    return FieldDescriptor(key="k", label=label, name=name, field_type=FieldType(ftype),
                           required=required, options=options or [])


def test_classify_deterministic_identity():
    q = classify(_fd("Email", "email", True), _ctx())
    assert q.answer == "k@example.com"
    assert q.answer_source.value == "CANDIDATE_PROFILE" and not q.requires_review


def test_classify_resume_upload_uses_package_artifact():
    q = classify(_fd("Resume", "file", True), _ctx())
    assert q.answer == "/tmp/resume.pdf" and q.answer_source.value == "APPLICATION_PACKAGE"


def test_classify_high_impact_pauses_even_with_answer_available():
    for label in ["Expected salary", "Are you authorized to work in the US?",
                  "Are you willing to relocate?", "Gender"]:
        q = classify(_fd(label, "text", True), _ctx())
        assert q.requires_review, label
        assert q.answer_source.value == "UNRESOLVED"


def test_classify_semantic_question_uses_llm_and_validates():
    q = classify(_fd("Why are you interested in this role?", "textarea", True), _ctx())
    assert q.answer and q.answer_source.value == "LLM_GENERATED"
    assert not q.requires_review


def test_classify_semantic_answer_with_no_evidence_flags_review():
    q = classify(_fd("Describe your experience", "textarea", True), _ctx(evidence=""))
    assert q.requires_review and not q.answer


def test_classify_unknown_required_dropdown_needs_review():
    q = classify(_fd("Team", "select", True, options=["A", "B"]), _ctx())
    assert q.requires_review


# ------------------------------------------------------------------ runner #
def _basic_form(control="submit", confirmation="Application submitted"):
    return [{"fields": [
        {"label": "First Name", "name": "first", "type": "text", "required": True},
        {"label": "Email", "name": "email", "type": "email", "required": True},
        {"label": "Resume", "name": "resume", "type": "file", "required": True},
    ], "control": control, "confirmation": confirmation}]


def test_manual_mode_fills_but_never_submits():
    page = FakePage(_basic_form())
    t = run_it(_task(ApprovalMode.MANUAL), page, submit=False)
    assert t.status == St.REVIEW_REQUIRED
    assert not page.submitted
    assert page.values and page.uploads       # it really filled + uploaded


def test_review_mode_stops_at_review_then_approve_submits():
    t = _task(ApprovalMode.REVIEW_BEFORE_SUBMIT)
    run_it(t, FakePage(_basic_form()), submit=False)
    assert t.status == St.REVIEW_REQUIRED
    # user approves → re-run with submit=True on a fresh page
    page2 = FakePage(_basic_form())
    run_it(t, page2, submit=True)
    assert t.status == St.CONFIRMED and page2.submitted
    assert runner.applied(t)


def test_autonomous_submits_and_confirms():
    page = FakePage(_basic_form())
    t = run_it(_task(ApprovalMode.AUTONOMOUS), page, submit=True)
    assert t.status == St.CONFIRMED and runner.applied(t)


def test_autonomous_with_unresolved_question_does_not_submit():
    form = [{"fields": [
        {"label": "Email", "name": "email", "type": "email", "required": True},
        {"label": "Expected salary", "name": "salary", "type": "text", "required": True},
    ], "control": "submit"}]
    page = FakePage(form)
    t = run_it(_task(ApprovalMode.AUTONOMOUS), page, submit=True)
    assert t.status == St.USER_ACTION_REQUIRED      # high-impact pause beats autonomous
    assert not page.submitted and not runner.applied(t)


def test_captcha_blocks_and_never_submits():
    page = FakePage([{"fields": [], "captcha": True, "control": "submit"}])
    t = run_it(_task(ApprovalMode.AUTONOMOUS), page, submit=True)
    assert t.status == St.BLOCKED and t.error_code == "CAPTCHA"
    assert not page.submitted and not runner.applied(t)
    assert any(e.event == "CAPTCHA_DETECTED" for e in t.logs)


def test_login_required_pauses():
    page = FakePage([{"fields": [], "login": True, "control": "submit"}])
    t = run_it(_task(), page, submit=True)
    assert t.status == St.LOGIN_REQUIRED and not page.submitted


def test_multi_page_form():
    form = [
        {"fields": [{"label": "First Name", "name": "first", "type": "text", "required": True}],
         "control": "continue"},
        {"fields": [{"label": "Email", "name": "email", "type": "email", "required": True}],
         "control": "submit", "confirmation": "Thanks for applying"},
    ]
    page = FakePage(form)
    t = run_it(_task(ApprovalMode.AUTONOMOUS), page, submit=True)
    assert t.status == St.CONFIRMED and t.current_page == 1
    assert len(t.questions) == 2


def test_submission_uncertain_when_no_confirmation():
    page = FakePage(_basic_form(confirmation=""))    # submit yields no confirmation text
    t = run_it(_task(ApprovalMode.AUTONOMOUS), page, submit=True)
    assert t.status == St.SUBMISSION_UNCERTAIN
    assert not runner.applied(t)                     # must NOT count as applied (§31)


def run_it(task, page, *, submit):
    return runner.run_task(task, page, _ctx(), submit=submit)
