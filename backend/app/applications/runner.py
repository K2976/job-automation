"""The application runner (§2, §19-§31): a deterministic-first orchestrator over the
BrowserPage protocol. It is pure over (task, page, context) — no DB, no Playwright import —
so it runs identically against FakePage (tests) and PlaywrightPage (real).

All three approval modes share ONE fill+validate path and differ only in the terminal
action: MANUAL/REVIEW stop at REVIEW_REQUIRED; AUTONOMOUS submits iff `can_submit` passes.
APPLIED on the opportunity is owned by the worker and gated on APPLIED_STATUSES (§30) —
never here."""
from __future__ import annotations

from ..models import (
    APPLIED_STATUSES,
    TERMINAL_STATUSES,
    ApplicationStatus as St,
    ApplicationTask,
    ApprovalMode,
    FieldType,
)
from .page import BrowserPage, CONTINUE, SUBMIT
from .questions import FillContext, classify, field_label, unresolved
from .state_machine import transition

MAX_PAGES = 12  # ponytail: hard page cap so a mis-detected form can't loop forever

_CONFIRM_MARKERS = (
    "application submitted", "thanks for applying", "thank you for applying",
    "application received", "successfully applied", "we have received your application",
    "application complete", "your application has been submitted",
)


def can_submit(task: ApplicationTask) -> bool:
    """The single autonomous-submit predicate (§28): every required question resolved, none
    flagged for review, and the task not blocked/awaiting a human. Evaluated once, shared by
    every mode — there is no separate autonomous path that could skip a check."""
    if task.status in (St.BLOCKED, St.LOGIN_REQUIRED, St.USER_ACTION_REQUIRED):
        return False
    for q in task.questions:
        if q.requires_review:
            return False
        if q.required and not q.answer:
            return False
    return True


def _apply(page: BrowserPage, q) -> str:
    """Fill one resolved answer; return the log event name (never the value)."""
    t = q.field_type
    if t == FieldType.file:
        page.upload(q.field_key, q.answer)
        return "FILE_UPLOADED"
    if t == FieldType.select:
        page.select(q.field_key, q.answer)
    elif t in (FieldType.checkbox, FieldType.radio):
        # "true" is the only checked signal (not bare truthiness — "false"/"no" strings
        # must NOT check the box). Each radio <input> is its own field/key here (§1), so
        # checking it is correct and relies on native radio-group exclusivity in the DOM
        # rather than Playwright's select_option(), which only works on <select>.
        page.check(q.field_key, q.answer == "true")
    else:
        page.fill(q.field_key, q.answer)
    return "FIELD_FILLED"


def _detect_confirmation(page: BrowserPage) -> str | None:
    low = page.page_text().lower()
    for m in _CONFIRM_MARKERS:
        if m in low:
            return m
    return None


