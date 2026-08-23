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


class ResumeEntry(BaseModel):
    """A structured item within a section (a project / job / degree). Carries the fields
    the professional LaTeX layout needs — bold heading, right-aligned date, italic
    subheading — which a flat bullet string can't express. `date`/`subheading` are
    optional; the renderer skips them when blank (e.g. projects have no date)."""
    heading: str = ""
    subheading: str = ""
    date: str = ""
    bullets: list[ResumeBullet] = Field(default_factory=list)


class ResumeSection(BaseModel):
    title: str
    name: str = ""
    entries: list[ResumeEntry] = Field(default_factory=list)   # structured items (LaTeX)
    bullets: list[ResumeBullet] = Field(default_factory=list)  # flat items / legacy render


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


# =========================================================================== #
# V2 — Opportunity Intelligence                                                #
# =========================================================================== #
class SourceStatus(str, Enum):
    """Result of asking a source for opportunities in one discovery run. Anything that
    isn't AVAILABLE means: skip the source, report it, do NOT retry (§7, §8)."""
    AVAILABLE = "AVAILABLE"
    BLOCKED = "BLOCKED"            # access denied / anti-bot challenge
    CAPTCHA = "CAPTCHA"            # captcha encountered — never bypassed, just skipped
    UNREACHABLE = "UNREACHABLE"    # network / DNS / connection failure
    RATE_LIMITED = "RATE_LIMITED"  # 429 / throttled
    UNSUPPORTED = "UNSUPPORTED"    # site structure we don't handle
    ERROR = "ERROR"               # anything else


class OpportunityStatus(str, Enum):
    """Lifecycle (§11). V2 never sets APPLIED automatically — the user does (§28)."""
    DISCOVERED = "DISCOVERED"
    FILTERED = "FILTERED"              # passed hard filters, awaiting analysis
    ANALYZED = "ANALYZED"             # V1 match/gap analysis attached
    SHORTLISTED = "SHORTLISTED"
    TAILORING = "TAILORING"
    READY_TO_APPLY = "READY_TO_APPLY"
    APPLIED = "APPLIED"               # future / manual only
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"


class SourceHealth(BaseModel):
    source: str
    status: SourceStatus = SourceStatus.AVAILABLE
    discovered: int = 0
    detail: str = ""


class SearchPreferences(BaseModel):
    """Candidate discovery preferences (§13). Kept small and practical."""
    candidate_id: Optional[int] = None
    target_roles: list[str] = Field(default_factory=list)
    target_domains: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: str = "any"        # any | remote | onsite | hybrid
    employment_types: list[str] = Field(default_factory=list)  # e.g. internship, full-time
    experience_level: str = ""            # e.g. internship | entry | mid
    minimum_match_score: float = 0.0
    technology_preferences: list[str] = Field(default_factory=list)
    excluded_roles: list[str] = Field(default_factory=list)
    excluded_companies: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)   # source names to query ([] = all enabled)


class Opportunity(BaseModel):
    """A potential application target (§10). Analysis fields (`requirements`, `matches`,
    `gaps`, scores, `job_id`) are populated lazily — cheap fields at discovery, the rest
    only for opportunities that reach deep analysis / packaging."""
    id: Optional[int] = None
    candidate_id: int
    source: str = ""
    source_id: str = ""                   # stable id within the source
    source_url: str = ""
    application_url: str = ""
    dedup_key: str = ""
    source_refs: list[str] = Field(default_factory=list)  # other sources that had this opp

    company: str = ""
    title: str = ""
    location: str = ""
    work_mode: str = ""                   # remote | onsite | hybrid | ""
    employment_type: str = ""
    salary: str = ""
    description_raw: str = ""
    jd_text: str = ""                     # normalized text fed to V1
    technologies: list[str] = Field(default_factory=list)

    # cheap, deterministic signals (pre-LLM)
    cheap_score: float = 0.0
    # deep-analysis outputs (V1 reuse) — optional until analysed
    requirements: Optional[JDRequirements] = None
    matches: list[RequirementMatch] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)
    match_score: float = 0.0              # V1 requirement coverage
    opportunity_score: float = 0.0        # final ranking blend
    job_id: Optional[int] = None          # set only when a package is prepared
    cover_letter: str = ""                # drafted at package prep (§27)

    status: OpportunityStatus = OpportunityStatus.DISCOVERED
    discovered_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    closing_date: str = ""


class BatchStatus(str, Enum):
    PREPARATION = "PREPARATION"
    READY = "READY"
    ARCHIVED = "ARCHIVED"


class ApplicationBatch(BaseModel):
    """A controlled set of selected opportunities (§23). `max_opportunities` is a hard
    ceiling enforced at selection time — never auto-backfilled (§24)."""
    id: Optional[int] = None
    candidate_id: int
    name: str = ""
    max_opportunities: int = 10
    target_roles: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    opportunity_ids: list[int] = Field(default_factory=list)
    status: BatchStatus = BatchStatus.PREPARATION
    # V3: default approval mode inherited by this batch's application tasks (§10). Stored as
    # a string here (the ApprovalMode enum is defined in the V3 section below); the queue
    # coerces it. Defaults to the safe middle option.
    approval_mode: str = "REVIEW_BEFORE_SUBMIT"
    created_at: str = Field(default_factory=_now)


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class DiscoveryRun(BaseModel):
    """One discovery execution. Progress + real counts are written as it runs so the UI
    can poll instead of holding an HTTP request open (§41). Numbers are never faked (§9)."""
    id: Optional[int] = None
    candidate_id: int
    status: RunStatus = RunStatus.RUNNING
    stage: str = ""                       # human-readable current stage
    sources_checked: int = 0
    sources_successful: int = 0
    sources_skipped: int = 0
    discovered: int = 0
    after_filtering: int = 0
    after_dedup: int = 0
    deeply_analyzed: int = 0
    shortlisted: int = 0
    source_health: list[SourceHealth] = Field(default_factory=list)
    opportunity_ids: list[int] = Field(default_factory=list)
    error: str = ""
    created_at: str = Field(default_factory=_now)
    finished_at: str = ""


