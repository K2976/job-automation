"""High-level orchestration — the two flows the API drives: analyse a JD against a
candidate, and generate+validate a tailored resume. Deterministic stages recompute
freely; only user approval state is persisted."""
from __future__ import annotations

import json
from pathlib import Path

from . import analysis, db, generation, kb, matching, planning, validation
from .config import REPO_ROOT
from .models import (
    JDRequirements,
    MasterProfile,
    ModificationType,
    Status,
)
from .providers.llm import LLMProvider, get_llm_provider
from .retrieval import RetrievalIndex

FIXTURES = REPO_ROOT / "data" / "fixtures"


# --------------------------------------------------------------------------- #
def seed_from_fixture(path: Path | None = None) -> int:
    profile = MasterProfile.model_validate_json(
        (path or FIXTURES / "master_profile.json").read_text())
    return kb.seed_profile(profile)


def _supported_entities(candidate_id: int):
    from .models import SUPPORTED_STATUSES
    return db.get_entities(candidate_id, statuses=SUPPORTED_STATUSES)


# --------------------------------------------------------------------------- #
def analyze_job(candidate_id: int, jd_text: str, llm: LLMProvider | None = None) -> dict:
    llm = llm or get_llm_provider()
    requirements = llm.analyze_jd(jd_text)

    entities = _supported_entities(candidate_id)
    index = RetrievalIndex(entities)
    skill_set = matching.candidate_skill_set(entities)

    matches = matching.match_requirements(index, requirements, skill_set)
    gaps = matching.analyze_gaps(matches)
    plan = planning.build_plan(requirements.role, requirements, matches, index,
                               entities, llm)

    job_id = db.insert_job(candidate_id, jd_text, requirements.role,
                           requirements.model_dump_json())
    db.replace_suggestions(job_id, candidate_id, plan.suggestions)

    return {"job_id": job_id, "requirements": requirements, "matches": matches,
            "gaps": gaps, "plan": plan}


def _load_job(job_id: int) -> tuple[int, JDRequirements, str]:
    row = db.get_job(job_id)
    if row is None:
        raise KeyError(f"unknown job {job_id}")
    return (row["candidate_id"],
            JDRequirements.model_validate_json(row["requirements_json"]),
            row["raw_text"])


def generate_for_job(job_id: int, llm: LLMProvider | None = None) -> dict:
    llm = llm or get_llm_provider()
    candidate_id, requirements, _ = _load_job(job_id)
    candidate = db.get_candidate(candidate_id)

    # Approved project rewrites (USER_CONFIRMED / USER_EDITED only).
    approved_rewrites = {
        s.target: s.suggested for s in db.get_suggestions(job_id)
        if s.type == ModificationType.REWRITE
        and s.status in (Status.USER_CONFIRMED, Status.USER_EDITED)
    }

    # Confirmed skills are already persisted in the KB by the approval step.
    entities = _supported_entities(candidate_id)
    index = RetrievalIndex(entities)
    skill_set = matching.candidate_skill_set(entities)
    matches = matching.match_requirements(index, requirements, skill_set)

    resume = generation.generate_resume(
        candidate, requirements.role, requirements, matches, entities, index, llm,
        approved_rewrites=approved_rewrites)

    # Validate against ALL entities (any provenance) so unapproved claims are caught.
    all_entities = db.get_entities(candidate_id)
    report = validation.validate_resume(resume, all_entities)
    ats = analysis.ats_report(requirements, matches, resume, report)
    master_md = analysis.render_master_markdown(candidate, all_entities)
    comparison = analysis.compare_resumes(master_md, resume.markdown)

    return {"resume": resume, "validation": report, "ats": ats,
            "comparison": comparison, "matches": matches}
