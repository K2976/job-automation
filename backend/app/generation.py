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
    ResumeEntry,
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


def _daterange(start: str | None, end: str | None) -> str:
    return " -- ".join(x for x in (start, end) if x)


def _entry(heading: str, subheading: str, date: str, bullet_texts: list[str],
           evidence_id: int | None, status: Status = Status.GENERATED) -> ResumeEntry:
    bullets = [ResumeBullet(text=t, status=status, evidence_entity_id=evidence_id)
               for t in bullet_texts if t and t.strip()]
    return ResumeEntry(heading=heading, subheading=subheading, date=date, bullets=bullets)


def original_resume(candidate: Candidate, entities: list[KBEntity]) -> TailoredResume:
    """The untailored master profile as a TailoredResume — no JD, no filtering — so the
    original can be exported through the same template as tailored views (§32). Content is
    ORIGINAL evidence verbatim; nothing is reframed or dropped."""
    by_type: dict[EntityType, list[KBEntity]] = {}
    for e in entities:
        by_type.setdefault(e.entity_type, []).append(e)

    proj = ResumeSection(title="Projects")
    for e in by_type.get(EntityType.project, []):
        d = e.data
        pts = (d.get("responsibilities") or ([d.get("summary")] if d.get("summary") else []))
        proj.entries.append(_entry(e.name, "", "", pts[:4], e.id, Status.ORIGINAL))
        proj.bullets.append(ResumeBullet(text=f"{e.name}: {d.get('summary') or e.content}",
                                         status=Status.ORIGINAL, evidence_entity_id=e.id))

    exp = ResumeSection(title="Experience")
    for e in by_type.get(EntityType.experience, []):
        d = e.data
        pts = d.get("highlights") or ([d["description"]] if d.get("description") else [])
        exp.entries.append(_entry(d.get("company") or e.name, d.get("title", ""),
                                  _daterange(d.get("start"), d.get("end")), pts[:4], e.id,
                                  Status.ORIGINAL))
        exp.bullets.append(ResumeBullet(text=e.content, status=Status.ORIGINAL,
                                        evidence_entity_id=e.id))

    edu = ResumeSection(title="Education")
    for e in by_type.get(EntityType.education, []):
        d = e.data
        sub = ", ".join(x for x in (d.get("degree"), d.get("field")) if x)
        edu.entries.append(_entry(d.get("institution") or e.name, sub,
                                  _daterange(d.get("start"), d.get("end")), [], e.id,
                                  Status.ORIGINAL))
        edu.bullets.append(ResumeBullet(text=e.content, status=Status.ORIGINAL,
                                        evidence_entity_id=e.id))

    flat = []
    for title, etype in (("Achievements", EntityType.achievement),
                         ("Certifications", EntityType.certification)):
        sec = ResumeSection(title=title, bullets=[
            ResumeBullet(text=e.content, status=Status.ORIGINAL, evidence_entity_id=e.id)
            for e in by_type.get(etype, [])])
        flat.append(sec)

    skills = [prettify_skill(e.name) for e in by_type.get(EntityType.skill, [])]
    sections = [s for s in (proj, exp, edu, *flat) if s.entries or s.bullets]
    resume = TailoredResume(candidate=candidate, target_role=candidate.headline,
                            summary=candidate.headline, skills=skills, sections=sections)
    resume.markdown = render_markdown(resume)
    return resume


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
        # Structured entry for the LaTeX layout — bullets drawn from approved rewrite or
        # the project's ORIGINAL responsibilities (all supported evidence, never invented).
        rewrite = approved_rewrites.get(ent.name)
        pts = [rewrite] if rewrite else (ent.data.get("responsibilities") or [text])[:3]
        proj_section.entries.append(_entry(ent.name, "", "", pts, ent.id))

    exp_section = ResumeSection(title="Experience")
    for e in entities:
        if e.entity_type == EntityType.experience:
            exp_section.bullets.append(ResumeBullet(
                text=e.content, status=Status.GENERATED, evidence_entity_id=e.id))
            d = e.data
            pts = (d.get("highlights") or ([d["description"]] if d.get("description") else []))
            exp_section.entries.append(_entry(
                d.get("company") or e.name, d.get("title", ""),
                _daterange(d.get("start"), d.get("end")), pts[:3], e.id))

    edu_section = ResumeSection(title="Education")
    for e in entities:
        if e.entity_type == EntityType.education:
            edu_section.bullets.append(ResumeBullet(
                text=e.content, status=Status.GENERATED, evidence_entity_id=e.id))
            d = e.data
            sub = ", ".join(x for x in (d.get("degree"), d.get("field")) if x)
            edu_section.entries.append(_entry(
                d.get("institution") or e.name, sub,
                _daterange(d.get("start"), d.get("end")), [], e.id))

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


def render_html(r: TailoredResume) -> str:
    """Standalone, print-friendly HTML document from the structured résumé model."""
    import html as _html

    def esc(s: str) -> str:
        return _html.escape(s or "")

    c = r.candidate
    contact = " · ".join(x for x in (c.email, c.phone, c.location, *c.links) if x)
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{esc(c.name)} — {esc(r.target_role)}</title>",
        "<style>",
        "body{font:14px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a1a;",
        "max-width:760px;margin:32px auto;padding:0 24px;}",
        "h1{font-size:26px;margin:0 0 2px;} .contact{color:#555;font-size:13px;margin-bottom:14px;}",
        "h2{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:#2a5db0;",
        "border-bottom:1px solid #d7dae0;padding-bottom:3px;margin:18px 0 8px;}",
        ".role{color:#555;font-size:13px;} ul{margin:6px 0;padding-left:20px;} li{margin:3px 0;}",
        ".skills{margin:4px 0;}</style></head><body>",
        f"<h1>{esc(c.name)}</h1>",
        f"<div class='role'>{esc(r.target_role)}</div>" if r.target_role else "",
        f"<div class='contact'>{esc(contact)}</div>" if contact else "",
    ]
    if r.summary:
        parts += ["<h2>Summary</h2>", f"<p>{esc(r.summary)}</p>"]
    if r.skills:
        parts += ["<h2>Skills</h2>",
                  f"<div class='skills'>{esc(' · '.join(r.skills))}</div>"]
    for sec in r.sections:
        parts.append(f"<h2>{esc(sec.title)}</h2><ul>")
        parts += [f"<li>{esc(b.text)}</li>" for b in sec.bullets]
        parts.append("</ul>")
    parts.append("</body></html>")
    return "".join(parts)


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
