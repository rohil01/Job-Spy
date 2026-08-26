"""Service layer: orchestrates the scraper and the three AI agents.

The FastAPI routes in ``app.py`` stay thin; all the wiring lives here so it can
be unit-tested and reused. Blocking work (scraping, LLM calls) is invoked from
background tasks by ``app.py`` via Starlette's threadpool.
"""

import json
import math
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from scraper.scraper import JobScraper
from Agent.ai_job_agent import AIJobAgent
from Agent.resume_io import build_docx

from . import tasks

# --------------------------------------------------------------------------- #
# Shared config / singletons
# --------------------------------------------------------------------------- #
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_OUTPUT_ROOT = _PROJECT_ROOT / "data" / "output"

_agent: Optional[AIJobAgent] = None
_agent_lock = threading.Lock()


def load_config() -> Dict[str, Any]:
    return config.load_config()


def get_agent() -> AIJobAgent:
    """Lazy, thread-safe singleton for the AI agent."""
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                _agent = AIJobAgent()
    return _agent


def get_scraper(overrides: Optional[Dict[str, Any]] = None) -> JobScraper:
    """Fresh scraper (re-reads config.py each time).

    When ``overrides`` is given, they are merged over config.py so callers can
    set custom scrape parameters without editing config.py.
    """
    if overrides:
        return JobScraper({**load_config(), **overrides})
    return JobScraper()


def scrape_defaults() -> Dict[str, Any]:
    """The scrape-related subset of config.py, for prefilling the UI."""
    cfg = load_config()
    keys = (
        "sites",
        "search_terms",
        "location",
        "results_wanted",
        "hours_old",
        "country_indeed",
        "linkedin_fetch_description",
        "scrape_cooldown_minutes",
    )
    return {key: cfg[key] for key in keys}


def agent_status() -> Dict[str, Any]:
    """Provider / model / readiness info for the health endpoint."""
    agent = get_agent()
    return {
        "ai_provider": agent.ai_provider,
        "ai_model": agent.ai_model,
        "ai_client_ready": agent._ai_client is not None,
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _json_sanitize(value: Any) -> Any:
    """Replace NaN/Infinity (pandas leftovers) with None so output is valid JSON."""
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else value
    if isinstance(value, dict):
        return {key: _json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_sanitize(item) for item in value]
    return value


def _scraped_path() -> Path:
    return _PROJECT_ROOT / load_config().get("scraped_jobs_path", "data/scraped_jobs.json")


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:120] or "job"


