"""Application task state machine (§8). Transitions are explicit and enforced — an illegal
transition raises rather than silently corrupting task state. `APPLIED` on the underlying
opportunity is owned elsewhere (runner) and only for SUBMITTED/CONFIRMED (§30)."""
from __future__ import annotations

from ..models import ApplicationStatus as S

# Legal transitions. Read as: from → {allowed next states}.
_LEGAL: dict[S, set[S]] = {
    S.READY: {S.QUEUED, S.PAUSED, S.CANCELLED},
    S.QUEUED: {S.OPENING, S.CLAIMED, S.PAUSED, S.CANCELLED},
    # A remote worker claims a QUEUED task, then reports one terminal/pause outcome (its
    # local runner drove OPENING→…→final on its own copy). Stale recovery sends it back to
    # QUEUED, or to SUBMISSION_UNCERTAIN if a submit was granted (§15, §18).
    S.CLAIMED: {S.REVIEW_REQUIRED, S.USER_ACTION_REQUIRED, S.LOGIN_REQUIRED, S.BLOCKED,
                S.FAILED, S.SUBMITTED, S.CONFIRMED, S.SUBMISSION_UNCERTAIN,
                S.QUEUED, S.CANCELLED},
    S.PAUSED: {S.QUEUED, S.CANCELLED},
    S.OPENING: {S.INSPECTING, S.BLOCKED, S.LOGIN_REQUIRED, S.FAILED},
    S.INSPECTING: {S.FILLING, S.BLOCKED, S.LOGIN_REQUIRED, S.FAILED},
    S.FILLING: {
        S.INSPECTING,            # advanced to the next page of a multi-page form
        S.REVIEW_REQUIRED,       # filled, waiting for human approval (manual/review)
        S.USER_ACTION_REQUIRED,  # unknown / high-impact question needs the user
        S.BLOCKED, S.LOGIN_REQUIRED, S.FAILED,
        S.SUBMITTED, S.SUBMISSION_UNCERTAIN,  # autonomous submit outcomes
    },
    S.REVIEW_REQUIRED: {S.SUBMITTED, S.SUBMISSION_UNCERTAIN, S.FAILED, S.CANCELLED,
                        S.FILLING, S.QUEUED},   # QUEUED: approved task re-queued for a worker

    S.USER_ACTION_REQUIRED: {S.QUEUED, S.FILLING, S.CANCELLED, S.FAILED},
    S.LOGIN_REQUIRED: {S.QUEUED, S.FILLING, S.CANCELLED, S.FAILED},
    S.BLOCKED: {S.CANCELLED, S.QUEUED},      # a retry re-queues; automation never bypasses
    S.SUBMITTED: {S.CONFIRMED, S.SUBMISSION_UNCERTAIN},
    S.SUBMISSION_UNCERTAIN: {S.CONFIRMED, S.FAILED},
    # Terminal (retry re-queues a failed task, mutating it in place — §29):
    S.FAILED: {S.QUEUED},
    S.CONFIRMED: set(),
    S.CANCELLED: set(),
}


class IllegalTransition(ValueError):
    pass


def can(frm: S, to: S) -> bool:
    return to in _LEGAL.get(frm, set())


def transition(task, to: S) -> None:
    """Move `task` to state `to`, raising IllegalTransition if the edge isn't allowed.
    A no-op (to == current) is permitted so idempotent updates don't blow up."""
    frm = task.status
    if frm == to:
        return
    if not can(frm, to):
        raise IllegalTransition(f"{frm.value} → {to.value} is not a legal transition")
    task.status = to
