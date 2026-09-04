"""FastAPI application exposing the full JobSpy pipeline.

Endpoints
---------
GET  /health                      liveness + AI readiness
POST /scrape                      (background) scrape (config.py, body overrides) -> JSON
POST /scrape/stream               (streaming NDJSON) scrape, one event per search term
GET  /scrape/{run_id}             poll a scrape run
GET  /config/scrape               default scrape parameters (for UI prefill)
GET  /jobs                        latest scraped jobs
GET  /jobs/grouped                latest scraped jobs grouped by company + role
POST /filter/experience           Agent 1: keep jobs whose required years overlap
POST /filter/experience/stream    Agent 1 (streaming NDJSON): tag each posting selected/not
POST /screen/stream               Agents 1+2 (streaming NDJSON): one call per job estimates
                                  required experience AND scores resume fit
POST /suitability                 Agent 2: score a resume against one job
POST /tailor-resume               Agent 3: rewrite a resume -> .docx download
POST /run                         (background) full chain: scrape/load -> filter
                                  -> suitability -> tailor
GET  /run/{run_id}                poll a full run
GET  /run/{run_id}/resume/{job_id} download a tailored resume
"""

import json
from io import BytesIO
from typing import Optional

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from Agent.resume_io import extract_text

from . import schemas, service, tasks

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

app = FastAPI(
    title="JobSpy API",
    version="1.0.0",
    description="Scrape jobs, check experience fit, assess resume suitability, "
    "and generate tailored resumes.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
async def _read_resume_text(resume: UploadFile) -> str:
    data = await resume.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty resume file.")
    try:
        text = extract_text(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=f"Could not read resume. Only valid .docx files are supported ({exc}).",
        )
    if not text.strip():
        raise HTTPException(status_code=400, detail="Resume contained no readable text.")
    return text


def _resolve_job(job_id: Optional[str], job: Optional[str]) -> dict:
    if job:
        try:
            parsed = json.loads(job)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="`job` must be valid JSON.")
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="`job` must be a JSON object.")
        return parsed
    if job_id:
        found = service.find_job_by_id(job_id)
        if found is None:
            raise HTTPException(
                status_code=404,
                detail=f"job_id '{job_id}' not found in latest scraped jobs.",
            )
        return found
    raise HTTPException(
        status_code=400, detail="Provide either `job_id` or a `job` JSON object."
    )


def _call_agent(func, *args):
    """Run an agent call, mapping failures to helpful HTTP errors."""
    try:
        return func(*args)
    except RuntimeError as exc:  # AI client not configured
        raise HTTPException(status_code=503, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - upstream/API failure
        raise HTTPException(status_code=502, detail=f"AI request failed: {exc}")


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get("/health", response_model=schemas.HealthResponse)
def health() -> schemas.HealthResponse:
    return schemas.HealthResponse(status="ok", **service.agent_status())


@app.post("/scrape", response_model=schemas.RunAccepted, status_code=202)
def start_scrape(
    background_tasks: BackgroundTasks,
    request: Optional[schemas.ScrapeRequest] = None,
) -> schemas.RunAccepted:
    """Kick off a scrape (background). Any body fields override config.py."""
    overrides = request.model_dump(exclude_none=True) if request else {}
    run_id = tasks.create_run()
    background_tasks.add_task(service.run_scrape_task, run_id, overrides)
    return schemas.RunAccepted(run_id=run_id)


@app.post("/scrape/stream")
def scrape_stream(
    request: Optional[schemas.ScrapeRequest] = None,
) -> StreamingResponse:
    """Scrape and stream results as NDJSON, one event per search term.

    Emits ``start`` -> ``term`` (with per-term group deltas and a ``percent``
    that advances each term) -> ``done``. Body fields override config.py, same
    as ``POST /scrape``. The final flat list is persisted to disk so a later
    ``GET /jobs`` / filter still works.
    """
    overrides = request.model_dump(exclude_none=True) if request else {}
    return StreamingResponse(
        service.stream_scrape(overrides), media_type="application/x-ndjson"
    )


@app.get("/scrape/{run_id}", response_model=schemas.RunStatus)
def scrape_status(run_id: str) -> schemas.RunStatus:
    run = tasks.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id '{run_id}'.")
    return schemas.RunStatus(**run)


@app.get("/config/scrape", response_model=schemas.ScrapeConfigResponse)
def scrape_config() -> schemas.ScrapeConfigResponse:
    """Default scrape parameters (from config.py) for prefilling the UI."""
    return schemas.ScrapeConfigResponse(**service.scrape_defaults())


@app.get("/jobs", response_model=schemas.JobsResponse)
def get_jobs(limit: Optional[int] = Query(default=None, ge=1)) -> schemas.JobsResponse:
    """Return the latest scraped jobs from disk."""
    jobs = service.load_latest_jobs()
    if limit is not None:
        jobs = jobs[:limit]
    return schemas.JobsResponse(count=len(jobs), jobs=jobs)


@app.get("/jobs/grouped", response_model=schemas.GroupedJobsResponse)
def get_grouped_jobs(
    limit: Optional[int] = Query(default=None, ge=1),
) -> schemas.GroupedJobsResponse:
    """Return the latest scraped jobs grouped by company + exact role title.

    ``limit`` caps the number of groups (not postings).
    """
    groups = service.load_grouped_jobs(limit)
    return schemas.GroupedJobsResponse(count=len(groups), groups=groups)


@app.post("/filter/experience", response_model=schemas.ExperienceFilterResponse)
def filter_experience(
    request: schemas.ExperienceFilterRequest,
) -> schemas.ExperienceFilterResponse:
    """Agent 1 — keep only jobs whose required experience overlaps the target window.

    If the request sets neither ``min_years`` nor ``max_years`` the config.py
    defaults are used. Note: this makes one LLM call per job (synchronous).
    """
    jobs = request.jobs if request.jobs is not None else service.load_latest_jobs()
    if request.min_years is None and request.max_years is None:
        cfg = service.load_config()
        min_years = cfg.get("experience_min_years", 0)
        max_years = cfg.get("experience_max_years")
    else:
        min_years = request.min_years if request.min_years is not None else 0
        max_years = request.max_years
    filtered = _call_agent(service.filter_experience, jobs, min_years, max_years)
    return schemas.ExperienceFilterResponse(
        input_count=len(jobs),
        filtered_count=len(filtered),
        min_years=min_years,
        max_years=max_years,
        jobs=filtered,
    )


@app.post("/filter/experience/stream")
def filter_experience_stream(
    request: schemas.ExperienceFilterRequest,
) -> StreamingResponse:
    """Agent 1 (streaming) — evaluate each posting one-by-one and stream a verdict.

    Emits ``start`` -> ``job`` (each tagged ``selected`` true/false, with a
    ``percent``) -> ``done``. Jobs default to the latest scraped list and the
    window defaults to config.py, mirroring ``POST /filter/experience``. Makes
    one LLM call per posting, so a working AI key is required.
    """
    return StreamingResponse(
        service.stream_filter_experience(
            request.jobs, request.min_years, request.max_years
        ),
        media_type="application/x-ndjson",
    )


@app.post("/screen/stream")
async def screen_stream(
    resume: UploadFile = File(..., description="Resume as a .docx file"),
    min_years: Optional[int] = Form(default=None, description="Target window lower bound"),
    max_years: Optional[int] = Form(default=None, description="Target window upper bound; blank = open-ended"),
    jobs: Optional[str] = Form(
        default=None, description="JSON array of jobs; defaults to the latest scraped list"
    ),
) -> StreamingResponse:
    """Agents 1+2 combined (streaming) — screen each posting against the resume.

    For every job, ONE LLM call both estimates its required experience and
    scores how well the resume fits. Emits ``start`` -> ``job`` (each tagged
    ``match`` true/false and carrying score / verdict / matched+missing skills)
    -> ``done``. Jobs default to the latest scraped list and the window defaults
    to config.py. Makes one LLM call per posting, so a working AI key is required.
    """
    resume_text = await _read_resume_text(resume)
    parsed_jobs = None
    if jobs:
        try:
            parsed_jobs = json.loads(jobs)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="`jobs` must be valid JSON.")
        if not isinstance(parsed_jobs, list):
            raise HTTPException(status_code=400, detail="`jobs` must be a JSON array.")
    return StreamingResponse(
        service.stream_screen_jobs(resume_text, parsed_jobs, min_years, max_years),
        media_type="application/x-ndjson",
    )


