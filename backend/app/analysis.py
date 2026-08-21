"""JD-alignment ("ATS-style") analysis (§24), explainability (§21) and original-vs-
tailored comparison (§23). Scores are deterministic product indicators, not guarantees."""
from __future__ import annotations

import difflib

from .config import settings
from .models import (
    ATSReport,
    Candidate,
    JDRequirements,
    KBEntity,
    MatchStatus,
    RequirementMatch,
    TailoredResume,
    ValidationReport,
)
from .text_utils import extract_skills, normalize_skill, tokenize

# Scoring weights (CLAUDE.md §19) — configurable, product-level indicator only.
_WEIGHTS = {"skill": 0.40, "keyword": 0.20, "requirement": 0.25, "project": 0.15}


def _coverage(items: list[str], present: set[str]) -> tuple[float, list[str]]:
    if not items:
        return 1.0, []
    missing = [i for i in items if normalize_skill(i) not in present]
    return (len(items) - len(missing)) / len(items), missing


def ats_report(requirements: JDRequirements, matches: list[RequirementMatch],
               resume: TailoredResume, validation: ValidationReport) -> ATSReport:
    resume_text = resume.markdown or resume.summary
    resume_skills = {normalize_skill(s) for s in resume.skills}
    resume_skills.update(extract_skills(resume_text))
    resume_tokens = set(tokenize(resume_text))

    skill_cov, missing = _coverage(requirements.required_skills, resume_skills)
    matched_kw = [k for k in requirements.keywords if k in resume_tokens]
    keyword_cov = (len(matched_kw) / len(requirements.keywords)
                   if requirements.keywords else 1.0)

    if matches:
        good = sum(1 for m in matches if m.match_status in (
            MatchStatus.STRONG_MATCH, MatchStatus.PARTIAL_MATCH))
        req_cov = good / len(matches)
    else:
        req_cov = 0.0

    proj_bullets = next((s.bullets for s in resume.sections if s.title == "Projects"), [])
    project_rel = min(1.0, len(proj_bullets) / 3) if proj_bullets else 0.0

    components = {"skill": skill_cov, "keyword": keyword_cov,
                  "requirement": req_cov, "project": project_rel}
    overall = sum(components[k] * w for k, w in _WEIGHTS.items())

    issues = []
    if missing:
        issues.append(f"{len(missing)} required skill(s) not evidenced: "
                      + ", ".join(missing[:6]))
    if validation.unsupported:
        issues.append(f"{validation.unsupported} unsupported claim(s) flagged by validator.")
    if len(resume_tokens) < 60:
        issues.append("Resume is very short; may lack keyword surface for ATS.")

    return ATSReport(
        overall_score=round(overall, 3), skill_coverage=round(skill_cov, 3),
        keyword_coverage=round(keyword_cov, 3), requirement_coverage=round(req_cov, 3),
        project_relevance=round(project_rel, 3),
        components={k: round(v, 3) for k, v in components.items()},
        matched_keywords=matched_kw, missing_skills=missing, potential_issues=issues)


def explain_requirement(requirement: str, matches: list[RequirementMatch]) -> dict:
    """'Why is this here?' — trace a requirement to its evidence and reasoning."""
    m = next((x for x in matches
              if normalize_skill(x.requirement) == normalize_skill(requirement)), None)
    if m is None:
        return {"requirement": requirement, "found": False}
    return {
        "requirement": m.requirement, "found": True, "status": m.match_status.value,
        "relevance": m.score, "reason": m.reason,
        "evidence": [{"name": e.name, "type": e.entity_type.value,
                      "snippet": e.snippet, "score": e.score, "status": e.status.value}
                     for e in m.evidence],
    }


def render_master_markdown(candidate: Candidate, entities: list[KBEntity]) -> str:
    """Baseline 'everything' resume from the master profile, for comparison."""
    from .models import EntityType
    lines = [f"# {candidate.name}", ""]
    order = [EntityType.skill, EntityType.experience, EntityType.project,
             EntityType.education, EntityType.certification, EntityType.achievement]
    for et in order:
        items = [e for e in entities if e.entity_type == et]
        if not items:
            continue
        lines.append(f"## {et.value.title()}")
        if et == EntityType.skill:
            lines.append(", ".join(e.name for e in items))
        else:
            lines += [f"- {e.content}" for e in items]
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def compare_resumes(original_md: str, tailored_md: str) -> dict:
    """Textual diff: added / removed lines + skill set delta (CLAUDE.md §23)."""
    o_lines = [l.strip() for l in original_md.splitlines() if l.strip()]
    t_lines = [l.strip() for l in tailored_md.splitlines() if l.strip()]
    sm = difflib.SequenceMatcher(a=o_lines, b=t_lines)
    added, removed = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            removed += o_lines[i1:i2]
        if tag in ("replace", "insert"):
            added += t_lines[j1:j2]

    o_skills = set(extract_skills(original_md))
    t_skills = set(extract_skills(tailored_md))
    return {
        "added_lines": added, "removed_lines": removed,
        "skills_added": sorted(t_skills - o_skills),
        "skills_dropped": sorted(o_skills - t_skills),
        "similarity": round(sm.ratio(), 3),
    }