# =========================================================================== #
# V3 — Application Automation                                                  #
# =========================================================================== #
class ApprovalMode(str, Enum):
    """How much human involvement an application requires (§9)."""
    MANUAL = "MANUAL"                        # fill only; user submits
    REVIEW_BEFORE_SUBMIT = "REVIEW_BEFORE_SUBMIT"  # fill, then user approves before submit
    AUTONOMOUS = "AUTONOMOUS"                # submit automatically when safe


class ApplicationStatus(str, Enum):
    """Application task lifecycle (§8). Transitions are constrained in state_machine.py."""
    READY = "READY"
    QUEUED = "QUEUED"
    PAUSED = "PAUSED"
    OPENING = "OPENING"
    INSPECTING = "INSPECTING"
    FILLING = "FILLING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"      # filled, awaiting human approve (manual/review)
    USER_ACTION_REQUIRED = "USER_ACTION_REQUIRED"  # unknown/high-impact question needs user
    LOGIN_REQUIRED = "LOGIN_REQUIRED"        # site needs authentication (§25)
    BLOCKED = "BLOCKED"                       # CAPTCHA / anti-bot — never bypassed (§22)
    FAILED = "FAILED"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    SUBMISSION_UNCERTAIN = "SUBMISSION_UNCERTAIN"  # submitted but no confirmation (§31)
    CANCELLED = "CANCELLED"


# Statuses that mean "an application really went through" — the ONLY ones that set
# Opportunity.status = APPLIED (§30). SUBMISSION_UNCERTAIN deliberately excluded.
APPLIED_STATUSES = {ApplicationStatus.SUBMITTED, ApplicationStatus.CONFIRMED}
# Terminal statuses — the runner does no further work from here.
TERMINAL_STATUSES = {
    ApplicationStatus.CONFIRMED, ApplicationStatus.SUBMITTED,
    ApplicationStatus.SUBMISSION_UNCERTAIN, ApplicationStatus.FAILED,
    ApplicationStatus.CANCELLED,
}


class AnswerSource(str, Enum):
    CANDIDATE_PROFILE = "CANDIDATE_PROFILE"
    APPLICATION_PACKAGE = "APPLICATION_PACKAGE"   # tailored résumé / cover letter
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE"
    LLM_GENERATED = "LLM_GENERATED"
    USER_PROVIDED = "USER_PROVIDED"
    UNRESOLVED = "UNRESOLVED"                       # no safe answer yet


class FieldType(str, Enum):
    text = "text"
    email = "email"
    tel = "tel"
    url = "url"
    number = "number"
    date = "date"
    textarea = "textarea"
    select = "select"
    radio = "radio"
    checkbox = "checkbox"
    file = "file"
    button = "button"
    unknown = "unknown"


class ApplicationQuestion(BaseModel):
    """A structured representation of one application form field/question (§12)."""
    field_key: str = ""                      # opaque driver handle (never a CSS selector)
    question_text: str = ""
    name: str = ""                           # html name/id, for logging
    field_type: FieldType = FieldType.text
    required: bool = False
    options: list[str] = Field(default_factory=list)
    answer: str = ""
    answer_source: AnswerSource = AnswerSource.UNRESOLVED
    confidence: float = 0.0
    requires_review: bool = False
    reason: str = ""


class ApplicationAnswer(BaseModel):
    """Structured LLM output for a semantic question (§17). Validated before use."""
    answer: str = ""
    source_evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    requires_review: bool = False


class TaskEvent(BaseModel):
    """One structured browser-task log line (§33). Field NAMES only — never values,
    passwords, cookies or tokens."""
    at: str = Field(default_factory=_now)
    event: str
    detail: str = ""


class ApplicationTask(BaseModel):
    """A single application attempt for one opportunity (§7). One task per selected
    opportunity; a retry mutates this task, never creates a sibling — that keeps the V2
    batch maximum true by construction (§29)."""
    id: Optional[int] = None
    opportunity_id: int
    batch_id: Optional[int] = None
    candidate_id: int
    application_url: str = ""
    status: ApplicationStatus = ApplicationStatus.READY
    approval_mode: ApprovalMode = ApprovalMode.REVIEW_BEFORE_SUBMIT

    resume_artifact: str = ""                # resolved file/endpoint for the tailored résumé
    cover_letter: str = ""
    current_page: int = 0
    questions: list[ApplicationQuestion] = Field(default_factory=list)
    logs: list[TaskEvent] = Field(default_factory=list)

    error_code: str = ""
    error_message: str = ""
    confirmation_reference: str = ""
    retry_count: int = 0

    created_at: str = Field(default_factory=_now)
    started_at: str = ""
    finished_at: str = ""
    submitted_at: str = ""

    def log(self, event: str, detail: str = "") -> None:
        self.logs.append(TaskEvent(event=event, detail=detail))
