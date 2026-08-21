# CLAUDE.md — Adaptive RAG Resume Engineering System

## 1. Project Overview

### Working Project Name

**Adaptive Resume Engineer**

The final product name can be changed later.

### Core Idea

Build an RAG-powered application that takes:

1. A candidate's **master/original resume or professional profile**
2. A **Job Description (JD)** for a target role

and intelligently produces a **role-specific tailored resume**.

The system should reproduce and automate the manual process a candidate normally performs when applying to different types of jobs.

Example:

A candidate may have a master resume primarily oriented toward iOS development, but they may also have experience involving:

- Python
- SQL
- APIs
- databases
- backend systems
- data processing
- cybersecurity
- ML
- IoT
- cloud
- etc.

When applying for a Data Engineer role, the system should identify the portions of the candidate's experience that are relevant to Data Engineering and **reframe, reorder, strengthen, shorten, or rewrite them** according to the JD.

When applying for an AI Engineer role, it should produce a different optimized view of the same underlying candidate profile.

The system is therefore **not simply a resume generator**.

It is an:

> **RAG-powered adaptive resume intelligence and transformation system.**

---

# 2. Primary Product Principle

The application should treat the candidate's professional information as a **living knowledge base** rather than a single static resume.

The candidate has:

```text
                    MASTER CANDIDATE PROFILE
                              |
          -------------------------------------------
          |              |             |             |
       Skills         Projects     Experience   Achievements
          |              |             |             |
          -------------------------------------------
                              |
                    Role-specific views
                              |
          -------------------------------------------
          |              |             |             |
      AI Engineer    Data Engineer   Backend      Cybersecurity
```

The original information remains reusable.

A tailored resume is a **view/transformation of the master profile**, not a replacement for it.

---

# 3. Core V1 Workflow

The main V1 flow is:

```text
Resume / Candidate Profile
            |
            v
     Resume Ingestion
            |
            v
Candidate Knowledge Base
            |
            |
JD ----------+
|
v
JD Analysis
|
v
Requirement Extraction
|
v
Hybrid Retrieval
|
v
Candidate Evidence Matching
|
v
Gap Analysis
|
v
Suggested Resume Modification Plan
|
v
Human Approval / Editing
|
v
Tailored Resume Generation
|
v
ATS / Relevance Analysis
|
v
Evidence / Claim Validation
|
v
Final Resume
```

---

# 4. Product Goals

The system should:

- Understand a job description semantically.
- Extract required and preferred skills.
- Extract responsibilities and role expectations.
- Determine which candidate experiences are relevant.
- Retrieve relevant projects, skills, experience, achievements, certifications, etc.
- Rank candidate evidence by relevance.
- Detect strong matches, partial matches, and gaps.
- Suggest modifications to the candidate's resume.
- Suggest ways to reposition existing projects and experience.
- Allow candidate-approved additions or modifications.
- Rewrite project descriptions and resume sections according to the target role.
- Preserve useful original information while reducing irrelevant information.
- Generate a polished role-specific resume.
- Provide an explanation of why experiences were selected.
- Provide evidence/provenance for generated claims where possible.
- Provide a match/ATS-style analysis.
- Preserve the original master profile.

---

# 5. Important Product Behavior: Human-in-the-Loop

The human-in-the-loop mechanism is **central**, not optional.

The system must NOT silently modify important candidate information.

Instead, it should propose changes.

Example:

```text
Potential Gap Detected

Skill:
NLP

Reason:
NLP appears in the target JD, but there is no explicit NLP evidence
in the current candidate profile.

Suggested action:
Add NLP to this role-specific profile?

[ Accept ] [ Reject ] [ Edit ]
```

Another example:

```text
Project Reframing Suggestion

Project:
Parkezy

Current emphasis:
- SwiftUI
- mobile UI
- iOS architecture

Suggested emphasis for Data Engineer role:
- backend integration
- persistent data
- real-time synchronization
- structured data flow
- API/data layer

[ Accept ] [ Edit ] [ Reject ]
```

