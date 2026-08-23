"""Remote browser-worker channel (§13-§18). The public API creates/stores tasks; the
MacBook worker reaches IN over HTTPS to claim and update them — the worker never listens on
a port (§8). Everything here is behind a shared bearer token (§13) and, per task, an
ownership check so a worker can only touch the task it actually claimed (§14, §30).

The API service imports this WITHOUT importing Playwright — it only reads/writes task state
and proxies LLM calls; Chromium lives only on the worker (§5, §28)."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel

from . import db, export
from .applications import queue
from .applications.runner import applied
from .config import settings
from .models import (
    ApplicationStatus as St,
    ApplicationTask,
    ApplicationQuestion,
    FillContextBundle,
    OpportunityStatus,
    TailoredResume,
    TaskEvent,
    WORKER_REPORTABLE_STATUSES,
    _now,
)

router = APIRouter(prefix="/worker", tags=["worker"])


# --------------------------------------------------------------------- auth #
def require_worker(authorization: str = Header(default="")) -> None:
    """Fail closed: no configured token ⇒ the whole channel is refused (§13). Constant-time
    compare so the token can't be guessed by timing."""
    if not settings.worker_auth_token:
        raise HTTPException(503, "worker channel not configured")
    prefix = "Bearer "
    presented = authorization[len(prefix):] if authorization.startswith(prefix) else ""
    if not (presented and hmac.compare_digest(presented, settings.worker_auth_token)):
        raise HTTPException(401, "invalid worker credentials")


def _owned(task_id: int, worker_id: str) -> ApplicationTask:
    """The task must exist AND be owned by this worker — blocks touching unrelated/unclaimed
    records (§14 security). 409 (not 404) so a lost race is distinguishable from a bad id."""
    task = db.get_task(task_id)
    if task is None:
        raise HTTPException(404, "task not found")
    if task.worker_id != worker_id:
        raise HTTPException(409, "task is not owned by this worker")
    return task


# ------------------------------------------------------------------- claim #
class ClaimIn(BaseModel):
    worker_id: str


class ClaimOut(BaseModel):
    task: ApplicationTask
    context: FillContextBundle
    submit: bool


@router.post("/tasks/claim", dependencies=[Depends(require_worker)])
def claim_task(body: ClaimIn, response: Response) -> ClaimOut | None:
    """Atomically claim one QUEUED task (§15). 204 when the queue is empty so the worker
    just backs off (§16)."""
    task, submit = db.claim_next_task(
        body.worker_id, heartbeat_timeout=settings.worker_heartbeat_timeout,
        stale_grace=settings.worker_stale_grace)
    if task is None:
        response.status_code = 204
        return None
    db.upsert_worker(body.worker_id, status="busy", current_task_id=task.id)
    return ClaimOut(task=task, context=queue.build_context_bundle(task), submit=submit)


# --------------------------------------------------------------- heartbeat #
class HeartbeatIn(BaseModel):
    worker_id: str
    status: str = "idle"                     # idle | busy
    current_task_id: int | None = None


@router.post("/heartbeat", dependencies=[Depends(require_worker)])
def heartbeat(body: HeartbeatIn) -> dict:
    """Liveness ping — sent whether idle or busy so the badge shows Online even between
    tasks (§17). Never carries worker secrets back out."""
    db.upsert_worker(body.worker_id, status=body.status,
                     current_task_id=body.current_task_id)
    return {"ok": True, "heartbeat_timeout": settings.worker_heartbeat_timeout}


@router.post("/tasks/{task_id}/heartbeat", dependencies=[Depends(require_worker)])
def task_heartbeat(task_id: int, body: ClaimIn) -> dict:
    _owned(task_id, body.worker_id)
    db.upsert_worker(body.worker_id, status="busy", current_task_id=task_id)
    return {"ok": True}


# ------------------------------------------------------------------ events #
class EventsIn(BaseModel):
    worker_id: str
    events: list[TaskEvent]


@router.post("/tasks/{task_id}/events", dependencies=[Depends(require_worker)])
def report_events(task_id: int, body: EventsIn) -> dict:
    """Append progress log lines so the UI can show live activity. Field NAMES only — the
    worker never sends values/secrets (§38)."""
    task = _owned(task_id, body.worker_id)
    task.logs.extend(body.events)
    db.save_task(task)
    return {"ok": True, "logs": len(task.logs)}


# ---------------------------------------------------------------- complete #
class CompleteIn(BaseModel):
    """What the worker reports after a run. IDENTITY fields (opportunity/candidate/batch/
    approval_mode) are NEVER taken from the worker — only these mutable outcome fields are."""
    worker_id: str
    status: St
    questions: list[ApplicationQuestion] = []
    logs: list[TaskEvent] = []
    current_page: int = 0
    error_code: str = ""
    error_message: str = ""
    confirmation_reference: str = ""
    started_at: str = ""
    submitted_at: str = ""
    finished_at: str = ""


