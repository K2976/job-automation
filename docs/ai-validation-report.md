# AI Validation Report — Adaptive Résumé Engineer

**Date:** 2026-08-22 · **Phase:** V1 live AI validation (Part 3)

## Evidence legend
Every result below is tagged so claims aren't overstated:

- **Verified** — passed a deterministic automated assertion (`pytest`).
- **Observed** — measured on a live/mock run; illustrative, small sample.
- **Subjective** — human judgement of prose quality (live output, one reviewer).
- **Not Tested** — needs live calls not made, or an artifact not available.

---

## 1. Executive summary

**What works (high confidence):**
- The **deterministic core is robust to live LLM input.** Across both live providers and
  all 4 role JDs, evidence matching (`strong`/`missing`), provenance transitions
  (accept/reject/edit), and anti-hallucination all behaved correctly. *Verified.*
- **Live JD extraction is strong and clearly beats the offline lexicon** where it matters:
  cybersecurity requirement recall was **0.17 (mock) → 0.83 (Groq) → ~1.0 (Gemini)**.
- **Project reframing works** — the motivating use case. Live Groq rewrote an iOS project
  into a data/backend narrative, truthfully, with zero unsupported claims (§7 below).
- **The claim validator catches live hallucination.** On the *reframed* live-Groq résumés,
  generation introduced 2 unsupported claims (Backend, Cybersecurity); the deterministic
  validator flagged all of them. *Verified.*
- **Provider failures are handled cleanly** (retry/timeout/no key leak/no data corruption).
  A real Gemini free-tier 429 mid-run was handled gracefully. *Verified.*

**What doesn't / limitations:**
- **JD-alignment (ATS) score does not reward tailoring** — the tailored résumé scores ≈ the
  "everything" baseline (Δ ≈ −0.05..+0.11). The metric measures coverage, not focus. Not a
  regression; a metric limitation (§9).
- **Hybrid retrieval's semantic benefit is unproven offline** — the default embedder is
  TF-IDF (lexical), so semantic ≈ keyword. Needs Gemini embeddings to measure. *Not Tested.*
- **Gemini free-tier is slow and rate-limited** — ~30–54s/JD and repeated 429s (completed
  only 1/4 and 3/4 across two runs), vs Groq's ~7s and 4/4 every time. Correct when it runs.
  *Observed.*
- **Manual-benchmark comparison (§15) not done** — the candidate's hand-tailored DE résumé
  was not provided. *Not Tested.*

**Verdict on the motivating question** ("does it automate the manual tailoring?"):
**Yes, for the project-reframing + gap + validation loop**, on this candidate and these JDs,
with live models — see §7. Broader qualitative confidence needs the manual benchmark and a
multi-candidate set.

---

## 2. Test environment
- **Providers/models:** mock (offline) · Groq `openai/gpt-oss-120b` · Gemini
  `gemini-3.6-flash`. Keys in `.env`, never logged.
- **Embeddings:** local TF-IDF (deterministic) for all runs.
- **Candidate:** bundled master profile (`data/fixtures/master_profile.json`) — iOS dev
  with Python/SQL/PostgreSQL/FastAPI/Supabase/REST/1D-CNN/edge-AI evidence.
- **Dataset:** 4 role JDs (`tests/evaluation/fixtures/`) + human labels
  (`tests/evaluation/labels.py`). Reproduce: `python tests/evaluation/run_eval.py
  --provider <p>` → `docs/eval-runs/<p>.json`.
- Each JD runs in an isolated throwaway DB; the master profile is never mutated (§29).

---

## 3. JD analysis results
Concept-recall of expected requirements (substring coverage over the extracted skill
fields, fair to rich live phrasing):

| JD | mock | Groq | Gemini |
|---|---|---|---|
| Data Engineer | 1.00 | 1.00 | 1.00 |
| AI/ML Engineer | 1.00 | 1.00 | 1.00 |
| Backend Engineer | 1.00 | 1.00 | 1.00 |
| Cybersecurity | **0.17** | **0.83** | rate-limited (429) |
| **avg** | 0.79 | 0.96 | 1.00 (3 JDs) |

*Observed.* **False positives: 0** across all runs (no mobile/UI terms leaked into
non-mobile JDs) — *Verified*. **Finding:** the deterministic mock lexicon can't extract
security terms (burp suite, penetration testing, …); live LLMs can. This is the clearest
demonstration of why live extraction matters, and a documented mock limitation — **not**
fixed by expanding the lexicon (that would game the eval and mutate deterministic behaviour
Parts 1–2 depend on).

