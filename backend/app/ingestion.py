"""Resume ingestion (CLAUDE.md §4). Extract text from PDF/DOCX/plain text, then parse
into a structured MasterProfile via the LLM. Uploaded content is untrusted: size and
type are validated, and the candidate is expected to review the result before it becomes
their master profile."""
from __future__ import annotations

import io

from .config import settings
from .models import MasterProfile
from .providers.llm import LLMProvider

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


class IngestionError(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > settings.max_upload_bytes:
        raise IngestionError(
            f"File too large ({len(data)} bytes > {settings.max_upload_bytes}).")
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestionError(f"Unsupported file type {ext!r}. "
                             f"Allowed: {sorted(ALLOWED_EXTENSIONS)}")
    if ext == ".pdf":
        return _pdf_text(data)
    if ext == ".docx":
        return _docx_text(data)
    return data.decode("utf-8", errors="replace")


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages).strip()


def _docx_text(data: bytes) -> str:
    import docx
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs).strip()


def ingest_resume_text(text: str, llm: LLMProvider) -> MasterProfile:
    if not text.strip():
        raise IngestionError("Resume text is empty.")
    return llm.parse_resume(text)
