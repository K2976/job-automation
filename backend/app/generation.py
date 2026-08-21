"""Tailored resume generation (CLAUDE.md §20). Assembles from approved evidence +
approved modifications only. Identity is preserved verbatim; generated prose is tagged
GENERATED with a link back to the evidence entity it came from."""
from __future__ import annotations

from .models import (
    Candidate,
    EntityType,
    JDRequirements,
    KBEntity,
    MatchStatus,
    RequirementMatch,
    ResumeBullet,
    ResumeSection,
    Status,
    TailoredResume,
)
from .providers.llm import LLMProvider
from .retrieval import RetrievalIndex
from .text_utils import extract_skills, normalize_skill, prettify_skill


def _relevant_skills(entities: list[KBEntity], confirmed_skills: list[str],
                     requirements: JDRequirements) -> list[str]:
    jd = [normalize_skill(s) for s in
          (*requirements.required_skills, *requirements.preferred_skills,
           *requirements.technologies)]
    jd_order = {s: i for i, s in enumerate(jd)}
    have: set[str] = set(normalize_skill(s) for s in confirmed_skills)
    for e in entities:
        have.update(extract_skills(e.content))
        if e.entity_type == EntityType.skill:
            have.add(normalize_skill(e.name))
    # keep only skills the JD actually wants, ordered by JD priority
    relevant = [s for s in have if s in jd_order]
    relevant.sort(key=lambda s: jd_order[s])
    return relevant


def generate_resume(
    candidate: Candidate, role: str, requirements: JDRequirements,
    matches: list[RequirementMatch], entities: list[KBEntity],
    index: RetrievalIndex, llm: LLMProvider, *,
    approved_rewrites: dict[str, str] | None = None,
    confirmed_skills: list[str] | None = None,
) -> TailoredResume:
    approved_rewrites = approved_rewrites or {}
    confirmed_skills = confirmed_skills or []

    skills = [prettify_skill(s) for s in
              _relevant_skills(entities, confirmed_skills, requirements)]

    # rank projects by relevance to the role; drop clearly-irrelevant ones
    projects = [e for e in entities if e.entity_type == EntityType.project]
    query = f"{role} " + " ".join(requirements.required_skills[:8])
    ranked = index.search(query, top_k=len(projects) or 1,
                          entity_types=[EntityType.project]) if projects else []
    kept = [s for s in ranked if s.score >= 0.08] or ranked[:2]

    proj_section = ResumeSection(title="Projects")
    for s in kept:
        ent = s.entity
        text = approved_rewrites.get(ent.name) or ent.data.get("summary") or ent.content
        proj_section.bullets.append(ResumeBullet(
            text=f"{ent.name}: {text}", status=Status.GENERATED,
            evidence_entity_id=ent.id))

    exp_section = ResumeSection(title="Experience")
    for e in entities:
        if e.entity_type == EntityType.experience:
            exp_section.bullets.append(ResumeBullet(
                text=e.content, status=Status.GENERATED, evidence_entity_id=e.id))

    edu_section = ResumeSection(title="Education")
    for e in entities:
        if e.entity_type == EntityType.education:
            edu_section.bullets.append(ResumeBullet(
                text=e.content, status=Status.GENERATED, evidence_entity_id=e.id))

    highlights = [f"{s.entity.name} ({', '.join(extract_skills(s.entity.content)[:3])})"
                  for s in kept[:2]]
    highlights += [m.requirement for m in matches
                   if m.match_status == MatchStatus.STRONG_MATCH][:3]
    summary = llm.compose_summary(role, highlights or [role])

    sections = [s for s in (proj_section, exp_section, edu_section) if s.bullets]
    resume = TailoredResume(candidate=candidate, target_role=role, summary=summary,
                            skills=skills, sections=sections)
    resume.markdown = render_markdown(resume)
    return resume


def render_markdown(r: TailoredResume) -> str:
    c = r.candidate
    lines = [f"# {c.name}", ""]
    contact = " | ".join(x for x in (c.email, c.phone, c.location) if x)
    if contact:
        lines += [contact, ""]
    lines += [f"**Target role:** {r.target_role}", "", "## Summary", r.summary, ""]
    if r.skills:
        lines += ["## Skills", ", ".join(r.skills), ""]
    for sec in r.sections:
        lines.append(f"## {sec.title}")
        for b in sec.bullets:
            lines.append(f"- {b.text}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
