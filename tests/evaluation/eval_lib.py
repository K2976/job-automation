"""Evaluation library: deterministic, lazy metrics (set overlap / Hit@K / equality — no
LLM-judge) plus a provider-agnostic per-JD runner. Used by both the pytest evaluation
(mock, offline) and the standalone live runner (run_eval.py).

CRITICAL: the runner never mutates a persistent DB. Callers pass an isolated candidate_id
seeded into a throwaway database, so accept/edit test modifications never contaminate the
master profile (§29)."""
from __future__ import annotations

import time
from pathlib import Path

from app import analysis, db, matching, pipeline
from app.models import (
    ApprovalAction, Candidate, EntityType, KBEntity, MatchStatus, ResumeBullet,
    ResumeSection, Status, SUPPORTED_STATUSES, TailoredResume, ValidationReport,
)
from app.planning import apply_approval
from app.providers.embeddings import get_embedding_provider
from app.providers.llm import LLMProvider
from app.retrieval import RetrievalIndex
from app.text_utils import extract_skills, normalize_skill, prettify_skill

FIXTURES = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------------- #
# Lazy metrics
# --------------------------------------------------------------------------- #
def prf(predicted: set[str], expected: set[str]) -> dict:
    """Precision / recall / F1 with the concrete matched/missed/extra sets."""
    tp = predicted & expected
    precision = len(tp) / len(predicted) if predicted else 0.0
    recall = len(tp) / len(expected) if expected else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        "matched": sorted(tp), "missed": sorted(expected - predicted),
        "extra": sorted(predicted - expected),
    }


def hit_at_k(retrieved_names: list[str], expected: set[str], k: int) -> bool:
    top = {n.lower() for n in retrieved_names[:k]}
    return any(e.lower() in top for e in expected)


# --------------------------------------------------------------------------- #
# Retrieval-mode comparison (semantic vs keyword vs hybrid) — fully offline
# --------------------------------------------------------------------------- #
def retrieval_modes(index: RetrievalIndex, query: str, k: int = 5) -> dict[str, list[str]]:
    scored = index.search(query, top_k=len(index.entities) or 1)
    def names(key) -> list[str]:
        return [s.entity.name for s in sorted(scored, key=key, reverse=True)[:k]]
    return {
        "semantic": names(lambda s: s.semantic),
        "keyword": names(lambda s: s.keyword),
        "hybrid": names(lambda s: s.score),
    }


# --------------------------------------------------------------------------- #
# Baseline ("untailored, everything") résumé, so ATS can score original vs tailored
# --------------------------------------------------------------------------- #
def baseline_resume(candidate: Candidate, entities: list[KBEntity], role: str) -> TailoredResume:
    skills = [prettify_skill(normalize_skill(e.name))
              for e in entities if e.entity_type == EntityType.skill]
    projects = ResumeSection(title="Projects", bullets=[
        ResumeBullet(text=f"{e.name}: {e.content}", evidence_entity_id=e.id)
        for e in entities if e.entity_type == EntityType.project])
    r = TailoredResume(candidate=candidate, target_role=role, skills=skills,
                       summary="", sections=[projects])
    from app.generation import render_markdown
    r.markdown = render_markdown(r)
    return r


