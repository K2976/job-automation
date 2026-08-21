"""Modification plan (CLAUDE.md §17) + approval workflow (§5, §10). The plan is what the
candidate reviews BEFORE any resume is generated. Approvable items are exactly the ones
that could introduce unsupported claims: project rewrites and skill additions."""
from __future__ import annotations

import re

from . import db, kb
from .models import (
    ApprovalAction,
    EntityType,
    JDRequirements,
    KBEntity,
    MatchStatus,
    ModificationPlan,
    ModificationSuggestion,
    ModificationType,
    RequirementMatch,
    Status,
)
from .providers.llm import LLMProvider
from .retrieval import RetrievalIndex
from .text_utils import extract_skills, normalize_skill


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def build_plan(role: str, requirements: JDRequirements, matches: list[RequirementMatch],
               index: RetrievalIndex, entities: list[KBEntity],
               llm: LLMProvider) -> ModificationPlan:
    jd_skills = {normalize_skill(s) for s in
                 (*requirements.required_skills, *requirements.preferred_skills,
                  *requirements.technologies)}

    suggestions: list[ModificationSuggestion] = []

    # 1. Project reframing (REWRITE) — grounded in the project's own evidence.
    projects = [e for e in entities if e.entity_type == EntityType.project]
    query = f"{role} " + " ".join(requirements.required_skills[:8])
    ranked = [s for s in index.search(query, top_k=len(projects) or 1,
                                      entity_types=[EntityType.project])]
    reorder = [s.entity.name for s in ranked]

    for s in ranked[:3]:
        ent = s.entity
        proj_skills = [sk for sk in extract_skills(ent.content) if sk in jd_skills]
        if not proj_skills:
            continue
        focus = ", ".join(proj_skills[:5])
        original = ent.data.get("description") or ent.data.get("summary") or ent.content
        rewritten = llm.rewrite(
            instruction=f"Reframe this project for a {role} role, emphasising {focus}",
            original=original, evidence=ent.content)
        suggestions.append(ModificationSuggestion(
            id=f"rewrite-{_slug(ent.name)}", type=ModificationType.REWRITE,
            target=ent.name, current=original[:280], suggested=rewritten,
            reason=f"This project supports {focus}, which the {role} JD emphasises.",
            requires_approval=True, status=Status.AI_SUGGESTED))

    # 2. Skill additions (ADD_SKILL) — only for gaps the candidate must confirm.
    for m in matches:
        if m.match_status not in (MatchStatus.USER_CONFIRMATION_REQUIRED,
                                  MatchStatus.MISSING):
            continue
        suggestions.append(ModificationSuggestion(
            id=f"addskill-{_slug(m.requirement)}", type=ModificationType.ADD_SKILL,
            target=m.requirement, current="not in profile", suggested=m.requirement,
            reason=(f"'{m.requirement}' appears in the JD ({m.match_status.value}). "
                    "Only include it if you genuinely have this experience."),
            requires_approval=True, status=Status.AI_SUGGESTED))

    # 3. Emphasis guidance (deterministic, no per-item approval needed).
    emphasize = [m.requirement for m in matches
                 if m.match_status in (MatchStatus.STRONG_MATCH,
                                       MatchStatus.PARTIAL_MATCH)][:12]
    candidate_skills = set()
    for e in entities:
        candidate_skills.update(extract_skills(e.content))
    deemphasize = sorted(candidate_skills - jd_skills)

    return ModificationPlan(role=role, suggestions=suggestions, emphasize=emphasize,
                            deemphasize=deemphasize, reorder=reorder)


# --------------------------------------------------------------------------- #
# Approval transitions                                                         #
# --------------------------------------------------------------------------- #
_TRANSITION = {
    ApprovalAction.ACCEPT: Status.USER_CONFIRMED,
    ApprovalAction.EDIT: Status.USER_EDITED,
    ApprovalAction.REJECT: Status.REJECTED,
}


def apply_approval(candidate_id: int, suggestion_id: str, action: ApprovalAction,
                   edited_text: str = "") -> Status:
    """Move a suggestion AI_SUGGESTED -> USER_CONFIRMED / USER_EDITED / REJECTED.
    Confirmed skill additions become real (non-ORIGINAL) KB evidence."""
    row = db.get_suggestion(suggestion_id)
    if row is None:
        raise KeyError(f"unknown suggestion {suggestion_id!r}")
    new_status = _TRANSITION[action]
    db.update_suggestion(suggestion_id, new_status,
                         edited_text if action == ApprovalAction.EDIT else "")

    if row["type"] == ModificationType.ADD_SKILL.value and \
            new_status in (Status.USER_CONFIRMED, Status.USER_EDITED):
        skill = edited_text or row["suggested"]
        kb.add_confirmed_skill(candidate_id, skill, new_status)
    return new_status
