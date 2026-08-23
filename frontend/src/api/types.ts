// Hand-maintained to match backend/app/models.py. Kept minimal — only what the UI uses.

export type Status =
  | 'ORIGINAL' | 'AI_SUGGESTED' | 'USER_CONFIRMED' | 'USER_EDITED'
  | 'GENERATED' | 'REJECTED'

export type MatchStatus =
  | 'STRONG_MATCH' | 'PARTIAL_MATCH' | 'WEAK_MATCH' | 'MISSING'
  | 'USER_CONFIRMATION_REQUIRED'

export type ClaimStatus =
  | 'SUPPORTED_BY_ORIGINAL' | 'SUPPORTED_BY_USER_CONFIRMATION'
  | 'AI_SUGGESTED_NOT_APPROVED' | 'UNSUPPORTED'

export type EntityType =
  | 'skill' | 'project' | 'experience' | 'education' | 'certification' | 'achievement'

export type ApprovalAction = 'ACCEPT' | 'REJECT' | 'EDIT'

export interface Candidate {
  id?: number
  name: string; email: string; phone: string
  location: string; headline: string; links: string[]
}

export interface KBEntity {
  id: number; candidate_id: number; entity_type: EntityType
  name: string; content: string; data: Record<string, unknown>
  domain: string; status: Status; source: string
}

export interface JDRequirements {
  role: string
  required_skills: string[]; preferred_skills: string[]
  responsibilities: string[]; technologies: string[]
  domain_terms: string[]; keywords: string[]; experience_expectations: string[]
}

export interface EvidenceRef {
  entity_id: number | null; entity_type: EntityType; name: string
  snippet: string; score: number; status: Status
}

export interface RequirementMatch {
  requirement: string; kind: string; match_status: MatchStatus
  score: number; evidence: EvidenceRef[]; reason: string
}

export interface GapItem {
  requirement: string; kind: string; category: MatchStatus
  reason: string; suggested_action: string
}

export interface ModificationSuggestion {
  id: string; type: string; target: string
  current: string; suggested: string; reason: string
  requires_approval: boolean; status: Status
}

export interface ModificationPlan {
  role: string; suggestions: ModificationSuggestion[]
  emphasize: string[]; deemphasize: string[]; reorder: string[]
}

export interface AnalysisResult {
  job_id: number; requirements: JDRequirements
  matches: RequirementMatch[]; gaps: GapItem[]; plan: ModificationPlan
}

export interface ResumeBullet { text: string; status: Status; evidence_entity_id: number | null }
export interface ResumeSection { title: string; name: string; bullets: ResumeBullet[] }
export interface TailoredResume {
  candidate: Candidate; target_role: string; summary: string
  skills: string[]; sections: ResumeSection[]; markdown: string
}

export interface Claim {
  text: string; status: ClaimStatus; evidence_entity_id: number | null; reason: string
}
export interface ValidationReport {
  claims: Claim[]; supported: number; unsupported: number; needs_approval: number
}

export interface ATSReport {
  overall_score: number; skill_coverage: number; keyword_coverage: number
  requirement_coverage: number; project_relevance: number
  components: Record<string, number>
  matched_keywords: string[]; missing_skills: string[]; potential_issues: string[]
}

export interface Comparison {
  added_lines: string[]; removed_lines: string[]
  skills_added: string[]; skills_dropped: string[]; similarity: number
}

export interface GenerationResult {
  resume: TailoredResume; validation: ValidationReport
  ats: ATSReport; comparison: Comparison; matches: RequirementMatch[]
}

export interface Explanation {
  requirement: string; found: boolean; status?: MatchStatus; relevance?: number
  reason?: string
  evidence?: { name: string; type: string; snippet: string; score: number; status: string }[]
}

export interface Health { status: string; llm_provider: string; embedding_provider: string }
export interface WorkerInfo { worker_id: string; status: string; current_task_id: number | null; last_seen: string }
export interface WorkerStatusResponse {
  online: boolean; inline: boolean; heartbeat_timeout: number; workers: WorkerInfo[]
}
export interface RoleProfile { id: number; name: string; target_role: string; job_id: number }

