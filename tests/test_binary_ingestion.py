"""Round-trip the binary extraction paths so the pypdf/python-docx calls are actually
exercised, not just claimed. reportlab is a dev-only helper for generating a PDF."""
import io

import pytest

from app.ingestion import extract_text


def test_docx_round_trip():
    docx = pytest.importorskip("docx")
    doc = docx.Document()
    doc.add_paragraph("Jane Doe")
    doc.add_paragraph("Skills: Python, PostgreSQL")
    buf = io.BytesIO()
    doc.save(buf)
    text = extract_text("resume.docx", buf.getvalue())
    assert "Jane Doe" in text and "PostgreSQL" in text


def test_pdf_round_trip():
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Jane Doe Python PostgreSQL")
    c.save()
    text = extract_text("resume.pdf", buf.getvalue())
    assert "Jane Doe" in text