The system can suggest information that is not currently present in the master resume, but:

### It must never silently fabricate or inject information.

Any such addition must be:

```text
AI Suggested
        ->
Candidate Approval
        ->
Approved Modification
        ->
Used in Tailored Resume
```

Every accepted modification should maintain provenance.

Recommended statuses:

```text
ORIGINAL
AI_SUGGESTED
USER_CONFIRMED
USER_EDITED
GENERATED
REJECTED
```

This is important both technically and for auditability.

The application should never represent an unapproved AI suggestion as an original candidate fact.

---

# 6. Three Information States

Candidate information should conceptually have three major states.

## 6.1 Verified / Original

Information extracted from the uploaded master resume or directly entered by the candidate.

Example:

```text
Python
SQL
Supabase
FastAPI
1D-CNN
```

## 6.2 User-Confirmed Modification

Information suggested by the system and explicitly accepted/edited by the candidate.

Example:

```text
Candidate confirms:
"PostgreSQL was used in this project."
```

This becomes eligible for generation.

## 6.3 Missing / Unverified

The JD requires something for which no supporting information exists.

The system should flag it and ask the user.

Never silently convert:

```text
Missing
```

into:

```text
Verified experience
```

---

# 7. RAG Philosophy

RAG is a core architectural component.

Do not build:

```text
JD -> LLM -> Resume
```

Instead build:

```text
JD
 |
 v
JD Analyzer
 |
 v
Structured Requirements
 |
 v
Hybrid Retrieval
 |
 +--> Semantic Search
 +--> Keyword Search
 +--> Structured Filters
 |
 v
Reranking
 |
 v
Relevant Candidate Evidence
 |
 v
LLM Reasoning
 |
 v
Modification Plan
 |
 v
User Approval
 |
 v
LLM Generation
```

The LLM should reason over retrieved candidate evidence rather than hallucinating an entire candidate profile from scratch.

---

# 8. LLM Responsibilities

LLMs should be used for tasks that benefit from semantic reasoning and language generation.

## Recommended LLM Tasks

### A. JD Analysis

Convert raw JD into structured information:

```json
{
  "role": "Data Engineer",
  "required_skills": [],
  "preferred_skills": [],
  "responsibilities": [],
  "domain": [],
  "experience_expectations": [],
  "keywords": []
}
```

### B. Requirement Normalization

Understand that:

```text
"Postgres"
"PostgreSQL"
"PostgreSQL database"
```

may refer to the same technology.

But do not collapse technically different technologies simply because they are vaguely related.

### C. Evidence Relevance Reasoning

Given:

```text
JD Requirement
+
Retrieved Candidate Evidence
```

determine:

- relevance
- strength
- contextual usefulness
- possible resume positioning

### D. Gap Analysis

Determine:

- strong match
- partial match
- weak match
- missing skill
- missing evidence

### E. Resume Modification Planning

Determine:

- what to emphasize
- what to reduce
- what to reorder
- what to rewrite
- which project to prioritize
- what additional candidate confirmation is useful

### F. Resume Generation

Generate polished role-specific language.

### G. Validation

Check whether generated claims have supporting candidate evidence or explicit user approval.

---

# 9. Do NOT Use the LLM for Everything

Prefer deterministic code where appropriate.

Examples:

- counting requirements
- calculating match percentages
- sorting
- database operations
- provenance tracking
- validation rules
- schema validation
- file handling
- document generation
- permission checks
- duplicate detection

The application should use:

```text
Deterministic Logic
+
RAG
+
LLM
```

rather than:

```text
LLM everywhere
```

---

# 10. LLM Provider Architecture

The project should use an abstraction layer for LLM providers.

Initial providers:

- Gemini API
- Groq API

Do NOT couple business logic directly to either vendor.

Create an internal interface such as:

```text
LLMProvider
```

with operations conceptually similar to:

```text
generate()
structured_generate()
analyze()
```

The exact implementation can be decided during development.