@router.post("/tasks/{task_id}/complete", dependencies=[Depends(require_worker)])
def complete_task(task_id: int, body: CompleteIn) -> dict:
    """Record a run's outcome and, in the ONE place it happens, flip the opportunity to
    APPLIED on a real submission (§30). The worker can only report a whitelisted status — it
    can never write APPLIED or an arbitrary state."""
    if body.status not in WORKER_REPORTABLE_STATUSES:
        raise HTTPException(400, f"{body.status.value} is not a reportable status")
    task = _owned(task_id, body.worker_id)
    if task.status != St.CLAIMED:
        raise HTTPException(409, f"task is {task.status.value}, not CLAIMED")

    # Overlay only the mutable outcome fields onto the server's authoritative task.
    task.status = body.status
    task.questions = body.questions
    task.logs = body.logs or task.logs
    task.current_page = body.current_page
    task.error_code = body.error_code
    task.error_message = body.error_message
    task.confirmation_reference = body.confirmation_reference
    task.started_at = body.started_at or task.started_at
    task.submitted_at = body.submitted_at
    task.finished_at = body.finished_at or _now()
    task.submit_approved = False              # consume the one-shot approval
    db.save_task(task)

    # The single APPLIED gate (§30): SUBMITTED/CONFIRMED only, never SUBMISSION_UNCERTAIN.
    if applied(task):
        opp = db.get_opportunity(task.opportunity_id)
        if opp is not None and opp.status != OpportunityStatus.APPLIED:
            opp.status = OpportunityStatus.APPLIED
            db.save_opportunity(opp)
    db.upsert_worker(body.worker_id, status="idle", current_task_id=None)
    return {"ok": True, "status": task.status.value, "applied": applied(task)}


# -------------------------------------------------------------------- fail #
class FailIn(BaseModel):
    worker_id: str
    error_code: str = "WORKER_ERROR"
    error_message: str = ""
    # Whatever the run got through before it crashed (mirrors CompleteIn) — without these a
    # crash silently threw away every field the worker had already filled (§24).
    questions: list[ApplicationQuestion] = []
    logs: list[TaskEvent] = []
    current_page: int = 0


@router.post("/tasks/{task_id}/fail", dependencies=[Depends(require_worker)])
def fail_task(task_id: int, body: FailIn) -> dict:
    """Driver/browser crash the worker caught. Never downgrades a task that already reached a
    submitted state — that would hide a real submission (§19)."""
    task = _owned(task_id, body.worker_id)
    if task.status in (St.SUBMITTED, St.CONFIRMED, St.SUBMISSION_UNCERTAIN):
        return {"ok": True, "status": task.status.value, "note": "already terminal"}
    task.status = St.FAILED
    task.questions = body.questions or task.questions
    task.logs = body.logs or task.logs
    task.current_page = body.current_page or task.current_page
    task.error_code = body.error_code
    task.error_message = body.error_message[:300]
    task.finished_at = _now()
    task.log("FAILED", body.error_code)
    db.save_task(task)
    db.upsert_worker(body.worker_id, status="idle", current_task_id=None)
    return {"ok": True, "status": "FAILED"}


# --------------------------------------------------------------- resume dl #
@router.get("/tasks/{task_id}/resume.pdf", dependencies=[Depends(require_worker)])
def download_resume(task_id: int) -> Response:
    """Serve the tailored résumé PDF for the worker to upload (trap #1). Rendered on demand
    with reportlab — no LaTeX engine needed on either side (§25)."""
    task = db.get_task(task_id)
    if task is None:
        raise HTTPException(404, "task not found")
    opp = db.get_opportunity(task.opportunity_id)
    stored = db.get_generation(opp.job_id) if opp and opp.job_id else None
    if not stored:
        raise HTTPException(404, "no prepared résumé for this task")
    pdf = export.build_pdf(TailoredResume.model_validate_json(stored))
    return Response(content=pdf, media_type="application/pdf")


# ---------------------------------------------------------------- llm proxy #
class AnswerIn(BaseModel):
    question: str
    jd: str = ""
    evidence: str = ""


@router.post("/llm/answer", dependencies=[Depends(require_worker)])
def llm_answer(body: AnswerIn) -> dict:
    """Semantic answers stay server-side so provider keys/prompts/logging are centralized
    (§28). The worker calls this via RemoteLLMProvider; grounding/validation is unchanged."""
    from .providers.llm import get_llm_provider, LLMError
    try:
        ans = get_llm_provider().answer_question(body.question, body.jd, body.evidence)
    except LLMError as e:
        raise HTTPException(502, f"llm error: {e}")
    return ans.model_dump()
