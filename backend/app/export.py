"""Résumé export. Renders the structured TailoredResume model to PDF via reportlab
platypus (pure-python, no system deps) and HTML. The structured model is the single
source of truth — renderers never receive pre-baked resume text."""
from __future__ import annotations

import io

from .generation import render_html  # noqa: F401 (re-exported for callers)
from .models import TailoredResume


def build_pdf(resume: TailoredResume) -> bytes:
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title=f"{resume.candidate.name} résumé",
                            leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    base = getSampleStyleSheet()
    name_s = ParagraphStyle("Name", parent=base["Title"], fontSize=20, spaceAfter=2,
                            alignment=TA_LEFT)
    role_s = ParagraphStyle("Role", parent=base["Normal"], fontSize=10, textColor="#555555")
    contact_s = ParagraphStyle("Contact", parent=base["Normal"], fontSize=9,
                               textColor="#555555", spaceAfter=6)
    head_s = ParagraphStyle("Head", parent=base["Heading2"], fontSize=11,
                            textColor="#2a5db0", spaceBefore=10, spaceAfter=2)
    body_s = ParagraphStyle("Body", parent=base["Normal"], fontSize=9.5, leading=13)

    c = resume.candidate
    contact = " · ".join(x for x in (c.email, c.phone, c.location, *c.links) if x)
    story = [Paragraph(_esc(c.name), name_s)]
    if resume.target_role:
        story.append(Paragraph(_esc(resume.target_role), role_s))
    if contact:
        story.append(Paragraph(_esc(contact), contact_s))

    def section(title: str):
        story.append(Paragraph(title, head_s))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#d7dae0",
                                spaceBefore=1, spaceAfter=4))

    if resume.summary:
        section("Summary")
        story.append(Paragraph(_esc(resume.summary), body_s))
    if resume.skills:
        section("Skills")
        story.append(Paragraph(_esc(" · ".join(resume.skills)), body_s))
    for sec in resume.sections:
        if not sec.bullets:
            continue
        section(sec.title)
        story.append(ListFlowable(
            [ListItem(Paragraph(_esc(b.text), body_s), leftIndent=10)
             for b in sec.bullets],
            bulletType="bullet", start="•", leftIndent=12))
        story.append(Spacer(1, 2))

    doc.build(story)
    return buf.getvalue()


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
