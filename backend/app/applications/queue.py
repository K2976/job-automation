"""Application queue + worker (§5, §29, §30). Creates one task per selected opportunity
(never more than the batch max, no backfill), builds each task's fill context from V1/V2
artifacts, runs it through the runner, and — in the ONE place it happens — flips the
opportunity to APPLIED on a real submission. Tasks run serially (each is a browser process).

The page factory is injectable so tests drive the whole pipeline with FakePage and never
launch Chromium; the default is a real Playwright session."""
from __future__ import annotations

import os
import tempfile
from typing import Callable

from .. import db, export, matching
from ..models import (
    ApplicationStatus as St,
    ApplicationTask,
    ApprovalMode,
    OpportunityStatus,
    SUPPORTED_STATUSES,
    TERMINAL_STATUSES,
    TailoredResume,
)
from ..providers.llm import get_llm_provider
from . import field_mapper as fm, runner
from .page import BrowserPage
from .questions import FillContext

# A factory returns a context manager yielding a BrowserPage. Overridable in tests.
PageFactory = Callable[[], "object"]

# Test/worker override: set to a FakePage factory so the API pipeline runs with no browser.
# When None, a real Playwright session is used.
OVERRIDE_FACTORY: PageFactory | None = None


def _default_factory():
    from .playwright_page import playwright_session
    return playwright_session()


def _approval(mode_str: str) -> ApprovalMode:
    try:
        return ApprovalMode(mode_str)
    except ValueError:
        return ApprovalMode.REVIEW_BEFORE_SUBMIT


# --------------------------------------------------------------- task creation #
def create_tasks_for_batch(batch_id: int) -> list[ApplicationTask]:
    """One task per selected, package-ready opportunity — capped at the batch maximum, no
    backfill (§29). Idempotent: re-running reuses each opportunity's single task."""
    batch = db.get_batch(batch_id)
    if batch is None:
        raise KeyError(f"unknown batch {batch_id}")
    mode = _approval(batch.approval_mode)

    tasks: list[ApplicationTask] = []
    for oid in batch.opportunity_ids[: batch.max_opportunities]:   # hard cap
        opp = db.get_opportunity(oid)
        if opp is None or not opp.job_id:      # only package-ready opportunities
            continue
        task = db.get_task_for_opportunity(oid) or ApplicationTask(
            opportunity_id=oid, candidate_id=opp.candidate_id, batch_id=batch_id,
            application_url=opp.application_url)
        task.batch_id = batch_id
        task.approval_mode = mode              # inherit the batch mode (§10)
        task.application_url = opp.application_url
        task.id = db.upsert_task(task)
        tasks.append(task)
    return tasks


# ------------------------------------------------------------------- context #
def _evidence(opp) -> str:
    lines: list[str] = []
    for m in opp.matches:
        for e in m.evidence[:1]:
            lines.append(f"{e.name}: {e.snippet}")
    return "\n".join(dict.fromkeys(lines))[:1200]


def _render_resume_pdf(job_id: int) -> str:
    """Write the tailored résumé to a temp PDF using reportlab (always available — no LaTeX
    engine needed on the worker, §14). Returns the file path, or '' if not generated."""
    stored = db.get_generation(job_id)
    if not stored:
        return ""
    resume = TailoredResume.model_validate_json(stored)
    pdf = export.build_pdf(resume)
    fd, path = tempfile.mkstemp(prefix="resume_", suffix=".pdf")
    with os.fdopen(fd, "wb") as fh:
        fh.write(pdf)
    return path


def build_context(task: ApplicationTask, llm=None) -> FillContext:
    llm = llm or get_llm_provider()
    opp = db.get_opportunity(task.opportunity_id)
    candidate = db.get_candidate(task.candidate_id)
    entities = db.get_entities(task.candidate_id, statuses=SUPPORTED_STATUSES)
    return FillContext(
        candidate_values=fm.candidate_field_values(candidate),
        evidence=_evidence(opp), jd_text=opp.jd_text,
        supported_skills=matching.candidate_skill_set(entities),
        resume_artifact=_render_resume_pdf(opp.job_id) if opp.job_id else "",
        cover_letter=opp.cover_letter, llm=llm,
        role=(opp.requirements.role if opp.requirements else opp.title))


# ---------------------------------------------------------------- execution #
def execute(task_id: int, *, submit: bool, page_factory: PageFactory | None = None) -> ApplicationTask | None:
    task = db.get_task(task_id)
    if task is None or task.status in (St.PAUSED, St.CANCELLED):
        return task
    opp = db.get_opportunity(task.opportunity_id)
    if opp is None or not opp.job_id:
        task.status = St.FAILED
        task.error_code = "PACKAGE_NOT_READY"
        task.log("FAILED", "no prepared application package")
        db.save_task(task)
        return task

    # Defensive batch cap (§29): never submit beyond the maximum, even under races.
    if submit and task.batch_id:
        batch = db.get_batch(task.batch_id)
        if batch and db.count_submitted_tasks(task.batch_id) >= batch.max_opportunities:
            submit = False

    ctx = build_context(task)
    task.resume_artifact = ctx.resume_artifact
    factory = page_factory or OVERRIDE_FACTORY or _default_factory
    try:
        with factory() as page:                # isolated browser context per task (§6)
            runner.run_task(task, page, ctx, submit=submit)
    except Exception as e:  # noqa: BLE001 — any driver/browser failure is contained (§24)
        task.status = St.FAILED
        task.error_code = "RUNNER_ERROR"
        task.error_message = f"{type(e).__name__}: {e}"[:300]
        task.log("FAILED", type(e).__name__)
    finally:
        if ctx.resume_artifact and os.path.exists(ctx.resume_artifact):
            os.remove(ctx.resume_artifact)     # don't leave résumé PDFs on the worker

    db.save_task(task)
    _mark_applied_if_submitted(task)           # the ONE place APPLIED is set (§30)
    return task


def _mark_applied_if_submitted(task: ApplicationTask) -> None:
    if not runner.applied(task):
        return
    opp = db.get_opportunity(task.opportunity_id)
    if opp is not None and opp.status != OpportunityStatus.APPLIED:
        opp.status = OpportunityStatus.APPLIED
        db.save_opportunity(opp)


def execute_batch(batch_id: int, page_factory: PageFactory | None = None) -> None:
    """Run every task in a batch serially. submit is decided by each task's approval mode:
    only AUTONOMOUS submits automatically; MANUAL/REVIEW stop at REVIEW_REQUIRED."""
    for task in db.list_tasks(batch_id=batch_id):
        if task.status in TERMINAL_STATUSES or task.status in (St.PAUSED, St.CANCELLED):
            continue
        submit = task.approval_mode == ApprovalMode.AUTONOMOUS
        execute(task.id, submit=submit, page_factory=page_factory)
