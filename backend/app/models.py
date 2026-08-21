"""Domain models — the shared vocabulary. Provenance (`Status`) is threaded through
every piece of candidate information: the product must never silently turn a Missing
requirement into a Verified fact."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Provenance                                                                   #
# --------------------------------------------------------------------------- #
class Status(str, Enum):
    ORIGINAL = "ORIGINAL"                # extracted from master resume / entered by candidate
    AI_SUGGESTED = "AI_SUGGESTED"        # proposed by the system, not yet approved
    USER_CONFIRMED = "USER_CONFIRMED"    # candidate accepted an AI suggestion as-is
    USER_EDITED = "USER_EDITED"          # candidate accepted an AI suggestion with edits
    GENERATED = "GENERATED"              # produced by the generation step
    REJECTED = "REJECTED"                # candidate rejected


# Statuses that count as real, usable candidate evidence.
SUPPORTED_STATUSES = {Status.ORIGINAL, Status.USER_CONFIRMED, Status.USER_EDITED}


class EntityType(str, Enum):
    skill = "skill"
    project = "project"
    experience = "experience"
    education = "education"
    certification = "certification"
    achievement = "achievement"


# --------------------------------------------------------------------------- #
# Candidate master profile (ingestion output / fixture shape)                  #
# --------------------------------------------------------------------------- #
class Candidate(BaseModel):
    id: Optional[int] = None
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    headline: str = ""
    links: list[str] = Field(default_factory=list)


class SkillItem(BaseModel):
    name: str
    category: str = ""
    level: str = ""


class ProjectItem(BaseModel):
    name: str
    summary: str = ""
    description: str = ""
    domain: str = ""
    technologies: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    company: str
    title: str = ""
    start: str = ""
    end: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    institution: str
    degree: str = ""
    field: str = ""
    start: str = ""
    end: str = ""


class CertificationItem(BaseModel):
    name: str
    issuer: str = ""
    year: str = ""


class AchievementItem(BaseModel):
    text: str


class MasterProfile(BaseModel):
    candidate: Candidate = Field(default_factory=Candidate)
    skills: list[SkillItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)
    achievements: list[AchievementItem] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Knowledge base entity (storage + retrieval unit)                            #
# --------------------------------------------------------------------------- #
class KBEntity(BaseModel):
    id: Optional[int] = None
    candidate_id: int
    entity_type: EntityType
    name: str
    content: str                          # text used for embedding + keyword search
    data: dict[str, Any] = Field(default_factory=dict)  # type-specific structured fields
    domain: str = ""
    status: Status = Status.ORIGINAL
    source: str = "master_resume"
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    def technologies(self) -> list[str]:
        techs = self.data.get("technologies", []) or []
        langs = self.data.get("languages", []) or []
        return [str(t) for t in (*techs, *langs)]


# --------------------------------------------------------------------------- #
# JD analysis                                                                  #
# --------------------------------------------------------------------------- #
class JDRequirements(BaseModel):
    role: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    domain_terms: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    experience_expectations: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Retrieval + matching                                                         #
# --------------------------------------------------------------------------- #
class MatchStatus(str, Enum):
    STRONG_MATCH = "STRONG_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    WEAK_MATCH = "WEAK_MATCH"
    MISSING = "MISSING"
    USER_CONFIRMATION_REQUIRED = "USER_CONFIRMATION_REQUIRED"


class EvidenceRef(BaseModel):
    entity_id: Optional[int] = None
    entity_type: EntityType
    name: str
    snippet: str = ""
    score: float = 0.0
    status: Status = Status.ORIGINAL


class RequirementMatch(BaseModel):
    requirement: str
    kind: str = "required"                # required | preferred | responsibility | technology
    match_status: MatchStatus
    score: float = 0.0
    evidence: list[EvidenceRef] = Field(default_factory=list)
    reason: str = ""


class GapItem(BaseModel):
    requirement: str
    kind: str = "required"
    category: MatchStatus
    reason: str = ""
    suggested_action: str = ""


# --------------------------------------------------------------------------- #
# Modification plan + approval                                                 #
# --------------------------------------------------------------------------- #
class ModificationType(str, Enum):
    KEEP = "KEEP"
    EMPHASIZE = "EMPHASIZE"
    DEEMPHASIZE = "DEEMPHASIZE"
    REORDER = "REORDER"
    REWRITE = "REWRITE"
    ADD_SKILL = "ADD_SKILL"
    ADD_EVIDENCE = "ADD_EVIDENCE"


class ModificationSuggestion(BaseModel):
    id: str
    type: ModificationType
    target: str                           # entity name or skill this applies to
    current: str = ""
    suggested: str = ""
    reason: str = ""
    requires_approval: bool = True
    status: Status = Status.AI_SUGGESTED


class ModificationPlan(BaseModel):
    role: str = ""
    suggestions: list[ModificationSuggestion] = Field(default_factory=list)
    emphasize: list[str] = Field(default_factory=list)
    deemphasize: list[str] = Field(default_factory=list)
    reorder: list[str] = Field(default_factory=list)


class ApprovalAction(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    EDIT = "EDIT"


# --------------------------------------------------------------------------- #
# Generation + validation + ATS                                               #
# --------------------------------------------------------------------------- #
class ResumeBullet(BaseModel):
    text: str
    status: Status = Status.GENERATED
    evidence_entity_id: Optional[int] = None


class ResumeSection(BaseModel):
    title: str
    name: str = ""
    bullets: list[ResumeBullet] = Field(default_factory=list)


class TailoredResume(BaseModel):
    candidate: Candidate
    target_role: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    sections: list[ResumeSection] = Field(default_factory=list)
    markdown: str = ""


class ClaimStatus(str, Enum):
    SUPPORTED_BY_ORIGINAL = "SUPPORTED_BY_ORIGINAL"
    SUPPORTED_BY_USER_CONFIRMATION = "SUPPORTED_BY_USER_CONFIRMATION"
    AI_SUGGESTED_NOT_APPROVED = "AI_SUGGESTED_NOT_APPROVED"
    UNSUPPORTED = "UNSUPPORTED"


class Claim(BaseModel):
    text: str
    status: ClaimStatus
    evidence_entity_id: Optional[int] = None
    reason: str = ""


class ValidationReport(BaseModel):
    claims: list[Claim] = Field(default_factory=list)
    supported: int = 0
    unsupported: int = 0
    needs_approval: int = 0


class ATSReport(BaseModel):
    overall_score: float = 0.0
    skill_coverage: float = 0.0
    keyword_coverage: float = 0.0
    requirement_coverage: float = 0.0
    project_relevance: float = 0.0
    components: dict[str, float] = Field(default_factory=dict)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    potential_issues: list[str] = Field(default_factory=list)