The provider should be configurable through environment variables.

Example concept:

```text
LLM_PROVIDER=gemini
```

or:

```text
LLM_PROVIDER=groq
```

The architecture should make it easy to add other providers later without rewriting the application.

Do not assume a provider's free-tier limits are permanent.

---

# 11. Embeddings

LLM generation and embedding retrieval are separate concerns.

The embedding model should be abstracted as:

```text
EmbeddingProvider
```

The project should preferably support a low-cost/local embedding option for development so that vector retrieval does not necessarily depend on paid LLM inference.

Embedding configuration must be replaceable.

---

# 12. Retrieval Architecture

Use hybrid retrieval.

Recommended architecture:

```text
JD Requirement
     |
     +--------------------+
     |                    |
     v                    v
Semantic Retrieval    Keyword Retrieval
     |                    |
     +---------+----------+
               |
               v
        Candidate Results
               |
               v
            Reranker
               |
               v
       Top Relevant Evidence
```

Potential components:

### Semantic retrieval

Vector database / vector extension.

### Keyword retrieval

BM25, PostgreSQL full-text search, or another suitable mechanism.

### Structured retrieval

PostgreSQL filters for:

- project
- skill
- domain
- role
- experience
- technology
- source
- confidence
- approval state

The final retrieval pipeline should combine these signals.

---

# 13. Candidate Knowledge Base

The candidate knowledge base should not store the resume as one large chunk.

Break it into meaningful entities.

Suggested entities:

```text
Candidate
|
+-- Skills
|
+-- Projects
|
+-- Experience
|
+-- Education
|
+-- Certifications
|
+-- Achievements
|
+-- Hackathons
|
+-- Publications
|
+-- Courses
|
+-- Responsibilities
|
+-- Technologies
|
+-- Role Profiles
|
+-- User-approved modifications
```

---

# 14. Suggested Project Entity

A project should contain structured fields similar to:

```text
Project
- id
- name
- summary
- detailed_description
- domain
- technologies
- programming_languages
- architecture
- responsibilities
- achievements
- metrics
- links
- source
- verification_status
- created_at
- updated_at
```

Do not over-engineer the exact schema before examining implementation requirements.

---

# 15. Metadata for RAG

Retrieved chunks should have useful metadata.

Example:

```json
{
  "entity_type": "project",
  "entity_id": "...",
  "project_name": "Setu AI",
  "domain": "edge_ai",
  "technologies": [
    "Python",
    "1D-CNN",
    "MAX78000",
    "Edge Impulse"
  ],
  "source": "master_resume",
  "status": "ORIGINAL"
}
```

This metadata allows structured filtering and improves retrieval quality.

---

# 16. Role-Specific Profiles

The candidate should have one master profile but may have multiple role-specific views.

Example:

```text
Master Profile
 |
 +-- AI Engineer Profile
 +-- Data Engineer Profile
 +-- Backend Engineer Profile
 +-- Cybersecurity Engineer Profile
 +-- iOS Developer Profile
```

These are not independent candidate records.

They are transformations/views over the master knowledge base.

This allows the system to reuse past accepted modifications.

---

# 17. Resume Transformation

The application should think in terms of **transformation**, not just rewriting.

For each target role, create an intermediate:

## Resume Modification Plan

Example:

```text
Target Role:
Data Engineer

KEEP:
- backend experience
- databases
- APIs

EMPHASIZE:
- SQL
- data flow
- backend integration
- data processing

DE-EMPHASIZE:
- mobile UI details
- visual implementation details

REORDER:
- data/backend project higher

REWRITE:
- Project A description
- Project B description

SUGGEST:
- PostgreSQL
- ETL

REQUIRES APPROVAL:
- PostgreSQL
- ETL
```

This plan should exist before final resume generation.

---

# 18. Gap Analysis

Gap analysis should classify requirements into categories.

Suggested categories:

```text
STRONG_MATCH
PARTIAL_MATCH
WEAK_MATCH
MISSING
USER_CONFIRMATION_REQUIRED
```

