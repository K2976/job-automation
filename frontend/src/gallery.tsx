/* Dev-only visual gallery: renders the real Shell + panels with mock data so screens can
   be screenshotted without a backend. Not part of the production build (index.html only). */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { Shell } from './App'
import type { Engine } from './store'
import type {
  AnalysisResult, GenerationResult, KBEntity, ModificationSuggestion,
} from './api/types'

const noop = async () => {}
const ent = (id: number, t: KBEntity['entity_type'], name: string, content: string, status: KBEntity['status'] = 'ORIGINAL'): KBEntity =>
  ({ id, candidate_id: 1, entity_type: t, name, content, data: {}, domain: '', status, source: 'master_resume' })

const entities: KBEntity[] = [
  ent(1, 'skill', 'Python', 'Python'), ent(2, 'skill', 'SQL', 'SQL'),
  ent(3, 'skill', 'PostgreSQL', 'PostgreSQL'), ent(4, 'skill', 'SwiftUI', 'SwiftUI'),
  ent(5, 'skill', 'FastAPI', 'FastAPI'), ent(6, 'skill', 'Machine Learning', 'ML', 'USER_CONFIRMED'),
  ent(10, 'project', 'Parkezy', 'Real-time smart-parking app: FastAPI backend, PostgreSQL persistence, REST APIs for live slot availability.'),
  ent(11, 'project', 'Setu AI', 'Edge-AI anomaly detection: 1D-CNN on a MAX78000 microcontroller with a Python feature-engineering pipeline.'),
  ent(20, 'experience', 'iOS Developer at Freelance', 'Shipped iOS apps with FastAPI + PostgreSQL backends for clients.'),
  ent(30, 'education', 'B.Tech Computer Engineering', 'B.Tech in Computer Engineering, Example Institute of Technology'),
]

const analysis: AnalysisResult = {
  job_id: 1,
  requirements: { role: 'Data Engineer', required_skills: [], preferred_skills: [], responsibilities: [], technologies: [], domain_terms: [], keywords: [], experience_expectations: [] },
  matches: [
    { requirement: 'Python', kind: 'required', match_status: 'STRONG_MATCH', score: 1, reason: 'Directly present in your profile and used across projects.', evidence: [{ entity_id: 1, entity_type: 'skill', name: 'Python', snippet: 'Python', score: 1, status: 'ORIGINAL' }] },
    { requirement: 'SQL', kind: 'required', match_status: 'STRONG_MATCH', score: 1, reason: 'Directly present in your profile.', evidence: [] },
    { requirement: 'PostgreSQL', kind: 'required', match_status: 'STRONG_MATCH', score: 0.8, reason: 'Used in Parkezy for the persistence layer.', evidence: [{ entity_id: 10, entity_type: 'project', name: 'Parkezy', snippet: 'PostgreSQL persistence, REST APIs for live slot availability.', score: 0.8, status: 'ORIGINAL' }] },
    { requirement: 'data pipeline', kind: 'required', match_status: 'PARTIAL_MATCH', score: 0.31, reason: 'Related data-processing experience in Setu AI, but no explicit production pipeline.', evidence: [{ entity_id: 11, entity_type: 'project', name: 'Setu AI', snippet: 'Python feature-engineering pipeline', score: 0.31, status: 'ORIGINAL' }] },
    { requirement: 'Docker', kind: 'preferred', match_status: 'USER_CONFIRMATION_REQUIRED', score: 0.14, reason: 'Loosely related backend experience — confirm whether you have used Docker before claiming it.', evidence: [] },
    { requirement: 'Airflow', kind: 'preferred', match_status: 'MISSING', score: 0, reason: 'No supporting evidence in your profile.', evidence: [] },
    { requirement: 'Spark', kind: 'preferred', match_status: 'MISSING', score: 0, reason: 'No supporting evidence in your profile.', evidence: [] },
    { requirement: 'ETL', kind: 'required', match_status: 'MISSING', score: 0, reason: 'No supporting evidence in your profile.', evidence: [] },
  ],
  gaps: [],
  plan: {
    role: 'Data Engineer',
    suggestions: [],
    emphasize: ['Python', 'SQL', 'PostgreSQL', 'REST', 'real-time'],
    deemphasize: ['SwiftUI', 'Swift', 'iOS', 'Edge Impulse'],
    reorder: ['Parkezy', 'Setu AI'],
  },
}

const suggestions: ModificationSuggestion[] = [
  { id: '1-rewrite-parkezy', type: 'REWRITE', target: 'Parkezy', current: 'Built an iOS parking app in SwiftUI with a FastAPI backend and live availability.', suggested: 'Designed the PostgreSQL schema and SQL data-access layer for a real-time parking platform, exposing REST APIs that served live availability data.', reason: 'Foregrounds the backend/data work the Data Engineer role emphasises.', requires_approval: true, status: 'AI_SUGGESTED' },
  { id: '1-rewrite-setu', type: 'REWRITE', target: 'Setu AI', current: 'Edge-AI anomaly detection with a 1D-CNN on a microcontroller.', suggested: 'Built a Python pipeline to clean, window and label sensor time-series, then engineered features for on-device inference.', reason: 'Highlights the data-processing pipeline over the edge-ML framing.', requires_approval: true, status: 'AI_SUGGESTED' },
  { id: '1-addskill-etl', type: 'ADD_SKILL', target: 'ETL', current: 'not in profile', suggested: 'ETL', reason: '"ETL" appears in the JD but is not in your profile. Only include it if you genuinely have this experience.', requires_approval: true, status: 'AI_SUGGESTED' },
  { id: '1-addskill-airflow', type: 'ADD_SKILL', target: 'Airflow', current: 'not in profile', suggested: 'Airflow', reason: '"Airflow" appears in the JD but is not in your profile.', requires_approval: true, status: 'REJECTED' },
  { id: '1-addskill-spark', type: 'ADD_SKILL', target: 'Spark', current: 'not in profile', suggested: 'Spark', reason: '"Spark" appears in the JD but is not in your profile.', requires_approval: true, status: 'AI_SUGGESTED' },
]

