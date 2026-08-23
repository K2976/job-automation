"""Real-browser conformance: the SAME status outcomes the engine proved on FakePage, now
driven through PlaywrightPage against the local mock site. These cover the cases FakePage
cannot vouch for — multi-page re-inspection, real confirmation-page load (CONFIRMED vs
SUBMISSION_UNCERTAIN), CAPTCHA, login, unknown-required. Skipped if Chromium can't launch."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright")

from app.applications import runner
from app.applications.playwright_page import PlaywrightPage
from app.applications.questions import FillContext
from app.applications import field_mapper as fm
from app.models import (
    ApplicationStatus as St, ApplicationTask, ApprovalMode, Candidate,
)
from app.providers.llm import MockLLMProvider

SITE = Path(__file__).parent / "fixtures" / "app_site"
CAND = Candidate(name="Kartik Sanghi", email="k@example.com", phone="+91 99999 00000",
                 location="Bengaluru, India",
                 links=["https://linkedin.com/in/kartik", "https://github.com/kartik"])


@pytest.fixture(scope="module")
def _browser():
    from playwright.sync_api import sync_playwright
    pw = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
    except Exception as e:  # noqa: BLE001
        if pw:
            pw.stop()
        pytest.skip(f"Chromium not launchable here: {e}")
    yield browser
    browser.close()
    pw.stop()


@pytest.fixture
def page(_browser):
    ctx = _browser.new_context()          # isolated per application (§6)
    yield PlaywrightPage(ctx.new_page())
    ctx.close()


@pytest.fixture(scope="module")
def resume_pdf(tmp_path_factory):
    p = tmp_path_factory.mktemp("artifact") / "resume.pdf"
    p.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    return str(p)


def _ctx(resume_pdf) -> FillContext:
    return FillContext(
        candidate_values=fm.candidate_field_values(CAND),
        evidence="Backend API: Built FastAPI services with PostgreSQL and REST endpoints",
        jd_text="Backend Engineer. Python, FastAPI, PostgreSQL.",
        supported_skills={"python", "fastapi", "postgresql", "rest", "sql", "backend", "api"},
        resume_artifact=resume_pdf, cover_letter="Dear team, ...",
        llm=MockLLMProvider(), role="Backend Engineer")


def _run(name, page, resume_pdf, *, mode=ApprovalMode.AUTONOMOUS, submit=True):
    task = ApplicationTask(opportunity_id=1, candidate_id=1, approval_mode=mode,
                           application_url=(SITE / name).as_uri())
    return runner.run_task(task, page, _ctx(resume_pdf), submit=submit)


def test_basic_form_confirms(page, resume_pdf):
    t = _run("basic.html", page, resume_pdf)
    assert t.status == St.CONFIRMED and runner.applied(t)


def test_manual_mode_reviews_not_submits(page, resume_pdf):
    t = _run("basic.html", page, resume_pdf, mode=ApprovalMode.MANUAL, submit=False)
    assert t.status == St.REVIEW_REQUIRED and not runner.applied(t)


def test_deterministic_values_land_in_correct_dom_fields(page, resume_pdf):
    """The driver's key→element mapping puts each value in the RIGHT box (a first/last swap
    or email-in-phone would submit fine and pass every status test — this is the only guard).
    Runs in review mode so the filled form is still on screen to read back."""
    _run("basic.html", page, resume_pdf, mode=ApprovalMode.MANUAL, submit=False)
    assert page.page.get_by_label("First Name").input_value() == "Kartik"
    assert page.page.get_by_label("Last Name").input_value() == "Sanghi"
    assert page.page.get_by_label("Email").input_value() == "k@example.com"
    assert "linkedin.com" in page.page.get_by_label("LinkedIn").input_value()


def test_multi_page_confirms(page, resume_pdf):
    t = _run("page1.html", page, resume_pdf)
    assert t.status == St.CONFIRMED and t.current_page == 1


def test_semantic_question_filled_and_confirms(page, resume_pdf):
    t = _run("semantic.html", page, resume_pdf)
    assert t.status == St.CONFIRMED
    why = next(q for q in t.questions if q.name == "why")
    assert why.answer_source.value == "LLM_GENERATED" and why.answer


def test_captcha_blocks(page, resume_pdf):
    t = _run("captcha.html", page, resume_pdf)
    assert t.status == St.BLOCKED and t.error_code == "CAPTCHA" and not runner.applied(t)


def test_login_required(page, resume_pdf):
    t = _run("login.html", page, resume_pdf)
    assert t.status == St.LOGIN_REQUIRED


def test_unknown_required_pauses(page, resume_pdf):
    t = _run("unknown_required.html", page, resume_pdf)
    assert t.status == St.USER_ACTION_REQUIRED


def test_high_impact_pauses(page, resume_pdf):
    t = _run("highimpact.html", page, resume_pdf)
    assert t.status == St.USER_ACTION_REQUIRED and not runner.applied(t)


def test_submission_uncertain_without_confirmation(page, resume_pdf):
    t = _run("uncertain.html", page, resume_pdf)
    assert t.status == St.SUBMISSION_UNCERTAIN and not runner.applied(t)