def run_task(task: ApplicationTask, page: BrowserPage, ctx: FillContext, *,
             submit: bool = False) -> ApplicationTask:
    """Drive one application. `submit=True` permits an actual submission (autonomous mode,
    or an approved review); it still only submits when `can_submit` passes."""
    from ..models import AnswerSource, _now
    # A run is a fresh attempt: a re-drive (approve→submit, or retry) re-opens and re-fills.
    # Terminal tasks are never re-driven.
    if task.status in TERMINAL_STATUSES:
        return task
    # Carry over answers that must NOT be regenerated across a re-drive: a user's answer to
    # a high-impact/unknown question (else it's lost and re-flagged), and an LLM answer the
    # user already reviewed (else REVIEW_BEFORE_SUBMIT would submit different text — §27, §15).
    # A blank (name or question_text) is never a safe cross-run identity — several unrelated
    # fields on the same page can share it, and reusing it has handed one field's answer to a
    # completely different (and differently-typed) field on the next drive, e.g. a "No" typed
    # for a radio question ending up as a file upload path (§18).
    prior = {(q.name or q.question_text): q for q in task.questions
             if (q.name or q.question_text) and q.answer
             and q.answer_source in (AnswerSource.USER_PROVIDED, AnswerSource.LLM_GENERATED)}
    task.status = St.READY
    task.questions = []
    task.current_page = 0
    task.error_code = task.error_message = ""

    task.started_at = task.started_at or _now()
    task.log("TASK_STARTED", f"mode={task.approval_mode.value}")

    transition(task, St.QUEUED)
    transition(task, St.OPENING)
    page.goto(task.application_url)
    task.log("PAGE_OPENED", task.application_url)

    for _ in range(MAX_PAGES):
        if page.captcha_present():                       # §22 — stop, never bypass
            transition(task, St.BLOCKED)
            task.error_code = "CAPTCHA"
            task.log("CAPTCHA_DETECTED")
            return _finish(task)
        if page.login_required():                        # §25
            transition(task, St.LOGIN_REQUIRED)
            task.error_code = "LOGIN_REQUIRED"
            task.log("USER_INTERVENTION_REQUIRED", "login required")
            return _finish(task)

        transition(task, St.INSPECTING)
        fields = page.inspect()
        task.log("FORM_DETECTED", f"page {task.current_page}: {len(fields)} fields")
        transition(task, St.FILLING)

        page_questions = []
        for fd in fields:
            if fd.field_type == FieldType.button:
                continue
            # Must mirror `prior`'s own key exactly: name first (matching `q.name or
            # q.question_text` above), then the same label/fallback questions.py computes for
            # question_text — a bare `fd.name or fd.label` never matches a blank-labeled
            # field's stored fallback text and silently drops its carried-over answer on every
            # re-drive (§18).
            saved = prior.get(fd.name or field_label(fd))
            # Require the field type to still match — the same name/label reused for a
            # different kind of control (e.g. a fresh page layout) must be reclassified,
            # not blindly filled with an answer meant for something else.
            if saved is not None and saved.field_type == fd.field_type:
                q = saved.model_copy(update={"field_key": fd.key})
            else:
                q = classify(fd, ctx)
            task.questions.append(q)
            page_questions.append(q)
            if q.answer and not q.requires_review:
                try:
                    event = _apply(page, q)
                except Exception as e:  # noqa: BLE001 — one uncooperative field (e.g. a
                    # hidden mirror input behind a rich-text widget) must not crash the whole
                    # task (§11); fall back to the same "ask the human" path an unmapped
                    # field takes, instead of losing all progress made on this page.
                    q.answer = ""
                    q.requires_review = True
                    q.reason = f"Could not fill this field: {type(e).__name__}."
                    task.log("FIELD_FILL_FAILED", f"{q.name or q.question_text[:40]}: {type(e).__name__}")
                else:
                    task.log(event, q.name or q.question_text[:40])
                    if q.answer_source.value == "LLM_GENERATED":
                        task.log("QUESTION_GENERATED", q.name or q.question_text[:40])

        # A required question we can't safely answer stops the task (§11).
        blocking = unresolved(page_questions)
        if blocking:
            transition(task, St.USER_ACTION_REQUIRED)
            task.error_code = "NEEDS_INPUT"
            task.log("USER_INTERVENTION_REQUIRED",
                     "; ".join(q.question_text[:40] for q in blocking[:3]))
            return _finish(task)

        # Advance a multi-page form, or move to the submission decision.
        if page.find_control([SUBMIT]) is None and page.find_control([CONTINUE]):
            page.click(page.find_control([CONTINUE]))
            task.current_page += 1
            task.log("PAGE_OPENED", f"page {task.current_page}")
            continue
        break
    else:
        transition(task, St.FAILED)
        task.error_code = "TOO_MANY_PAGES"
        return _finish(task)

    submit_key = page.find_control([SUBMIT])
    if submit_key is None:
        transition(task, St.FAILED)
        task.error_code = "NO_SUBMIT_CONTROL"
        task.log("FAILED", "no submit control found")
        return _finish(task)

    # Terminal action — the ONLY place the modes diverge.
    if not (submit and can_submit(task)):
        transition(task, St.REVIEW_REQUIRED)
        task.log("READY_FOR_REVIEW",
                 f"{len(task.questions)} questions; can_submit={can_submit(task)}")
        return _finish(task)

    return _submit(task, page, submit_key)


def _submit(task: ApplicationTask, page: BrowserPage, submit_key: str) -> ApplicationTask:
    from ..models import _now
    page.click(submit_key)
    transition(task, St.SUBMITTED)
    task.submitted_at = _now()
    task.log("SUBMITTED")

    marker = _detect_confirmation(page)
    if marker:
        transition(task, St.CONFIRMED)
        task.confirmation_reference = marker
        task.log("CONFIRMATION_DETECTED", marker)
    else:
        transition(task, St.SUBMISSION_UNCERTAIN)   # never falsely mark success (§31)
        task.log("SUBMISSION_UNCERTAIN", "no confirmation text found")
    return _finish(task)


def _finish(task: ApplicationTask) -> ApplicationTask:
    from ..models import _now
    if task.status in APPLIED_STATUSES or task.status in (
            St.SUBMISSION_UNCERTAIN, St.FAILED, St.BLOCKED):
        task.finished_at = task.finished_at or _now()
    return task


def applied(task: ApplicationTask) -> bool:
    """Whether this task should flip Opportunity → APPLIED (§30). SUBMITTED/CONFIRMED only."""
    return task.status in APPLIED_STATUSES
