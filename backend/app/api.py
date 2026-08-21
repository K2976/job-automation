"""FastAPI layer. Thin — all logic lives in the pipeline/stage modules; endpoints just
validate input, call the pipeline, and return Pydantic models. Serves a single-page UI
that drives the whole flow (backend-first; a full Next.js frontend is future work)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import analysis, db, ingestion, kb, pipeline
from .config import settings
from .models import ApprovalAction, MasterProfile
from .providers.llm import LLMError, get_llm_provider

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Adaptive Resume Engineer", version="0.1.0", lifespan=lifespan)


# ------------------------------------------------------------------ requests #
class JobIn(BaseModel):
    candidate_id: int
    jd_text: str


class ApprovalIn(BaseModel):
    action: ApprovalAction
    edited_text: str = ""


# --------------------------------------------------------------------- meta #
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "llm_provider": settings.llm_provider,
            "embedding_provider": settings.embedding_provider}


@app.get("/api/fixtures/jds")
def sample_jds() -> dict:
    out = {}
    for f in sorted(pipeline.FIXTURES.glob("jd_*.txt")):
        text = f.read_text()
        label = next((ln.strip() for ln in text.splitlines() if ln.strip()), f.stem)
        out[label] = text
    return out


# ---------------------------------------------------------------- candidate #
@app.post("/api/candidates/seed-fixture")
def seed_fixture() -> dict:
    """Dev convenience: load the bundled sample master profile."""
    candidate_id = pipeline.seed_from_fixture()
    return {"candidate_id": candidate_id,
            "candidate": db.get_candidate(candidate_id)}


@app.post("/api/ingest")
async def ingest(file: UploadFile | None = File(default=None),
                 text: str = Form(default="")) -> MasterProfile:
    """Parse a resume (uploaded file or pasted text) into a reviewable profile.
    Does NOT persist — the candidate reviews it before it becomes the master profile."""
    llm = get_llm_provider()
    try:
        if file is not None:
            data = await file.read()
            text = ingestion.extract_text(file.filename or "resume.txt", data)
        elif not text.strip():
            raise HTTPException(400, "Provide a file or a non-empty 'text' form field.")
        return ingestion.ingest_resume_text(text, llm)
    except ingestion.IngestionError as e:
        raise HTTPException(400, str(e))
    except LLMError as e:
        raise HTTPException(502, str(e))


@app.post("/api/candidates")
def create_candidate(profile: MasterProfile) -> dict:
    """Persist a reviewed master profile as the candidate knowledge base."""
    candidate_id = kb.seed_profile(profile)
    return {"candidate_id": candidate_id}


@app.get("/api/candidates/{candidate_id}")
def get_candidate(candidate_id: int) -> dict:
    candidate = db.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(404, "candidate not found")
    entities = db.get_entities(candidate_id)
    return {"candidate": candidate, "entities": entities}


# --------------------------------------------------------------------- jobs #
@app.post("/api/jobs")
def create_job(job: JobIn) -> dict:
    if db.get_candidate(job.candidate_id) is None:
        raise HTTPException(404, "candidate not found")
    if not job.jd_text.strip():
        raise HTTPException(400, "jd_text is empty")
    try:
        return pipeline.analyze_job(job.candidate_id, job.jd_text)
    except LLMError as e:
        raise HTTPException(502, str(e))


@app.get("/api/jobs/{job_id}/plan")
def get_plan(job_id: int) -> dict:
    if db.get_job(job_id) is None:
        raise HTTPException(404, "job not found")
    return {"suggestions": db.get_suggestions(job_id)}


@app.post("/api/suggestions/{suggestion_id}/approve")
def approve(suggestion_id: str, body: ApprovalIn) -> dict:
    row = db.get_suggestion(suggestion_id)
    if row is None:
        raise HTTPException(404, "suggestion not found")
    status = pipeline.planning.apply_approval(
        row["candidate_id"], suggestion_id, body.action, body.edited_text)
    return {"suggestion_id": suggestion_id, "status": status}


@app.post("/api/jobs/{job_id}/generate")
def generate(job_id: int) -> dict:
    if db.get_job(job_id) is None:
        raise HTTPException(404, "job not found")
    try:
        return pipeline.generate_for_job(job_id)
    except LLMError as e:
        raise HTTPException(502, str(e))


@app.get("/api/jobs/{job_id}/explain")
def explain(job_id: int, requirement: str) -> dict:
    row = db.get_job(job_id)
    if row is None:
        raise HTTPException(404, "job not found")
    from .models import JDRequirements, SUPPORTED_STATUSES
    from .retrieval import RetrievalIndex
    from . import matching
    requirements = JDRequirements.model_validate_json(row["requirements_json"])
    entities = db.get_entities(row["candidate_id"], statuses=SUPPORTED_STATUSES)
    index = RetrievalIndex(entities)
    matches = matching.match_requirements(
        index, requirements, matching.candidate_skill_set(entities))
    return analysis.explain_requirement(requirement, matches)


# ----------------------------------------------------------------------- UI #
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