Example:

```text
Python        -> STRONG_MATCH
SQL           -> STRONG_MATCH
FastAPI       -> PARTIAL_MATCH
Docker        -> USER_CONFIRMATION_REQUIRED
Kubernetes    -> MISSING
```

The system should explain the reason for each classification.

---

# 19. Match Scoring

Do not pretend a single percentage is scientifically exact.

The score is a product-level indicator.

Possible components:

```text
Skill Match
Experience Relevance
Project Relevance
Responsibility Match
Keyword Match
Domain Match
```

The weights must be configurable.

Example:

```text
overall_score =
    skill_score * 0.35
  + experience_score * 0.20
  + project_score * 0.20
  + responsibility_score * 0.15
  + keyword_score * 0.10
```

This is only an initial model.

Evaluate it and revise based on actual examples.

---

# 20. Resume Generation

The final generation prompt should contain:

```text
Original Candidate Data
+
Target JD
+
Structured JD Requirements
+
Retrieved Evidence
+
Modification Plan
+
Approved User Modifications
+
Resume Formatting Requirements
```

The generator should not receive arbitrary unrelated candidate content when it is unnecessary.

The output should be role-focused.

---

# 21. Evidence-Backed Generation

Every significant generated claim should ideally have provenance.

Conceptually:

```text
Generated Claim
       |
       v
Evidence Lookup
       |
       +--> Original candidate evidence
       |
       +--> User-confirmed modification
       |
       +--> Unsupported
```

If unsupported:

```text
FLAG
```

or require approval.

The user should be able to click something like:

> Why is this included?

and see:

```text
JD requirement:
"Experience with API development"

Candidate evidence:
Project X -> FastAPI

Relevance:
High

Status:
Original candidate information
```

---

# 22. Anti-Hallucination / Claim Validation

A post-generation validator is required.

Do not blindly trust the generation model.

The validation layer should detect:

- unsupported technologies
- invented metrics
- invented job titles
- invented responsibilities
- invented employers
- unsupported years of experience
- fabricated achievements
- unsupported certifications

The system should distinguish:

```text
Supported by Original Profile
Supported by User Confirmation
AI Suggested / Not Yet Approved
Unsupported
```

---

# 23. Resume Comparison

The UI should eventually provide:

```text
Original Resume
vs
Tailored Resume
```

with:

- added content
- removed content
- rewritten content
- reordered content

This is important for transparency.

---

# 24. ATS / Relevance Analysis

The generated resume should be analyzed after generation.

Possible metrics:

```text
JD Keyword Coverage
Required Skill Coverage
Role Relevance
Section Relevance
Project Relevance
Readability
Potential ATS Issues
```

Do not claim that an arbitrary percentage guarantees ATS success.

Call it:

> ATS-style analysis / JD alignment analysis.

---

# 25. Future Features — DO NOT IMPLEMENT IN V1

The following are explicitly future roadmap features.

## V2 — Job Discovery

Automatically search for jobs matching:

- candidate profile
- preferred role
- location
- remote/on-site
- experience
- salary
- technology/domain

Potential future flow:

```text
Candidate Profile
      |
      v
Job Search Agent
      |
      v
Job Sources
      |
      v
JD Collector
      |
      v
JD Analyzer
      |
      v
Candidate Match Score
      |
      v
Job Dashboard
```

This must NOT be part of the initial implementation.

---

## V3 — Application Automation

Potential future flow:

```text
Find Job
   |
Analyze JD
   |
Tailor Resume
   |
Generate Cover Letter
   |
Fill Application
   |
Human Review
   |
Submit
```

The recommended product design is to retain human confirmation before final submission.

Do NOT implement this in V1.

---

# 26. Initial Technology Direction

Preferred initial stack:

## Frontend

- Next.js
- TypeScript
- modern React
- shadcn/ui where appropriate

## Backend

- FastAPI
- Python
- Pydantic

## Database

- PostgreSQL