/* --- V2: Opportunity Intelligence --- */
export type OpportunityStatus =
  | 'DISCOVERED' | 'FILTERED' | 'ANALYZED' | 'SHORTLISTED' | 'TAILORING'
  | 'READY_TO_APPLY' | 'APPLIED' | 'REJECTED' | 'SKIPPED' | 'EXPIRED' | 'BLOCKED'

export interface SearchPreferences {
  candidate_id?: number
  target_roles: string[]; target_domains: string[]; preferred_locations: string[]
  remote_preference: string; employment_types: string[]; experience_level: string
  minimum_match_score: number; technology_preferences: string[]
  excluded_roles: string[]; excluded_companies: string[]; sources: string[]
  result_limit: number
}

export interface Opportunity {
  id: number; candidate_id: number
  source: string; source_url: string; application_url: string; source_refs: string[]
  company: string; title: string; location: string; work_mode: string
  employment_type: string; salary: string; description_raw: string
  technologies: string[]
  cheap_score: number; match_score: number; opportunity_score: number
  requirements: JDRequirements | null; matches: RequirementMatch[]; gaps: GapItem[]
  job_id: number | null; cover_letter: string
  status: OpportunityStatus; discovered_at: string; closing_date: string
}

export interface WhyApply {
  match_score: number; opportunity_score: number
  strong_matches: string[]; partial_matches: string[]; gaps: string[]; best_evidence: string[]
}

export interface SourceHealth {
  name: string; configured: boolean; status: string; detail: string; discovered: number
}

export interface DiscoveryRun {
  id: number; candidate_id: number; status: 'RUNNING' | 'COMPLETE' | 'FAILED'
  stage: string
  sources_checked: number; sources_successful: number; sources_skipped: number
  discovered: number; after_filtering: number; after_dedup: number
  deeply_analyzed: number; shortlisted: number
  source_health: { source: string; status: string; discovered: number; detail: string }[]
  opportunity_ids: number[]; error: string
}

export interface ApplicationBatch {
  id: number; candidate_id: number; name: string; max_opportunities: number
  target_roles: string[]; opportunity_ids: number[]
  status: 'PREPARATION' | 'READY' | 'ARCHIVED'; created_at: string
  approval_mode: string
}

/* --- V3: Application Automation --- */
export type ApprovalMode = 'MANUAL' | 'REVIEW_BEFORE_SUBMIT' | 'AUTONOMOUS'

export type ApplicationTaskStatus =
  | 'READY' | 'QUEUED' | 'PAUSED' | 'OPENING' | 'INSPECTING' | 'FILLING'
  | 'REVIEW_REQUIRED' | 'USER_ACTION_REQUIRED' | 'LOGIN_REQUIRED' | 'BLOCKED'
  | 'FAILED' | 'SUBMITTED' | 'CONFIRMED' | 'SUBMISSION_UNCERTAIN' | 'CANCELLED'

export interface ApplicationQuestion {
  field_key: string; question_text: string; name: string; field_type: string
  required: boolean; options: string[]; answer: string; answer_source: string
  confidence: number; requires_review: boolean; reason: string
}

export interface TaskEvent { at: string; event: string; detail: string }

export interface ApplicationTask {
  id: number; opportunity_id: number; batch_id: number | null; candidate_id: number
  application_url: string; status: ApplicationTaskStatus; approval_mode: ApprovalMode
  resume_artifact: string; cover_letter: string; current_page: number
  questions: ApplicationQuestion[]; logs: TaskEvent[]
  error_code: string; error_message: string; confirmation_reference: string
  retry_count: number; created_at: string; started_at: string
  finished_at: string; submitted_at: string
}

export interface UnresolvedQuestion { key: string; text: string }

export interface ApplicationSummary {
  questions: number; deterministic: number; llm_generated: number; user_provided: number
  unresolved: number; unresolved_questions: UnresolvedQuestion[]; can_submit: boolean
  status: string; approval_mode: string
}
