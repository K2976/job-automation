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
export interface RoleProfile { id: number; name: string; target_role: string; job_id: number }
