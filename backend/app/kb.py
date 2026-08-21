"""Candidate knowledge base: turn a structured MasterProfile into retrievable,
provenance-tagged KB entities (not one big resume blob — CLAUDE.md §13)."""
from __future__ import annotations

from . import db
from .models import (
    EntityType,
    KBEntity,
    MasterProfile,
    Status,
)


def _project_content(p) -> str:
    parts = [p.name, p.summary, p.description]
    if p.responsibilities:
        parts.append("Responsibilities: " + "; ".join(p.responsibilities))
    if p.achievements:
        parts.append("Achievements: " + "; ".join(p.achievements))
    if p.metrics:
        parts.append("Metrics: " + "; ".join(p.metrics))
    techs = [*p.technologies, *p.languages]
    if techs:
        parts.append("Technologies: " + ", ".join(techs))
    if p.domain:
        parts.append("Domain: " + p.domain)
    return " ".join(s for s in parts if s)


def _experience_content(e) -> str:
    parts = [f"{e.title} at {e.company}".strip(), e.description]
    if e.highlights:
        parts.append("Highlights: " + "; ".join(e.highlights))
    if e.technologies:
        parts.append("Technologies: " + ", ".join(e.technologies))
    return " ".join(s for s in parts if s)


def seed_profile(profile: MasterProfile) -> int:
    """Persist a candidate + all master-profile entities as ORIGINAL evidence."""
    candidate_id = db.insert_candidate(profile.candidate)

    for s in profile.skills:
        # content is the skill name only — category/level are metadata, not retrieval
        # text (a code like "ml" must never be mistaken for a skill mention).
        db.insert_entity(KBEntity(
            candidate_id=candidate_id, entity_type=EntityType.skill,
            name=s.name, content=s.name,
            data={"category": s.category, "level": s.level}, status=Status.ORIGINAL))

    for p in profile.projects:
        db.insert_entity(KBEntity(
            candidate_id=candidate_id, entity_type=EntityType.project, name=p.name,
            content=_project_content(p), domain=p.domain,
            data=p.model_dump(), status=Status.ORIGINAL))

    for e in profile.experience:
        db.insert_entity(KBEntity(
            candidate_id=candidate_id, entity_type=EntityType.experience,
            name=f"{e.title} at {e.company}".strip(), content=_experience_content(e),
            data=e.model_dump(), status=Status.ORIGINAL))

    for ed in profile.education:
        db.insert_entity(KBEntity(
            candidate_id=candidate_id, entity_type=EntityType.education,
            name=f"{ed.degree} {ed.field}".strip() or ed.institution,
            content=f"{ed.degree} in {ed.field}, {ed.institution}".strip(),
            data=ed.model_dump(), status=Status.ORIGINAL))

    for c in profile.certifications:
        db.insert_entity(KBEntity(
            candidate_id=candidate_id, entity_type=EntityType.certification,
            name=c.name, content=f"{c.name} {c.issuer}".strip(),
            data=c.model_dump(), status=Status.ORIGINAL))

    for a in profile.achievements:
        db.insert_entity(KBEntity(
            candidate_id=candidate_id, entity_type=EntityType.achievement,
            name=a.text[:60], content=a.text, data={}, status=Status.ORIGINAL))

    return candidate_id


def add_confirmed_skill(candidate_id: int, skill: str, status: Status,
                        source: str = "user_confirmation") -> int:
    """A skill the candidate confirmed applies (from an approved suggestion).
    Never ORIGINAL — provenance stays honest."""
    return db.insert_entity(KBEntity(
        candidate_id=candidate_id, entity_type=EntityType.skill, name=skill,
        content=skill, data={"confirmed": True}, status=status, source=source))