def _job_summary(job: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("id", "site", "title", "company", "location", "job_url", "date_posted")
    return {key: job.get(key) for key in keys if key in job}


def output_dir(run_id: str) -> Path:
    return _OUTPUT_ROOT / _sanitize_filename(run_id)


def resume_path(run_id: str, job_id: str) -> Path:
    return output_dir(run_id) / f"resume_{_sanitize_filename(job_id)}.docx"


def load_latest_jobs() -> List[Dict[str, Any]]:
    """Read the most recent scraped jobs from disk (empty list if none)."""
    path = _scraped_path()
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return _json_sanitize(data) if isinstance(data, list) else []


def find_job_by_id(job_id: str, jobs: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    jobs = jobs if jobs is not None else load_latest_jobs()
    for job in jobs:
        if str(job.get("id")) == str(job_id) or str(job.get("job_url")) == str(job_id):
            return job
    return None


# --------------------------------------------------------------------------- #
# Individual steps
# --------------------------------------------------------------------------- #
def filter_experience(
    jobs: List[Dict[str, Any]],
    min_years: Optional[int] = None,
    max_years: Optional[int] = None,
) -> List[Dict[str, Any]]:
    return get_agent().filter_by_experience_years(jobs, min_years, max_years)


def assess(job: Dict[str, Any], resume_text: str) -> Dict[str, Any]:
    return get_agent().assess_suitability(job, resume_text)


def tailor_to_docx(resume_text: str, job: Dict[str, Any]) -> bytes:
    resume = get_agent().tailor_resume(resume_text, job)
    return build_docx(resume)


# --------------------------------------------------------------------------- #
# Background tasks
# --------------------------------------------------------------------------- #
def run_scrape_task(run_id: str, overrides: Optional[Dict[str, Any]] = None) -> None:
    """Background: scrape (config.py, optionally overridden) and save to JSON."""
    try:
        tasks.update_run(run_id, status="running", progress="scraping", percent=0.0)

        def _on_progress(completed: int, total: int, message: str) -> None:
            percent = round(100.0 * completed / total, 1) if total else None
            tasks.update_run(run_id, progress=message, percent=percent)

        jobs = get_scraper(overrides).scrape_and_save(progress_callback=_on_progress)
        tasks.update_run(
            run_id,
            status="completed",
            progress="done",
            percent=100.0,
            result={
                "count": len(jobs),
                "path": str(_scraped_path()),
                "params": overrides or {},
            },
        )
    except Exception as exc:  # noqa: BLE001 - surface failure via run status
        tasks.update_run(run_id, status="failed", error=str(exc))


def run_full_task(
    run_id: str,
    resume_text: str,
    top_n: int = 10,
    min_score: int = 60,
    do_scrape: bool = False,
) -> None:
    """Background: scrape/load -> experience filter -> suitability -> tailor.

    Chains all four functionalities. Writes tailored resumes and a result.json
    into ``data/output/{run_id}/``.
    """
    try:
        tasks.update_run(run_id, status="running", progress="loading jobs")
        if do_scrape:
            tasks.update_run(run_id, progress="scraping")
            jobs = get_scraper().scrape_and_save()
        else:
            jobs = load_latest_jobs()

        if not jobs:
            tasks.update_run(
                run_id,
                status="completed",
                progress="done",
                result={
                    "jobs_considered": 0,
                    "experience_matched": 0,
                    "tailored": 0,
                    "results": [],
                    "message": "No jobs available. POST /scrape first (or pass scrape=true).",
                },
            )
            return

        agent = get_agent()
        cfg = load_config()
        min_years = cfg.get("experience_min_years", 0)
        max_years = cfg.get("experience_max_years")

        tasks.update_run(run_id, progress=f"experience filter over {len(jobs)} jobs")
        filtered = agent.filter_by_experience_years(jobs, min_years, max_years)

        assessed: List[tuple] = []
        for index, job in enumerate(filtered):
            tasks.update_run(run_id, progress=f"assessing {index + 1}/{len(filtered)}")
            assessed.append((job, agent.assess_suitability(job, resume_text)))

        def _score(pair: tuple) -> float:
            score = pair[1].get("score")
            return float(score) if isinstance(score, (int, float)) else -1.0

        assessed.sort(key=_score, reverse=True)

        out_dir = output_dir(run_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        results: List[Dict[str, Any]] = []
        tailored_count = 0
        for job, suitability in assessed:
            entry: Dict[str, Any] = {
                "job": _job_summary(job),
                "suitability": suitability,
                "resume_file": None,
            }
            score = suitability.get("score")
            if (
                tailored_count < top_n
                and isinstance(score, (int, float))
                and score >= min_score
            ):
                tasks.update_run(
                    run_id, progress=f"tailoring resume for {job.get('title', '')}"
                )
                job_id = _sanitize_filename(
                    str(job.get("id") or job.get("job_url") or tailored_count)
                )
                docx_bytes = tailor_to_docx(resume_text, job)
                (out_dir / f"resume_{job_id}.docx").write_bytes(docx_bytes)
                entry["job_id"] = job_id
                entry["resume_file"] = f"resume_{job_id}.docx"
                entry["resume_download"] = f"/run/{run_id}/resume/{job_id}"
                tailored_count += 1
            results.append(entry)

        result = {
            "jobs_considered": len(jobs),
            "experience_matched": len(filtered),
            "tailored": tailored_count,
            "results": results,
        }
        (out_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tasks.update_run(run_id, status="completed", progress="done", result=result)
    except Exception as exc:  # noqa: BLE001 - surface failure via run status
        tasks.update_run(run_id, status="failed", error=str(exc))