# --------------------------------------------------------------------------- #
# Per-JD evaluation
# --------------------------------------------------------------------------- #
def evaluate_jd(candidate_id: int, key: str, label: dict, llm: LLMProvider) -> dict:
    jd_text = (FIXTURES / label["jd_file"]).read_text()

    t0 = time.perf_counter()
    result = pipeline.analyze_job(candidate_id, jd_text, llm=llm)
    analyze_ms = round((time.perf_counter() - t0) * 1000)

    requirements = result["requirements"]
    matches = result["matches"]
    plan = result["plan"]
    job_id = result["job_id"]

    # --- JD extraction quality ---
    # Concept coverage over the raw output strings (substring), so a live LLM's rich
    # phrasing ("Machine Learning and deep learning (CNN)") isn't penalised for not
    # collapsing to an exact canonical token. Fair to mock and live alike.
    req_strings = [s.lower() for s in
                   (*requirements.required_skills, *requirements.preferred_skills,
                    *requirements.technologies)]
    covered = {e for e in label["expect_required"]
               if any(e in rs for rs in req_strings)}
    jd_extraction = {
        "recall": round(len(covered) / len(label["expect_required"]), 3)
        if label["expect_required"] else 1.0,
        "matched": sorted(covered),
        "missed": sorted(label["expect_required"] - covered),
    }
    false_positives = sorted(
        a for a in label["expect_absent"] if any(a in rs for rs in req_strings))

    # --- matching classification vs labels ---
    status_by_skill = {normalize_skill(m.requirement): m.match_status for m in matches}
    strong_check = {s: status_by_skill.get(s) for s in label["expect_strong"]
                    if s in status_by_skill}
    strong_ok = all(v == MatchStatus.STRONG_MATCH for v in strong_check.values())
    missing_check = {s: status_by_skill.get(s) for s in label["expect_missing"]
                     if s in status_by_skill}
    missing_ok = all(v == MatchStatus.MISSING for v in missing_check.values())

    # --- retrieval Hit@K (offline; uses the supported KB) ---
    entities = db.get_entities(candidate_id, statuses=SUPPORTED_STATUSES)
    index = RetrievalIndex(entities, get_embedding_provider("local"))
    retrieval = {}
    for req, expected in label.get("expect_evidence", {}).items():
        modes = retrieval_modes(index, req, k=5)
        retrieval[req] = {
            "hit@3": hit_at_k(modes["hybrid"], expected, 3),
            "hit@5": hit_at_k(modes["hybrid"], expected, 5),
            "modes": modes,
        }

    # --- human-in-the-loop on a throwaway copy of the plan (accept/reject/edit) ---
    hitl = _human_in_the_loop(candidate_id, plan)

    # --- generation + validation + ats + comparison ---
    gen = pipeline.generate_for_job(job_id, llm=llm)
    resume, validation, ats, comparison = (
        gen["resume"], gen["validation"], gen["ats"], gen["comparison"])

    # original-vs-tailored alignment (same scorer, different résumé)
    candidate = db.get_candidate(candidate_id)
    all_ents = db.get_entities(candidate_id)
    base = baseline_resume(candidate, all_ents, requirements.role)
    base_ats = analysis.ats_report(requirements, matches, base, ValidationReport())

    # anti-hallucination: forbidden skills must not appear in the résumé
    resume_skills = {normalize_skill(s) for s in resume.skills}
    claimed_forbidden = sorted(resume_skills & label.get("must_not_claim", set()))

    total_ms = round((time.perf_counter() - t0) * 1000)
    return {
        "key": key, "provider": llm.name, "model": getattr(llm, "model", "-"),
        "role_extracted": requirements.role,
        "role_ok": label["role_substr"].lower() in requirements.role.lower(),
        "jd_extraction": jd_extraction, "false_positives": false_positives,
        "matching": {"strong_ok": strong_ok, "strong": _fmt(strong_check),
                     "missing_ok": missing_ok, "missing": _fmt(missing_check)},
        "retrieval": retrieval,
        "human_in_the_loop": hitl,
        "generation": {"skills": resume.skills,
                       "bullets": sum(len(s.bullets) for s in resume.sections)},
        "validation": {"supported": validation.supported,
                       "unsupported": validation.unsupported,
                       "needs_approval": validation.needs_approval},
        "ats": {"original": base_ats.overall_score, "tailored": ats.overall_score,
                "delta": round(ats.overall_score - base_ats.overall_score, 3),
                "missing_skills": ats.missing_skills},
        "comparison": {"skills_added": comparison["skills_added"],
                       "skills_dropped": comparison["skills_dropped"]},
        "anti_hallucination": {"claimed_forbidden": claimed_forbidden},
        "latency": {"analyze_ms": analyze_ms, "total_ms": total_ms},
    }


def _fmt(d: dict) -> dict:
    return {k: (v.value if hasattr(v, "value") else v) for k, v in d.items()}


def _human_in_the_loop(candidate_id: int, plan) -> dict:
    """Exercise accept / reject / edit and confirm the provenance transitions (§13).
    Runs against the isolated eval DB, so it never touches the real master profile."""
    adds = [s for s in plan.suggestions if s.type.value == "ADD_SKILL"]
    out: dict = {}
    if len(adds) >= 1:
        s = adds[0]
        st = apply_approval(candidate_id, s.id, ApprovalAction.ACCEPT)
        out["accept"] = {"target": s.target, "status": st.value,
                         "ok": st == Status.USER_CONFIRMED}
    if len(adds) >= 2:
        s = adds[1]
        st = apply_approval(candidate_id, s.id, ApprovalAction.REJECT)
        confirmed = {e.name.lower() for e in db.get_entities(
            candidate_id, entity_type=EntityType.skill, statuses=SUPPORTED_STATUSES)}
        out["reject"] = {"target": s.target, "status": st.value,
                         "ok": st == Status.REJECTED and s.target.lower() not in confirmed}
    if len(adds) >= 3:
        s = adds[2]
        st = apply_approval(candidate_id, s.id, ApprovalAction.EDIT, edited_text="Edited Skill")
        edited = {e.name for e in db.get_entities(
            candidate_id, entity_type=EntityType.skill, statuses=[Status.USER_EDITED])}
        out["edit"] = {"target": s.target, "status": st.value,
                       "ok": st == Status.USER_EDITED and "Edited Skill" in edited}
    return out