Use PostgreSQL for structured candidate/profile/application data.

For vector retrieval:

- PostgreSQL with pgvector, or
- another vector database if there is a compelling reason.

Prefer reducing infrastructure complexity during V1.

## LLM

Initial providers:

- Gemini API
- Groq API

## Embeddings

Pluggable embedding provider, preferably with a local/development-friendly option.

## Document Processing

Use appropriate Python libraries for:

- PDF extraction
- DOCX extraction
- text normalization

Select libraries based on actual implementation requirements.

## Resume Output

Support structured generation that can later render to:

- HTML
- PDF
- DOCX if needed

Do not lock the internal model to one output format.

---

# 27. Recommended High-Level Repository Structure

The exact structure may change after implementation analysis, but aim for clear separation.

```text
/
├── CLAUDE.md
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE
├── .gitignore
├── .env.example
│
├── docs/
│   ├── architecture.md
│   ├── product-overview.md
│   ├── rag-pipeline.md
│   ├── candidate-knowledge-base.md
│   ├── data-model.md
│   ├── llm-strategy.md
│   ├── retrieval.md
│   ├── resume-generation.md
│   ├── gap-analysis.md
│   ├── validation.md
│   ├── api.md
│   ├── setup.md
│   ├── development.md
│   ├── roadmap.md
│   └── decisions/
│       └── ...
│
├── frontend/
│   └── ...
│
├── backend/
│   └── ...
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evaluation/
│
├── scripts/
│   └── ...
│
└── data/
    └── ...
```

Do not create unnecessary directories merely to match this example.

Use a structure that makes architectural boundaries obvious.

---

# 28. Documentation Requirements

Documentation is a first-class deliverable.

At minimum maintain:

### README.md

Must explain:

- what the project does
- why it exists
- main features
- architecture summary
- local setup
- environment variables
- development workflow
- how to run tests
- how to start frontend/backend
- current project status

### docs/product-overview.md

Explain:

- problem
- target user
- user journey
- core workflow
- V1 boundaries
- future roadmap

### docs/architecture.md

Explain:

- system architecture
- frontend/backend interaction
- data flow
- LLM flow
- RAG flow
- validation flow

### docs/candidate-knowledge-base.md

Explain:

- candidate data model
- entities
- chunking
- metadata
- provenance

### docs/rag-pipeline.md

Explain:

- ingestion
- chunking
- embedding
- retrieval
- keyword search
- reranking
- context assembly
- generation

### docs/llm-strategy.md

Explain:

- model abstraction
- providers
- model selection
- structured generation
- fallback behavior
- token/cost considerations

### docs/resume-generation.md

Explain:

- modification plan
- approved changes
- prompt architecture
- generation process

### docs/validation.md

Explain:

- claim extraction
- evidence validation
- unsupported claim handling
- provenance

### docs/roadmap.md

Separate:

```text
V1
V2
V3
```

and clearly mark job search/application automation as future work.

### Architecture Decision Records

For meaningful architectural decisions, create concise ADRs.

Example:

```text
docs/decisions/ADR-001-postgresql-pgvector.md
docs/decisions/ADR-002-llm-provider-abstraction.md
```

Do not create ADRs for trivial implementation choices.

---

# 29. Testing Requirements

Testing is required.

Implement tests for:

- JD parsing
- structured JD output validation
- candidate ingestion
- chunk creation
- metadata correctness
- retrieval
- matching
- gap analysis
- modification-plan generation
- approval logic
- resume generation
- claim validation
- API endpoints
- important frontend behavior

For RAG-specific testing, maintain an evaluation dataset containing examples of:

```text
JD
+
Candidate Profile
+
Expected Relevant Evidence
+
Expected Gaps
+
Expected Role Positioning
```

This allows retrieval and generation quality to be measured rather than judged only manually.

---

# 30. Prompt Engineering Requirements

Do not scatter giant prompts throughout the codebase.

Prompts should be:

- versioned
- organized
- testable
- easy to change

Prefer dedicated prompt modules/files.