@app.post("/suitability", response_model=schemas.SuitabilityResponse)
async def suitability(
    resume: UploadFile = File(..., description="Resume as a .docx file"),
    job_id: Optional[str] = Form(default=None, description="Id of a scraped job"),
    job: Optional[str] = Form(default=None, description="A job as a JSON object"),
) -> schemas.SuitabilityResponse:
    """Agent 2 — assess how suitable the resume is for a job."""
    resume_text = await _read_resume_text(resume)
    target_job = _resolve_job(job_id, job)
    assessment = _call_agent(service.assess, target_job, resume_text)
    return schemas.SuitabilityResponse(job=service._job_summary(target_job), **assessment)


@app.post("/tailor-resume")
async def tailor_resume(
    resume: UploadFile = File(..., description="Resume as a .docx file"),
    job_id: Optional[str] = Form(default=None, description="Id of a scraped job"),
    job: Optional[str] = Form(default=None, description="A job as a JSON object"),
) -> StreamingResponse:
    """Agent 3 — rewrite the resume for a job and return an updated .docx."""
    resume_text = await _read_resume_text(resume)
    target_job = _resolve_job(job_id, job)
    docx_bytes = _call_agent(service.tailor_to_docx, resume_text, target_job)
    filename = f"tailored_resume_{service._sanitize_filename(str(target_job.get('id', 'job')))}.docx"
    return StreamingResponse(
        BytesIO(docx_bytes),
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/run", response_model=schemas.RunAccepted, status_code=202)
async def run_full(
    background_tasks: BackgroundTasks,
    resume: UploadFile = File(..., description="Resume as a .docx file"),
    top_n: int = Form(default=10, description="Max resumes to tailor"),
    min_score: int = Form(default=60, description="Only tailor jobs scoring >= this"),
    scrape: bool = Form(default=False, description="Scrape fresh jobs first"),
) -> schemas.RunAccepted:
    """Full chain (background): scrape/load -> experience filter -> suitability -> tailor.

    The resume is read up front; poll GET /run/{run_id} for progress and results.
    """
    resume_text = await _read_resume_text(resume)
    run_id = tasks.create_run()
    background_tasks.add_task(
        service.run_full_task, run_id, resume_text, top_n, min_score, scrape
    )
    return schemas.RunAccepted(run_id=run_id)


@app.get("/run/{run_id}", response_model=schemas.RunStatus)
def run_status(run_id: str) -> schemas.RunStatus:
    run = tasks.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id '{run_id}'.")
    return schemas.RunStatus(**run)


@app.get("/run/{run_id}/resume/{job_id}")
def download_tailored_resume(run_id: str, job_id: str) -> FileResponse:
    path = service.resume_path(run_id, job_id)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No tailored resume for run '{run_id}', job '{job_id}'.",
        )
    return FileResponse(
        path, media_type=DOCX_MEDIA_TYPE, filename=path.name
    )
