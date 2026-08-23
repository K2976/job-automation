"""V3 HTTP surface — the application queue and its controls (§34, §35). Thin, like the V1/V2
routers. Long-running browser work runs in a BackgroundTask (Starlette runs sync tasks in a
threadpool, so sync Playwright is safe); endpoints return immediately and the UI polls."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from . import db
from .applications import queue
from .applications.runner import can_submit
from .applications.state_machine import IllegalTransition, transition
from .models import (
    AnswerSource,
    ApplicationStatus as St,
    ApplicationTask,
    ApprovalMode,
)

router = APIRouter(prefix="/api", tags=["applications"])
MAX_RETRIES = 2


def _task_or_404(task_id: int) -> ApplicationTask:
    task = db.get_task(task_id)
    if task is None:
        raise HTTPException(404, "application task not found")
    return task


def _summary(task: ApplicationTask) -> dict:
    """Structured pre-submit summary (§27)."""
    by_source: dict[str, int] = {}
    for q in task.questions:
        by_source[q.answer_source.value] = by_source.get(q.answer_source.value, 0) + 1
    unresolved = [q.question_text for q in task.questions
                  if q.required and (q.requires_review or not q.answer)]
    return {
        "questions": len(task.questions),
        "deterministic": by_source.get("CANDIDATE_PROFILE", 0)
        + by_source.get("DETERMINISTIC_RULE", 0) + by_source.get("APPLICATION_PACKAGE", 0),
        "llm_generated": by_source.get("LLM_GENERATED", 0),
        "user_provided": by_source.get("USER_PROVIDED", 0),
        "unresolved": len(unresolved),
        "unresolved_questions": unresolved,
        "can_submit": can_submit(task),
        "status": task.status.value,
        "approval_mode": task.approval_mode.value,
    }


# ---------------------------------------------------------------- queue mgmt #
class ModeIn(BaseModel):
    approval_mode: ApprovalMode = ApprovalMode.REVIEW_BEFORE_SUBMIT


@router.post("/batches/{batch_id}/applications")
def create_applications(batch_id: int, body: ModeIn) -> dict:
    """Create one application task per prepared opportunity in the batch (≤ max, §29)."""
    batch = db.get_batch(batch_id)
    if batch is None:
        raise HTTPException(404, "batch not found")
    batch.approval_mode = body.approval_mode.value
    db.save_batch(batch)
    tasks = queue.create_tasks_for_batch(batch_id)
    return {"tasks": tasks, "count": len(tasks), "max_opportunities": batch.max_opportunities}


@router.get("/batches/{batch_id}/applications")
def list_batch_applications(batch_id: int) -> dict:
    return {"tasks": db.list_tasks(batch_id=batch_id)}


@router.get("/candidates/{candidate_id}/applications")
def list_applications(candidate_id: int) -> dict:
    """The application history / tracker across all batches (§32)."""
    return {"tasks": db.list_tasks(candidate_id=candidate_id)}


@router.get("/applications/{task_id}")
def get_application(task_id: int) -> dict:
    task = _task_or_404(task_id)
    return {"task": task, "summary": _summary(task)}


@router.get("/applications/{task_id}/summary")
def application_summary(task_id: int) -> dict:
    return _summary(_task_or_404(task_id))


# -------------------------------------------------------------- run controls #
@router.post("/applications/{task_id}/start")
def start_application(task_id: int, background: BackgroundTasks) -> dict:
    task = _task_or_404(task_id)
    submit = task.approval_mode == ApprovalMode.AUTONOMOUS
    background.add_task(queue.execute, task_id, submit=submit)
    return {"task_id": task_id, "started": True, "will_submit": submit}


@router.post("/batches/{batch_id}/applications/start")
def start_batch(batch_id: int, background: BackgroundTasks) -> dict:
    if db.get_batch(batch_id) is None:
        raise HTTPException(404, "batch not found")
    background.add_task(queue.execute_batch, batch_id)
    return {"batch_id": batch_id, "started": True}


@router.post("/applications/{task_id}/approve")
def approve_application(task_id: int, background: BackgroundTasks) -> dict:
    """Approve & submit a REVIEW_BEFORE_SUBMIT task sitting at REVIEW_REQUIRED (§28). MANUAL
    tasks are never submitted programmatically — the user submits on the site themselves."""
    task = _task_or_404(task_id)
    if task.approval_mode != ApprovalMode.REVIEW_BEFORE_SUBMIT:
        raise HTTPException(409, "only REVIEW_BEFORE_SUBMIT tasks can be approved for submit")
    if task.status != St.REVIEW_REQUIRED:
        raise HTTPException(409, f"task is {task.status.value}, not REVIEW_REQUIRED")
    background.add_task(queue.execute, task_id, submit=True)
    return {"task_id": task_id, "submitting": True}


class AnswersIn(BaseModel):
    answers: dict[str, str]          # field name → answer


@router.post("/applications/{task_id}/answers")
def provide_answers(task_id: int, body: AnswersIn) -> ApplicationTask:
    """Supply answers to questions the agent paused on (§11), then re-queue for a re-drive
    (which carries these USER_PROVIDED answers over)."""
    task = _task_or_404(task_id)
    for q in task.questions:
        if q.name in body.answers or q.question_text in body.answers:
            q.answer = body.answers.get(q.name) or body.answers.get(q.question_text, "")
            q.answer_source = AnswerSource.USER_PROVIDED
            q.requires_review = False
    if task.status in (St.USER_ACTION_REQUIRED, St.LOGIN_REQUIRED, St.REVIEW_REQUIRED):
        task.status = St.QUEUED
    db.save_task(task)
    return task


class ActionIn(BaseModel):
    action: str                      # pause | resume | cancel | skip | retry


@router.post("/applications/{task_id}/action")
def control(task_id: int, body: ActionIn, background: BackgroundTasks) -> dict:
    """Queue controls (§35). Retries are bounded and respect the state machine."""
    task = _task_or_404(task_id)
    act = body.action.lower()
    try:
        if act == "pause":
            transition(task, St.PAUSED)
        elif act == "resume":
            transition(task, St.QUEUED)
        elif act == "cancel":
            transition(task, St.CANCELLED)
        elif act == "skip":
            transition(task, St.CANCELLED)
            opp = db.get_opportunity(task.opportunity_id)
            if opp is not None:
                from .models import OpportunityStatus
                opp.status = OpportunityStatus.SKIPPED
                db.save_opportunity(opp)
        elif act == "retry":
            if task.retry_count >= MAX_RETRIES:
                raise HTTPException(409, f"retry limit ({MAX_RETRIES}) reached")
            transition(task, St.QUEUED)      # FAILED/BLOCKED → QUEUED
            task.retry_count += 1
            db.save_task(task)
            submit = task.approval_mode == ApprovalMode.AUTONOMOUS
            background.add_task(queue.execute, task_id, submit=submit)
            return {"task_id": task_id, "retrying": True, "retry_count": task.retry_count}
        else:
            raise HTTPException(400, f"unknown action {act!r}")
    except IllegalTransition as e:
        raise HTTPException(409, str(e))
    db.save_task(task)
    return {"task_id": task_id, "status": task.status.value}


@router.post("/applications/{task_id}/approval-mode")
def set_mode(task_id: int, body: ModeIn) -> ApplicationTask:
    task = _task_or_404(task_id)
    task.approval_mode = body.approval_mode
    db.save_task(task)
    return task
