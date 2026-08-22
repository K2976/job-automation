"""Application question engine (§12, §16-§18). Classifies each form field into an
ApplicationQuestion with an answer + provenance, spending an LLM call ONLY on genuine
semantic free-text questions. High-impact questions (salary, visa, relocation, demographics)
are never auto-answered — they pause the task in every mode, autonomous included (§11).
Semantic answers are validated against candidate evidence before use (anti-hallucination)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

from ..models import (
    AnswerSource,
    ApplicationQuestion,
    FieldType,
)
from ..providers.llm import LLMError, LLMProvider
from ..text_utils import extract_skills, normalize_skill
from . import field_mapper as fm
from .page import FieldDescriptor

# Questions whose answer we cannot safely derive from a résumé/profile — always pause (§11).
_HIGH_IMPACT = [
    (r"salary|compensation|expected pay|desired pay|\bctc\b|pay expectation", "compensation"),
    (r"visa|sponsor|work authoriz|authoriz(ed|ation) to work|right to work|work permit",
     "work authorization / visa"),
    (r"reloca", "relocation"),
    (r"notice period|start date|when can you start|availab", "availability / start date"),
    (r"clearance", "security clearance"),
    (r"citizen", "citizenship"),
    (r"gender|race|ethnic|disabilit|veteran|sexual orientation", "demographic / EEO"),
]
_SEMANTIC_CUES = ("why", "describe", "tell us", "what makes", "how would", "cover",
                  "motivat", "interest", "passion", "experience with", "project")


@dataclass
class FillContext:
    candidate_values: dict[str, str]
    evidence: str                    # top candidate evidence, built once per task (§16)
    jd_text: str
    supported_skills: set[str]
    resume_artifact: str = ""
    cover_letter: str = ""
    llm: LLMProvider | None = None
    role: str = ""


def _high_impact(text: str) -> str | None:
    low = text.lower()
    for pat, label in _HIGH_IMPACT:
        if re.search(pat, low):
            return label
    return None


def _is_semantic(fd: FieldDescriptor) -> bool:
    low = fd.label.lower()
    return fd.field_type == FieldType.textarea or "?" in fd.label or \
        any(c in low for c in _SEMANTIC_CUES)


def _answer_supported(answer: str, supported: set[str]) -> bool:
    """Anti-hallucination (§18): every skill/technology named in the answer must be backed
    by candidate evidence. Reuses V1's skill lexicon — no separate claim model."""
    return all(normalize_skill(s) in supported for s in extract_skills(answer))


def _q(fd: FieldDescriptor, **kw) -> ApplicationQuestion:
    return ApplicationQuestion(
        field_key=fd.key, question_text=fd.label or fd.name, name=fd.name,
        field_type=fd.field_type, required=fd.required, options=fd.options, **kw)


def classify(fd: FieldDescriptor, ctx: FillContext) -> ApplicationQuestion:
    """Turn one field into an answered (or flagged) ApplicationQuestion."""
    # 1. Résumé file upload → the tailored package artifact (§14).
    canon = fm.map_field(fd.label, fd.name)
    if fd.field_type == FieldType.file:
        if canon == fm.RESUME or "resume" in fd.label.lower() or "cv" in fd.label.lower():
            if ctx.resume_artifact:
                return _q(fd, answer=ctx.resume_artifact,
                          answer_source=AnswerSource.APPLICATION_PACKAGE, confidence=1.0,
                          reason="Tailored résumé from the application package.")
            return _q(fd, requires_review=bool(fd.required), reason="No résumé artifact.")
        return _q(fd, requires_review=bool(fd.required),
                  reason="Unrecognized file upload." if fd.required else "Optional file skipped.")

    # 2. High-impact question → never auto-answer, pause in all modes (§11).
    hi = _high_impact(f"{fd.label} {fd.name}")
    if hi:
        return _q(fd, answer_source=AnswerSource.UNRESOLVED, requires_review=True,
                  reason=f"High-impact question ({hi}) — needs your explicit answer.")

    # 3. Cover letter free-text → the V2-generated letter (§15).
    if canon == fm.COVER_LETTER or "cover letter" in fd.label.lower():
        if ctx.cover_letter:
            return _q(fd, answer=ctx.cover_letter,
                      answer_source=AnswerSource.APPLICATION_PACKAGE, confidence=0.9)
        return _q(fd, requires_review=bool(fd.required),
                  reason="Cover letter required but not prepared." if fd.required else "")

    # 4. Deterministic identity/contact field from the profile (§13).
    if canon in ctx.candidate_values:
        value = ctx.candidate_values[canon]
        if value:
            return _q(fd, answer=value, answer_source=AnswerSource.CANDIDATE_PROFILE,
                      confidence=1.0)
        return _q(fd, requires_review=bool(fd.required),
                  reason=f"No '{canon}' in profile." if fd.required else "")

    # 5. Semantic free-text question → LLM, then validate the answer (§16-§18).
    if _is_semantic(fd) and ctx.llm is not None:
        try:
            ans = ctx.llm.answer_question(fd.label or fd.name, ctx.jd_text, ctx.evidence)
        except LLMError:
            return _q(fd, requires_review=True, reason="Answer generation failed.")
        # Evidence handed to the model is itself candidate-supported, so its skills count.
        allowed = ctx.supported_skills | {
            normalize_skill(s) for s in extract_skills(ctx.evidence)}
        supported = _answer_supported(ans.answer, allowed)
        needs = ans.requires_review or not ans.answer.strip() or not supported
        return _q(fd, answer="" if needs else ans.answer,
                  answer_source=AnswerSource.UNRESOLVED if needs else AnswerSource.LLM_GENERATED,
                  confidence=ans.confidence,
                  requires_review=needs,
                  reason="Generated answer not supported by evidence." if not supported
                  else ("" if not needs else "Model flagged the answer for review."))

    # 6. Dropdowns/radios/unknown required fields — don't guess (§11, §42).
    if fd.field_type in (FieldType.select, FieldType.radio, FieldType.checkbox):
        if not fd.required:
            return _q(fd, reason="Optional choice left blank.")
        return _q(fd, requires_review=True, answer_source=AnswerSource.UNRESOLVED,
                  reason="Selection can't be safely inferred — needs your input.")

    # 7. Unmapped text field.
    return _q(fd, requires_review=bool(fd.required), answer_source=AnswerSource.UNRESOLVED,
              reason="Unrecognized required field." if fd.required
              else "Optional field skipped.")


def unresolved(questions: list[ApplicationQuestion]) -> list[ApplicationQuestion]:
    """Required questions that still need a human (drive REVIEW/USER_ACTION states)."""
    return [q for q in questions if q.required and (q.requires_review or not q.answer)]