Examples:

```text
prompts/
├── jd_analysis
├── evidence_matching
├── gap_analysis
├── modification_plan
├── resume_generation
└── claim_validation
```

Use structured outputs wherever practical.

Prefer schemas over free-form text for machine-consumed LLM output.

---

# 31. Security Requirements

Never commit:

- API keys
- tokens
- secrets
- personal credentials
- private production data

Use:

```text
.env
.env.local
```

and commit:

```text
.env.example
```

Make sure sensitive files are in `.gitignore`.

Validate uploaded files.

Do not trust raw document contents.

Limit file size and supported file types.

Do not expose provider API keys to the browser.

LLM calls involving private candidate data should happen server-side.

---

# 32. Git Workflow

Git history is an explicit project requirement.

The project should have a clean, professional commit history.

### Important identity rule

Commits must use the Git identity already configured for the repository/user.

Before making commits:

```bash
git config user.name
git config user.email
```

Use the candidate's existing configured Git profile/identity.

Do NOT create or use a Claude-specific identity.

Do NOT add:

```text
Co-authored-by: Claude
Co-authored-by: Anthropic
Co-authored-by: OpenAI
```

or any similar AI attribution trailer.

Do not alter the user's Git identity unless explicitly requested.

Do not spoof another person's identity.

### Commit cadence

Commit after meaningful milestones, not every line change.

Examples:

```text
chore: initialize project structure
feat: add candidate profile ingestion
feat: implement JD analysis pipeline
feat: add hybrid candidate retrieval
feat: implement gap analysis
feat: add modification approval workflow
feat: implement tailored resume generation
feat: add claim validation
test: add RAG evaluation suite
docs: document architecture and RAG pipeline
fix: resolve retrieval metadata issue
```

Aim for logical, focused commits.

Avoid giant commits containing unrelated work.

Avoid committing broken intermediate states unless necessary.

Run appropriate tests before committing when practical.

---

# 33. Git Rules

Before coding:

```bash
git status
git branch --show-current
git log --oneline -10
git config user.name
git config user.email
```

Before commits:

```bash
git diff
git diff --staged
```

Do not:

- force push
- rewrite history unnecessarily
- amend commits unless explicitly requested
- delete user work
- overwrite unrelated changes
- commit secrets
- commit generated junk
- commit huge temporary files

If pre-existing user changes exist, preserve them.

Never reset or discard them just to make the working tree clean.

---

# 34. Development Behavior

Claude Code should behave as a senior engineer working collaboratively.

Before large architectural changes:

1. Inspect the current repository.
2. Understand existing code.
3. Prefer existing patterns when reasonable.
4. Avoid unnecessary rewrites.
5. Make small, testable changes.
6. Run tests/lint/type checking where applicable.
7. Update documentation as the architecture changes.
8. Commit meaningful milestones.

Do not blindly implement the example architecture if the repository already has a better structure.

---

# 35. Code Quality

Prefer:

- clear naming
- small functions
- strong typing
- Pydantic validation
- clear interfaces
- dependency inversion where useful
- explicit error handling
- structured logging
- testable components
- environment-based configuration

Avoid:

- giant functions
- giant files
- duplicated prompt logic
- hardcoded API keys
- hardcoded model names throughout the codebase
- business logic inside UI components
- unnecessary abstractions

---

# 36. Error Handling

The system must handle:

- invalid resume files
- empty JD
- malformed LLM responses
- provider failures
- rate limits
- retrieval failures
- unavailable embeddings
- vector DB errors
- malformed structured outputs
- generation failures
- unsupported document types

Use graceful failure and useful user-facing errors.

---

# 37. LLM Structured Output

Whenever an LLM output is consumed programmatically, prefer:

```text
LLM
 ->
Structured Schema
 ->
Validation
 ->
Application Logic
```

rather than:

```text
LLM
 ->
arbitrary text parsing
```

Use Pydantic or equivalent validation.

If structured generation fails:

1. attempt safe retry if appropriate
2. log useful diagnostics without secrets
3. return a meaningful failure
4. avoid corrupting candidate data

---

# 38. Observability

Important AI operations should be traceable.

For each major operation, record useful metadata such as:

```text
operation
provider
model
latency
success/failure
retrieval count
generation type
```

Do not log sensitive resume content or API keys unnecessarily.

---

# 39. UX Principles

The UI should make AI decisions understandable.

Useful sections:

### Match Overview

```text
Match Score
Strong Matches
Partial Matches
Gaps
```

### Evidence

```text
JD Requirement
Candidate Evidence
Relevance
```

### Suggested Modifications

```text
Current
Suggested
Reason
Status
```

### Resume Preview

Show the generated result.

### Comparison

Allow:

```text
Original
vs
Tailored
```

### Explanation

Allow:

> Why was this project selected?

---

# 40. Initial Dashboard Concept

The final UI can conceptually contain:

```text
--------------------------------------------------
Adaptive Resume Engineer
--------------------------------------------------

Target Role:
Data Engineer

JD:
[ uploaded ]

Candidate:
Master Profile

---------------------------------------
MATCH ANALYSIS
82%

Strong Matches
Python
SQL
APIs

Partial Matches
PostgreSQL
ETL

Gaps
Airflow
Spark
---------------------------------------

RECOMMENDED PROJECTS

1. Project A       96%
2. Project B       88%
3. Project C       73%

---------------------------------------

SUGGESTED MODIFICATIONS

Project A
[Accept] [Edit] [Reject]

Skill: PostgreSQL
[Add] [Edit] [Reject]

---------------------------------------

[ Generate Tailored Resume ]
```

---

# 41. Do Not Overbuild V1

V1 should NOT include:

- automatic job searching
- automatic job applications
- browser automation for application forms
- large autonomous agents
- complicated multi-agent systems
- unnecessary microservices
- unnecessary cloud infrastructure

The priority is a strong core:

```text
RAG
+
JD understanding
+
Evidence matching
+
Gap analysis
+
Human approval
+
Resume transformation
+
Validation
```

---

# 42. Future Roadmap

## V1

Adaptive Resume Intelligence

```text
Resume
+
JD
>
RAG
>
Gap Analysis
>
Human Approval
>
Tailored Resume
>
Validation
```

## V2

Job Discovery

```text
Candidate Profile
>
Find Relevant Jobs
>
Analyze JDs
>
Rank Jobs
```

## V3

Application Assistance

```text
Job
>
Tailored Resume
>
Cover Letter
>
Application Form Assistance
>
Human Review
>
Submission
```

The future features must not contaminate V1 architecture unnecessarily.

Design interfaces so they can be added later.

---

# 43. Definition of Done for V1

V1 is considered complete only when:

- candidate profile can be ingested
- resume content can be structured
- candidate knowledge base exists
- embeddings/retrieval work
- JD can be analyzed
- JD requirements are structured
- candidate evidence can be matched
- gap analysis works
- modification plan can be generated
- user can approve/reject/edit suggestions
- tailored resume can be generated
- generated resume can be validated
- match/ATS-style analysis exists
- original and tailored resume can be compared
- important flows are tested
- environment configuration is documented
- README is complete
- architecture documentation is complete
- RAG documentation is complete
- setup documentation is complete
- roadmap is documented
- meaningful Git history exists

---

# 44. First Engineering Principle

Do not optimize for the number of features.

Optimize for:

> **A believable end-to-end RAG workflow that actually works on real resumes and real job descriptions.**

A small but robust implementation is better than a large collection of shallow AI features.

---

# 45. Final Instruction to Claude Code

Treat this file as the project's source of truth for:

- scope
- architecture
- engineering behavior
- Git practices
- documentation expectations
- V1 boundaries

However, this document is not permission to ignore actual repository state.

Always inspect the repository before modifying it.

If an implementation decision conflicts with this document, prefer the least disruptive option and update the documentation when the architecture genuinely changes.