Normalization (§8): `Postgres`/`PostgreSQL`/`PostgreSQL database` collapse to one;
`SQL`/`PostgreSQL`/`MySQL` stay distinct. *Verified* (`test_skill_normalization_rules`).

---

## 4. Retrieval results
**Hit@3 = 100%** for every labelled technology (PostgreSQL, REST, FastAPI, 1D-CNN, Python,
feature engineering, edge AI) — *Verified*. Hybrid vs semantic vs keyword analysis and the
TF-IDF caveat are in **[docs/rag-evaluation.md](rag-evaluation.md)**. Notable case: for
`feature engineering`, pure TF-IDF semantic wrongly ranks "B.Tech Computer Engineering"
first; the keyword component correctly promotes "Setu AI". *Observed.*

---

## 5. Evidence matching & gap analysis results
For all 4 JDs × 3 providers, labelled STRONG skills classified STRONG and labelled MISSING
skills classified MISSING — *Verified*. The deterministic classifier is **authoritative and
stable regardless of provider** (the LLM's messier strings did not corrupt classification).
Gap categories (partial / missing / confirmation-required) matched expectations; the
cybersecurity JD correctly produced a wall of MISSING (candidate has no security evidence).

---

## 6. Human-in-the-loop results (§13)
Across every run: **Accept → USER_CONFIRMED**, **Reject → REJECTED** (skill absent from the
résumé), **Edit → USER_EDITED** (edited value reaches generation). *Verified*
(`test_evaluation`, `test_provenance`). An unapproved suggestion never becomes résumé
content.

---

## 7. Modification planning & project reframing (§14) — the key qualitative test
**Live Groq, Data Engineer JD, Parkezy project** (accepted rewrite):

> **Original:** "Built an iOS parking app in SwiftUI with a FastAPI backend…"
>
> **AI rewrite:** "Designed and implemented the PostgreSQL schema and SQL data-access layer
> for a real-time parking application, using Python (FastAPI) to build RESTful APIs that
> queried and updated slot availability and supported live synchronization of availability
> data across iOS clients."

It **found the right project**, **foregrounded backend/database/API/real-time** aspects,
**de-emphasized the iOS/UI framing**, stayed **truthful** (still an "iOS client", no
invented tech), and **did not keyword-stuff**. This reproduces the manual workflow that
motivated the project. *Subjective (one reviewer, one JD), strongly positive.*

---

## 8. Résumé generation & claim validation results (§16, §17)
The systematic runner **accepts the top project rewrite**, so validation/ATS below score the
**reframed** résumé — the product's real output after a user accepts a suggestion, and the
highest-risk content for the validator.

Hand-inspected **live Groq DE résumé** (§7 run): Summary reframed to "building real-time data
solutions… Python and SQL for designing, implementing and optimizing data pipelines"; Skills
reduced to `Python, SQL, PostgreSQL` (iOS-only skills dropped); **6 supported, 0
unsupported.** *Observed / Subjective — role-relevant, specific, coherent.*

**Hallucination detection on the reframed live output.** Across the 4 reframed Groq
résumés, live generation introduced **2 unsupported claims** (on the Backend and
Cybersecurity résumés), and the deterministic validator **flagged all of them**
(`unsupported` = 1 each; DE and AI/ML = 0). This is the important result: when the LLM
reframes a project it sometimes over-reaches, and the anti-hallucination layer catches it on
*live* output — not just on constructed cases. Constructed cases (invented metric "250%",
unsupported Kubernetes) are also flagged — *Verified* (`test_validation_ats`).

Limitation: **Experience entries are not reframed** (only projects get REWRITE suggestions) —
see §13.

---

## 9. ATS / JD-alignment results (§18)
Tailored (reframed) vs a same-scorer "everything" baseline: **Δ ≈ −0.08 … +0.06**, mostly
slightly negative. *Observed.* **Finding:** the alignment score is coverage-based, so a
focused résumé (which *drops* irrelevant content) cannot out-score a kitchen-sink résumé on
it. The negative delta is **partly a baseline artifact**: `project_relevance = min(1,
n_bullets/3)` and the baseline keeps *all* projects while the tailored résumé *drops* some,
so tailored almost mechanically scores lower on that component. This is **not** evidence that
tailoring is worse — the tailoring value shows in the **comparison** (skills dropped),
**validation**, and the qualitative reframe (§7), not in a higher ATS number. Per §18/§24 the
formula was **not** tuned to force the number up.

---

## 10. Explainability & comparison results (§19, §20)
Explainability traces requirement → retrieved evidence → relevance → reason and never
invents evidence (the reasoning is deterministic, not LLM prose) — *Verified*
(`test_api`, `explain_requirement`). Comparison correctly reports skills added / dropped and
project reordering — *Verified* (`test_pipeline_e2e`).

---

## 11. Gemini vs Groq (§21)

| Metric | Groq `gpt-oss-120b` | Gemini `gemini-3.6-flash` |
|---|---|---|
| JDs completed (reframed run) | **4 / 4** | **1 / 4** — 3 hit free-tier 429 |
| Avg JD recall (completed) | 0.96 | 1.00 |
| Evidence matching (strong/missing) | all correct | all correct |
| Human-in-the-loop | all correct | all correct |
| Unsupported claims (caught by validator) | 2 (Backend, Cyber) | 1 (DE) |
| Structured-output reliability | 4/4 valid | valid on every call that wasn't rate-limited |
| **Avg latency / JD** | **~7 s** | **~30–54 s** |

*Observed.* Both drive the pipeline correctly with valid structured output, and both
produced correct deterministic-facing results with high JD recall. **Gemini is
correct-when-it-runs but its free tier could not sustain the suite** — an earlier run
completed 3/4, the reframed run only 1/4 before repeated 429s (the runner handled every 429
gracefully, no corruption). **Groq completed 4/4 on every run at ~7× lower latency and no
rate limits.** The separator is operational, not quality.

---

## 12. Provider failure results (§22) — all *Verified*
Invalid key → `LLMError`, **API key never in the message**; timeout → bounded retry →
`LLMError`; 429 (Retry-After) → retried → success; 5xx → bounded retry; malformed 200 →
`LLMError`; Gemini empty-candidates/safety → `LLMError`. **Data integrity:** a failure
mid-generation persists **no** résumé and leaves the KB unchanged (`test_provider_failures`).
Corroborated live: the Gemini 429 aborted one JD without corrupting the run.

---

## 13. Known limitations
1. ATS score rewards coverage, not focus (§9).
2. Hybrid retrieval's semantic benefit unproven on the local TF-IDF embedder (§4). *Not Tested.*
3. Mock lexicon lacks security/niche terms → low mock recall for out-of-lexicon roles (§3).
4. Experience entries aren't reframed, only projects (§8).
5. Gemini free-tier: slow + rate-limited (§11).
6. Single candidate, one reviewer for subjective calls; manual benchmark (§15) not run.

## 14. Recommended improvements (smallest layer first, per §24)
1. **Default provider → Groq** for latency + reliability; keep Gemini as fallback (§15 below).
2. Add a `sentence-transformers` embedding option so hybrid retrieval's semantic value can be
   measured offline; or run the eval with `EMBEDDING_PROVIDER=gemini`.
3. Consider a relevance/focus component in the ATS score (carefully; don't just inflate it).
4. Extend REWRITE suggestions to experience entries, not only projects.
5. **Run the §15 manual benchmark** — the candidate has a hand-tailored Data Engineer
   résumé. Drop the file in and it can be compared (skills emphasized, projects selected,
   keyword coverage, unsupported claims) against the AI output. Currently **Not Tested**.
   Broaden to more candidates thereafter.

## 15. Model selection (§28)
Evidence supports **Groq `openai/gpt-oss-120b` as the default** for all LLM tasks: equal
correctness on the deterministic-facing outputs, near-equal JD recall, valid structured
output, **~7× lower latency**, and no rate-limiting. **Gemini `gemini-3.6-flash`** is a
capable fallback (perfect recall on completed JDs) but slow and free-tier-limited today. No
evidence yet justifies per-task provider splitting — revisit if generation prose quality is
formally compared. `.env` already defaults to `groq`.

## 16. Regression status
Backend `pytest`: **53 passed** (offline, mock). Frontend `npm run build` + `npm test`:
pass. The evaluation additions did not weaken any existing behaviour; two real bugs were
found and fixed (job-scoped suggestion ids; stale Gemini model default).