const generation: GenerationResult = {
  resume: {
    candidate: { id: 1, name: 'Kartik Sanghi', email: 'kartik@example.com', phone: '+91 90000 00000', location: 'Pune, India', headline: '', links: [] },
    target_role: 'Data Engineer',
    summary: 'Data Engineer with hands-on experience building real-time data solutions — PostgreSQL schemas, SQL data-access layers and REST APIs — using Python across backend and edge-AI projects.',
    skills: ['Python', 'SQL', 'PostgreSQL', 'REST'],
    sections: [
      { title: 'Projects', name: '', bullets: [
        { text: 'Parkezy: Designed the PostgreSQL schema and SQL data-access layer for a real-time parking platform, exposing REST APIs that served live availability data.', status: 'GENERATED', evidence_entity_id: 10 },
        { text: 'Setu AI: Built a Python pipeline to clean, window and label sensor time-series, then engineered features for on-device inference.', status: 'GENERATED', evidence_entity_id: 11 },
      ] },
      { title: 'Experience', name: '', bullets: [
        { text: 'iOS Developer at Freelance — shipped apps with FastAPI + PostgreSQL backends for clients.', status: 'GENERATED', evidence_entity_id: 20 },
      ] },
      { title: 'Education', name: '', bullets: [
        { text: 'B.Tech in Computer Engineering, Example Institute of Technology', status: 'GENERATED', evidence_entity_id: 30 },
      ] },
    ],
    markdown: '',
  },
  validation: {
    claims: [
      { text: 'Skill: PostgreSQL', status: 'SUPPORTED_BY_ORIGINAL', evidence_entity_id: 3, reason: '' },
      { text: 'Skill: Python', status: 'SUPPORTED_BY_ORIGINAL', evidence_entity_id: 1, reason: '' },
      { text: 'Parkezy: Designed the PostgreSQL schema…', status: 'SUPPORTED_BY_ORIGINAL', evidence_entity_id: 10, reason: '' },
      { text: 'Distributed processing across a Spark cluster', status: 'UNSUPPORTED', evidence_entity_id: null, reason: "'Spark' has no supporting evidence." },
    ],
    supported: 12, unsupported: 1, needs_approval: 0,
  },
  ats: {
    overall_score: 0.72, skill_coverage: 0.78, keyword_coverage: 0.55,
    requirement_coverage: 0.7, project_relevance: 1, components: {},
    matched_keywords: [], missing_skills: ['ETL', 'Airflow', 'Spark'], potential_issues: [],
  },
  comparison: { added_lines: [], removed_lines: [], skills_added: ['Machine Learning'], skills_dropped: ['SwiftUI', 'Swift', 'Edge Impulse', 'Pandas'], similarity: 0.4 },
  matches: analysis.matches,
}

function mockEngine(over: Partial<Engine>): Engine {
  return {
    health: { status: 'ok', llm_provider: 'groq', embedding_provider: 'local' },
    candidate: null, entities: [], sampleJds: { 'Data Engineer': '', 'Backend Engineer': '', 'AI/ML Engineer': '' },
    jdText: '', analysis: null, suggestions: [], generation: null, roleProfiles: [],
    step: 0, busy: null, error: null,
    setStep: () => {}, setJd: () => {}, seed: noop, ingest: noop, ingestFile: noop,
    editCandidate: noop, addEntity: noop, editEntity: noop, deleteEntity: noop,
    analyze: noop, approve: noop, generate: noop, saveRoleProfile: noop,
    ...over,
  }
}

const candidate = { id: 1, name: 'Kartik Sanghi', email: 'kartik@example.com', phone: '', location: 'Pune, India', headline: 'iOS developer with backend, data & edge-AI experience', links: [] }

const STATES: Record<string, Engine> = {
  start: mockEngine({ step: 0 }),
  profile: mockEngine({ step: 0, candidate, entities, roleProfiles: [{ id: 1, name: 'DE view', target_role: 'Data Engineer', job_id: 1 }] }),
  analysis: mockEngine({ step: 1, candidate, entities, analysis, jdText: 'We are hiring a Data Engineer…' }),
  modifications: mockEngine({ step: 2, candidate, entities, analysis, suggestions }),
  resume: mockEngine({ step: 3, candidate, entities, analysis, generation, roleProfiles: [{ id: 1, name: 'DE view', target_role: 'Data Engineer', job_id: 1 }] }),
}

const which = new URLSearchParams(location.search).get('s') ?? 'start'
const engine = STATES[which] ?? STATES.start

createRoot(document.getElementById('root')!).render(
  <StrictMode><Shell engine={engine} /></StrictMode>,
)
